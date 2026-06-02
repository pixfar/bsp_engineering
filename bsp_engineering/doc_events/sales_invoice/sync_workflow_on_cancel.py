import frappe
from frappe.model.workflow import get_workflow_name, set_workflow_state_on_action


def sync_workflow_state_on_cancel(doc, method=None):
	"""Set workflow_state to the cancelled state when a Sales Invoice is cancelled."""
	workflow_name = get_workflow_name(doc.doctype)
	if not workflow_name:
		return

	set_workflow_state_on_action(doc, workflow_name, 'cancel')

	workflow = frappe.get_doc('Workflow', workflow_name)
	fieldname = workflow.workflow_state_field
	new_state = doc.get(fieldname)
	if not new_state:
		return

	frappe.db.set_value(
		doc.doctype,
		doc.name,
		fieldname,
		new_state,
		update_modified=False,
	)
