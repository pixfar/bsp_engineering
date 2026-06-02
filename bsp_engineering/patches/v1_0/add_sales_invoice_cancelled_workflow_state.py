import frappe
from frappe.model.workflow import get_workflow_name


WORKFLOW_NAME = 'Sales Invoice Approval'
CANCELLED_STATE = 'Cancelled'


def execute():
	_ensure_workflow_state(CANCELLED_STATE)
	_ensure_workflow_document_state()
	_backfill_cancelled_sales_invoices()


def _ensure_workflow_state(state_name):
	if frappe.db.exists('Workflow State', state_name):
		return

	frappe.get_doc(
		{
			'doctype': 'Workflow State',
			'workflow_state_name': state_name,
			'style': 'Danger',
		}
	).insert(ignore_permissions=True)


def _ensure_workflow_document_state():
	if not frappe.db.exists('Workflow', WORKFLOW_NAME):
		return

	workflow = frappe.get_doc('Workflow', WORKFLOW_NAME)
	if _has_cancelled_state(workflow):
		return

	workflow.append(
		'states',
		{
			'state': CANCELLED_STATE,
			'doc_status': '2',
			'allow_edit': 'All',
		},
	)
	workflow.save(ignore_permissions=True)


def _has_cancelled_state(workflow):
	for row in workflow.states:
		if row.state == CANCELLED_STATE and str(row.doc_status) == '2':
			return True
	return False


def _backfill_cancelled_sales_invoices():
	if not frappe.db.has_column('Sales Invoice', 'workflow_state'):
		return

	workflow_name = get_workflow_name('Sales Invoice') or WORKFLOW_NAME
	if not frappe.db.exists('Workflow', workflow_name):
		return

	workflow = frappe.get_doc('Workflow', workflow_name)
	cancelled_state = _get_cancelled_workflow_state(workflow)
	if not cancelled_state:
		return

	fieldname = workflow.workflow_state_field or 'workflow_state'

	frappe.db.sql(
		f"""
		UPDATE `tabSales Invoice`
		SET `{fieldname}` = %s
		WHERE docstatus = 2
			AND IFNULL(`{fieldname}`, '') != %s
		""",
		(cancelled_state, cancelled_state),
	)


def _get_cancelled_workflow_state(workflow):
	for row in workflow.states:
		if str(row.doc_status) == '2':
			return row.state
	return None
