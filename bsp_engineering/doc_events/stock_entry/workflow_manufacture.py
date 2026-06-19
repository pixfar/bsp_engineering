import frappe

MANUFACTURE_COMPLETED_STATE = 'Manufacture Completed'


def uses_manufacture_workflow(doc):
	if doc.get('custom_requisition') or doc.get('custom_material_transfer'):
		return False

	stock_entry_type = doc.get('stock_entry_type') or ''
	purpose = doc.get('purpose') or ''
	return stock_entry_type == 'Manufacture' or purpose == 'Manufacture'


def apply_manufacture_workflow_state(doc, method=None):
	if doc.docstatus != 1 or not uses_manufacture_workflow(doc):
		return

	if doc.get('workflow_state') == MANUFACTURE_COMPLETED_STATE:
		return

	frappe.db.set_value(
		'Stock Entry',
		doc.name,
		'workflow_state',
		MANUFACTURE_COMPLETED_STATE,
		update_modified=False,
	)
	doc.workflow_state = MANUFACTURE_COMPLETED_STATE
