import frappe

CANCELLED_STATUS = 'Cancelled'
DELIVERY_STATUS_OPTIONS = (
	'\nNot Received\nPartially Received\nFully Received\nCancelled'
)


def execute():
	_ensure_select_options()
	_backfill_cancelled_purchase_invoices()


def _ensure_select_options():
	fieldname = 'Purchase Invoice-custom_delivery_status'
	if not frappe.db.exists('Custom Field', fieldname):
		return

	current = frappe.db.get_value('Custom Field', fieldname, 'options') or ''
	if CANCELLED_STATUS in current.split('\n'):
		return

	frappe.db.set_value(
		'Custom Field',
		fieldname,
		'options',
		DELIVERY_STATUS_OPTIONS,
		update_modified=False,
	)


def _backfill_cancelled_purchase_invoices():
	if not frappe.db.has_column('Purchase Invoice', 'custom_delivery_status'):
		return

	frappe.db.sql(
		"""
		UPDATE `tabPurchase Invoice`
		SET custom_delivery_status = %s
		WHERE docstatus = 2
			AND IFNULL(custom_delivery_status, '') != %s
		""",
		(CANCELLED_STATUS, CANCELLED_STATUS),
	)
