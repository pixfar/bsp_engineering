import frappe

REQUIRED_ACTIONS = [
	'Submit',
	'Request Review',
	'Approve',
	'Reject',
	'Review',
	'Cancel',
]


def execute():
	for action_name in REQUIRED_ACTIONS:
		_ensure_workflow_action(action_name)


def _ensure_workflow_action(action_name):
	if frappe.db.exists('Workflow Action Master', action_name):
		return

	frappe.get_doc(
		{
			'doctype': 'Workflow Action Master',
			'workflow_action_name': action_name,
		}
	).insert(ignore_permissions=True)
