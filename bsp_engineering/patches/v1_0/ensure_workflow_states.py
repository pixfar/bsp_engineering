import frappe

WORKFLOW_STATES = {
	'Draft': 'Primary',
	'Pending Review': 'Warning',
	'Approved': 'Success',
	'Rejected': 'Danger',
	'Cancelled': 'Danger',
	'In Transit': 'Warning',
	'Requisition Received': 'Success',
}


def execute():
	for state_name, style in WORKFLOW_STATES.items():
		_ensure_workflow_state(state_name, style)


def _ensure_workflow_state(state_name, style):
	if frappe.db.exists('Workflow State', state_name):
		return

	frappe.get_doc(
		{
			'doctype': 'Workflow State',
			'workflow_state_name': state_name,
			'style': style,
		}
	).insert(ignore_permissions=True)
