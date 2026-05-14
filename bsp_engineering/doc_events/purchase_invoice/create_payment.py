import frappe
from frappe import _
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_payment_entry,
)


def create_payment_entry_from_purchase_invoice(doc, method=None):
	if _has_existing_payment_entry(doc.name):
		doc.db_set('custom_is_paid', 1, update_modified=False)
		return

	try:
		payment_entry = get_payment_entry('Purchase Invoice', doc.name)
		payment_entry.posting_date = doc.posting_date
		payment_entry.reference_no = doc.name
		payment_entry.reference_date = doc.posting_date
		payment_entry.insert(ignore_permissions=True)
		payment_entry.submit()
		doc.db_set('custom_is_paid', 1, update_modified=False)
		frappe.msgprint(
			_(f'Payment Entry {payment_entry.name} created.'),
			title=_('Payment Created'),
			indicator='green',
		)
	except Exception as error:
		frappe.log_error(
			frappe.get_traceback(),
			f'Payment Entry creation failed for Purchase Invoice {doc.name}',
		)
		doc.db_set('custom_is_paid', 0, update_modified=False)
		frappe.msgprint(
			_(f'Unable to create Payment Entry automatically: {error}'),
			title=_('Payment Creation Failed'),
			indicator='orange',
		)


def _has_existing_payment_entry(purchase_invoice):
	return bool(
		frappe.db.exists(
			'Payment Entry Reference',
			{
				'reference_doctype': 'Purchase Invoice',
				'reference_name': purchase_invoice,
				'docstatus': ('!=', 2),
			},
		)
	)
