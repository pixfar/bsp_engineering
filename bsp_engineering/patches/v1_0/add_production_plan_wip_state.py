import frappe

WORKFLOW_NAME = 'BSP Production Plan Workflow'


def execute():
	_ensure_workflow_state('Work In Progress', 'Warning')
	_ensure_workflow_state('Production Complete', 'Success')
	_ensure_workflow_action('Start Production')
	_ensure_workflow_action('Mark Production Complete')
	_update_workflow()


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


def _ensure_workflow_action(action_name):
	if frappe.db.exists('Workflow Action Master', action_name):
		return

	frappe.get_doc(
		{
			'doctype': 'Workflow Action Master',
			'workflow_action_name': action_name,
		}
	).insert(ignore_permissions=True)


def _update_workflow():
	if not frappe.db.exists('Workflow', WORKFLOW_NAME):
		return

	workflow = frappe.get_doc('Workflow', WORKFLOW_NAME)

	if any(row.state == 'Work In Progress' for row in workflow.states):
		# Already migrated
		return

	# Rename the submitted "Completed" state to "Production Complete"
	for row in workflow.states:
		if row.state == 'Completed' and str(row.doc_status) == '1':
			row.state = 'Production Complete'

	workflow.append(
		'states',
		{
			'state': 'Work In Progress',
			'doc_status': '0',
			'allow_edit': 'Manufacturing User',
		},
	)

	# Draft -> Mark Completed -> Completed  becomes  Draft -> Start Production -> Work In Progress
	for row in workflow.transitions:
		if row.state == 'Draft' and row.action == 'Mark Completed':
			row.action = 'Start Production'
			row.allowed = 'Manufacturing User'
			row.next_state = 'Work In Progress'
		elif row.action == 'Cancel' and row.state == 'Completed':
			row.state = 'Production Complete'

	# New: Work In Progress -> Mark Production Complete -> Production Complete
	workflow.append(
		'transitions',
		{
			'state': 'Work In Progress',
			'action': 'Mark Production Complete',
			'next_state': 'Production Complete',
			'allowed': 'Manufacturing Manager',
			'allow_self_approval': 1,
		},
	)

	workflow.save(ignore_permissions=True)
