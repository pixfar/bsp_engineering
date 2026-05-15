import frappe
from frappe import _
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
	# POS invoices: payment captured by POS itself, auto-mark as paid
	if doc.is_pos or doc.pos_profile:
		doc.db_set('custom_is_paid', 1, update_modified=False)
		return True, 'POS invoice — payment handled by POS.'

	# Respect the Is Paid checkbox — skip if unchecked
	if not doc.custom_is_paid:
		return False, 'Payment entry skipped — Is Paid is unchecked.'

	if _has_existing_payment_entry(doc.name):
		return True, 'Payment Entry already exists for this invoice.'

	try:
		payment_entry = get_payment_entry('Sales Invoice', doc.name)
		payment_entry.posting_date = doc.posting_date
		payment_entry.reference_no = doc.name
		payment_entry.reference_date = doc.posting_date
		payment_entry.insert(ignore_permissions=True)
		payment_entry.submit()
		return True, f'Payment Entry {payment_entry.name} created.'
	except Exception as error:
		frappe.log_error(
			frappe.get_traceback(),
			f'Payment Entry creation failed for Sales Invoice {doc.name}',
		)
		doc.db_set('custom_is_paid', 0, update_modified=False)
		return (
			False,
			f'Unable to create Payment Entry automatically: {error}',
		)


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