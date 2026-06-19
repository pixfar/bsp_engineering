import frappe

WORKFLOW_NAME = 'BSP Material Transfer Receipt'
STATE_NAME = 'Manufacture Completed'


def execute():
	_ensure_workflow_state()
	_ensure_workflow_document_state()
	_backfill_manufacture_stock_entries()


def _ensure_workflow_state():
	if frappe.db.exists('Workflow State', STATE_NAME):
		return

	frappe.get_doc(
		{
			'doctype': 'Workflow State',
			'workflow_state_name': STATE_NAME,
			'style': 'Success',
		}
	).insert(ignore_permissions=True)


def _ensure_workflow_document_state():
	if not frappe.db.exists('Workflow', WORKFLOW_NAME):
		return

	if frappe.db.exists(
		'Workflow Document State',
		{'parent': WORKFLOW_NAME, 'state': STATE_NAME},
	):
		return

	workflow = frappe.get_doc('Workflow', WORKFLOW_NAME)
	max_idx = max((row.idx or 0 for row in workflow.states), default=0)
	frappe.get_doc(
		{
			'doctype': 'Workflow Document State',
			'parent': WORKFLOW_NAME,
			'parenttype': 'Workflow',
			'parentfield': 'states',
			'idx': max_idx + 1,
			'state': STATE_NAME,
			'doc_status': '1',
			'allow_edit': 'Stock User',
			'send_email': 0,
		}
	).db_insert()


def _backfill_manufacture_stock_entries():
	if not frappe.db.has_column('Stock Entry', 'workflow_state'):
		return

	filters = {
		'docstatus': 1,
		'stock_entry_type': 'Manufacture',
		'workflow_state': ['in', ['In Transit', None, '']],
	}
	if frappe.db.has_column('Stock Entry', 'custom_requisition'):
		filters['custom_requisition'] = ['is', 'not set']
	if frappe.db.has_column('Stock Entry', 'custom_material_transfer'):
		filters['custom_material_transfer'] = ['is', 'not set']

	for name in frappe.get_all('Stock Entry', filters=filters, pluck='name'):
		frappe.db.set_value(
			'Stock Entry',
			name,
			'workflow_state',
			STATE_NAME,
			update_modified=False,
		)
