import frappe
from frappe import _


def on_update(doc, method):
	"""React to Production Plan workflow state transitions."""
	prev = doc.get_doc_before_save()
	if not prev:
		return

	prev_state = getattr(prev, 'workflow_state', None)
	curr_state = getattr(doc, 'workflow_state', None)

	if not curr_state or prev_state == curr_state:
		return

	if curr_state == 'In Production':
		_create_work_orders(doc)
	elif curr_state == 'Completed':
		_close_all_work_orders(doc)


def _create_work_orders(doc):
	"""Create and auto-submit Work Orders for the Production Plan.
	The global auto_submit hook handles submitting each Work Order after insert."""
	doc.make_work_order()


def _close_all_work_orders(doc):
	"""Close all open Work Orders linked to this Production Plan."""
	from erpnext.manufacturing.doctype.work_order.work_order import close_work_order

	work_orders = frappe.get_all(
		'Work Order',
		filters={
			'production_plan': doc.name,
			'docstatus': 1,
			'status': ['not in', ['Completed', 'Closed']],
		},
		pluck='name',
	)

	for wo_name in work_orders:
		close_work_order(wo_name, 'Closed')

	if work_orders:
		frappe.msgprint(
			_("{0} Work Order(s) closed.").format(len(work_orders)),
			alert=True,
		)
