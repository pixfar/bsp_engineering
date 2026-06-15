import frappe
from bsp_engineering.bsp_engineering.doctype.requisition.transfer_status import (
	update_requisition_transfer_status,
)


def sync_requisition_transfer_status(doc, method=None):
	requisition = doc.get('custom_requisition')

	# When the SE is cancelled, mark its workflow state as Cancelled
	# so the form badge reflects reality instead of showing the last active state.
	if doc.docstatus == 2 and doc.get('workflow_state') != 'Cancelled':
		frappe.db.set_value('Stock Entry', doc.name, 'workflow_state', 'Cancelled', update_modified=False)

	if not requisition:
		return
	update_requisition_transfer_status(requisition)
