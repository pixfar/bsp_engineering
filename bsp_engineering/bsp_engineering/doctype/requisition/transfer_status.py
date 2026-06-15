import frappe
from frappe.utils import flt

STATUS_NOT = 'Not Transferred'
STATUS_IN_TRANSIT = 'In Transit'
STATUS_PARTIAL = 'Partially Transferred'
STATUS_FULL = 'Fully Transferred'
STATUS_OVER = 'Over Transferred'


def get_requested_total(requisition_doc):
	return sum(flt(row.required_qty) for row in requisition_doc.items)


def get_transferred_total(requisition_name):
	if not frappe.db.has_column('Stock Entry', 'custom_requisition'):
		return 0.0
	result = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(sed.qty), 0)
		FROM `tabStock Entry Detail` sed
		INNER JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.docstatus = 1
			AND se.custom_requisition = %s
		""",
		requisition_name,
	)
	return flt(result[0][0]) if result else 0.0


def get_transferred_by_item(requisition_name):
	if not frappe.db.has_column('Stock Entry Detail', 'custom_requisition_item'):
		return {}
	rows = frappe.db.sql(
		"""
		SELECT sed.custom_requisition_item, COALESCE(SUM(sed.qty), 0) AS qty
		FROM `tabStock Entry Detail` sed
		INNER JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.docstatus = 1
			AND se.custom_requisition = %s
			AND IFNULL(sed.custom_requisition_item, '') != ''
		GROUP BY sed.custom_requisition_item
		""",
		requisition_name,
		as_dict=True,
	)
	return {row.custom_requisition_item: flt(row.qty) for row in rows}


def has_in_transit_stock_entry(requisition_name):
	"""Return True if there is a linked SE in workflow_state='In Transit' not yet confirmed."""
	if not frappe.db.has_column('Stock Entry', 'custom_requisition'):
		return False
	return frappe.db.exists('Stock Entry', {
		'custom_requisition': requisition_name,
		'workflow_state': 'In Transit',
		'docstatus': ['!=', 2],
	})


def calculate_transfer_status(requisition_doc):
	if requisition_doc.docstatus != 1:
		return STATUS_NOT

	requested = get_requested_total(requisition_doc)
	transferred = get_transferred_total(requisition_doc.name)

	if not requested:
		return STATUS_NOT

	# Stock confirmed-received (docstatus=1) takes precedence
	if transferred > 0:
		if transferred == requested:
			return STATUS_FULL
		if transferred < requested:
			return STATUS_PARTIAL
		return STATUS_OVER

	# No confirmed receipts yet — check for pending in-transit SE
	if has_in_transit_stock_entry(requisition_doc.name):
		return STATUS_IN_TRANSIT

	return STATUS_NOT


def update_requisition_transfer_status(requisition_name):
	if not requisition_name or not frappe.db.exists('Requisition', requisition_name):
		return

	requisition = frappe.get_doc('Requisition', requisition_name)
	status = calculate_transfer_status(requisition)
	if requisition.transfer_status == status:
		return

	frappe.db.set_value(
		'Requisition',
		requisition_name,
		'transfer_status',
		status,
		update_modified=False,
	)
