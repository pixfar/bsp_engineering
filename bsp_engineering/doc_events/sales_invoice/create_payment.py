import frappe
from frappe import _
from frappe.utils import flt
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_payment_entry,
)

from bsp_engineering.doc_events.sales_invoice.create_delivery import (
	create_delivery_note_from_sales_invoice,
)

PAYMENT_STATUS_PAID = 'Paid'
PAYMENT_STATUS_PARTIAL = 'Partially Paid'
PAYMENT_STATUS_UNPAID = 'Unpaid'


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


def _set_payment_status(doc, status):
	"""Set both custom_is_paid and custom_payment_status in one DB round-trip."""
	is_paid = 1 if status == PAYMENT_STATUS_PAID else 0
	doc.db_set('custom_is_paid', is_paid, update_modified=False)
	doc.db_set('custom_payment_status', status, update_modified=False)


def create_payment_entry_from_sales_invoice(doc, method=None):
	# Non-POS invoices: only proceed if custom_is_paid is checked
	if not doc.is_pos and not doc.pos_profile:
		if not doc.custom_is_paid:
			_set_payment_status(doc, PAYMENT_STATUS_UNPAID)
			return False, 'Payment entry skipped — Is Paid is unchecked.'

		if _has_existing_payment_entry(doc.name):
			_set_payment_status(doc, PAYMENT_STATUS_PAID)
			return True, 'Payment Entry already exists for this invoice.'

		return _create_full_payment_entry(doc)

	# POS invoices: accounting is handled internally via the payments child table.
	# ERPNext sets outstanding_amount = 0 after POS submission regardless of
	# partial payment, so creating a separate Payment Entry is not possible.
	# We only set the status fields based on paid_amount vs invoice total.
	invoice_total = flt(doc.rounded_total or doc.grand_total)
	paid_amount = flt(doc.paid_amount)

	if paid_amount >= invoice_total - 0.001:
		_set_payment_status(doc, PAYMENT_STATUS_PAID)
		return True, 'POS invoice — fully paid.'

	if paid_amount > 0.001:
		_set_payment_status(doc, PAYMENT_STATUS_PARTIAL)
		return True, f'POS invoice — partially paid ({paid_amount} of {invoice_total}).'

	_set_payment_status(doc, PAYMENT_STATUS_UNPAID)
	return False, 'POS invoice — no payment recorded.'


def _create_full_payment_entry(doc):
	try:
		payment_entry = get_payment_entry('Sales Invoice', doc.name)
		payment_entry.posting_date = doc.posting_date
		payment_entry.reference_no = doc.name
		payment_entry.reference_date = doc.posting_date
		payment_entry.insert(ignore_permissions=True)
		payment_entry.submit()
		_set_payment_status(doc, PAYMENT_STATUS_PAID)
		return True, f'Payment Entry {payment_entry.name} created.'
	except Exception as error:
		frappe.log_error(
			frappe.get_traceback(),
			f'Payment Entry creation failed for Sales Invoice {doc.name}',
		)
		_set_payment_status(doc, PAYMENT_STATUS_UNPAID)
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
