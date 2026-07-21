import frappe
from frappe import _
from frappe.utils import flt
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_payment_entry,
)

from bsp_engineering.doc_events.sales_invoice.create_delivery import (
	create_delivery_note_from_sales_invoice,
)



def create_payment_and_delivery_on_submit(doc, method=None):
	paid_success, paid_message = create_payment_entry_from_sales_invoice(doc)
	delivery_success, delivery_message = create_delivery_note_from_sales_invoice(doc)

	indicator = 'green' if paid_success and delivery_success else 'orange'
	frappe.msgprint(
		_(
			'Payment Status: {0}<br>Delivery Status: {1}'
		).format(paid_message, delivery_message),
		title=_('Sales Invoice Automation Result'),
		indicator=indicator,
	)


def create_payment_entry_from_sales_invoice(doc, method=None):
	if doc.is_return:
		doc.db_set('custom_is_paid', 0, update_modified=False)
		return False, 'Return invoice — payment entry not applicable.'

	# Non-POS invoices: only proceed if custom_is_paid is checked
	if not doc.is_pos and not doc.pos_profile:
		if not doc.custom_is_paid:
			return False, 'Payment entry skipped — Is Paid is unchecked.'

		if _has_existing_payment_entry(doc.name):
			return True, 'Payment Entry already exists for this invoice.'

		return _create_full_payment_entry(doc)

	# POS invoices with is_pos=1 have accounting handled internally via the
	# payments child table (ERPNext posts payment-side GL directly from those
	# rows, so a separate Payment Entry would double-post the same money).
	#
	# POS Awesome flips is_pos to 0 before submit specifically to skip that
	# direct GL posting for every POS sale — pos_profile stays set so the
	# invoice is still a recognised POS sale everywhere else (shift totals,
	# etc). In that case we create one real, submitted Payment Entry per
	# payment method here instead.
	if not doc.is_pos:
		if _has_existing_payment_entry(doc.name):
			doc.db_set('custom_is_paid', 1, update_modified=False)
			return True, 'Payment Entries already exist for this invoice.'
		return _create_payment_entries_per_payment_method(doc)

	invoice_total = flt(doc.rounded_total or doc.grand_total)
	paid_amount = flt(doc.paid_amount)

	if paid_amount >= invoice_total - 0.001:
		doc.db_set('custom_is_paid', 1, update_modified=False)
		return True, 'POS invoice — fully paid.'

	if paid_amount > 0.001:
		doc.db_set('custom_is_paid', 0, update_modified=False)
		return True, f'POS invoice — partially paid ({paid_amount} of {invoice_total}).'

	doc.db_set('custom_is_paid', 0, update_modified=False)
	return False, 'POS invoice — no payment recorded.'


def _create_payment_entries_per_payment_method(doc):
	"""Create one submitted Payment Entry per payment method row on a POS
	invoice that was submitted with is_pos=0 (see caller for why).

	Reads from `custom_payment_method_split` rather than the standard
	`payments` child table: ERPNext's own calculate_paid_amount()
	(taxes_and_totals.py) wipes `payments` to [] on every validate() once
	is_pos is falsy on a non-return invoice, so by the time this on_submit
	hook runs `payments` is already empty. POS Awesome copies the cashier's
	split into `custom_payment_method_split` before flipping is_pos, since
	that's a custom field ERPNext core doesn't know about and won't touch.

	Mirrors the Payment Entry shape POS Awesome itself uses for its own
	generated Payment Entries, including reference_no = POS Opening Shift so
	the invoice's payment still surfaces in POS Closing Shift / Z-report
	totals.
	"""
	created = []

	for row in doc.custom_payment_method_split or []:
		mode_of_payment = row.mode_of_payment
		amount = flt(row.amount)
		if amount <= 0:
			continue

		try:
			payment_entry = frappe.get_doc(
				{
					'doctype': 'Payment Entry',
					'payment_type': 'Receive',
					'party_type': 'Customer',
					'party': doc.customer,
					'company': doc.company,
					'posting_date': doc.posting_date,
					'paid_amount': amount,
					'received_amount': amount,
					'paid_from': doc.debit_to,
					'paid_to': row.account,
					'mode_of_payment': mode_of_payment,
					'reference_no': doc.get('posa_pos_opening_shift') or doc.name,
					'reference_date': doc.posting_date,
					'references': [
						{
							'reference_doctype': 'Sales Invoice',
							'reference_name': doc.name,
							'allocated_amount': amount,
						}
					],
				}
			)
			payment_entry.flags.ignore_permissions = True
			payment_entry.insert(ignore_permissions=True)
			payment_entry.submit()
			created.append(payment_entry.name)
			frappe.db.set_value(
				'Sales Invoice Payment Split', row.name, 'payment_entry', payment_entry.name
			)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f'Payment Entry creation failed for Sales Invoice {doc.name} ({mode_of_payment})',
			)

	if not created:
		doc.db_set('custom_is_paid', 0, update_modified=False)
		return False, 'POS invoice — unable to create Payment Entries.'

	outstanding_amount = flt(frappe.db.get_value('Sales Invoice', doc.name, 'outstanding_amount'))
	is_fully_paid = outstanding_amount <= 0.001
	doc.db_set('custom_is_paid', 1 if is_fully_paid else 0, update_modified=False)

	entry_word = 'Entry' if len(created) == 1 else 'Entries'
	return is_fully_paid, f'{len(created)} Payment {entry_word} created ({", ".join(created)}).'


def _create_full_payment_entry(doc):
	try:
		payment_entry = get_payment_entry('Sales Invoice', doc.name)
		payment_entry.posting_date = doc.posting_date
		payment_entry.reference_no = doc.name
		payment_entry.reference_date = doc.posting_date
		payment_entry.insert(ignore_permissions=True)
		payment_entry.submit()
		doc.db_set('custom_is_paid', 1, update_modified=False)
		return True, f'Payment Entry {payment_entry.name} created.'
	except Exception as error:
		frappe.log_error(
			frappe.get_traceback(),
			f'Payment Entry creation failed for Sales Invoice {doc.name}',
		)
		doc.db_set('custom_is_paid', 0, update_modified=False)
		return False, f'Unable to create Payment Entry automatically: {error}'



def _has_existing_payment_entry(sales_invoice):
	return bool(
		frappe.db.exists(
			'Payment Entry Reference',
			{
				'reference_doctype': 'Sales Invoice',
				'reference_name': sales_invoice,
				'docstatus': ('!=', 2),
			},
		)
	)
