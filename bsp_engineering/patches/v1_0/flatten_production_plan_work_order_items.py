import frappe
from frappe.utils import flt


def execute():
	"""BSP doesn't manufacture sub-assemblies as separate stock, but
	Work Orders auto-created from a Production Plan used to explode them
	anyway (use_multi_level_bom = 1 was ERPNext's own default) -- so
	required_items ended up listing a linked sub-BOM's own raw materials
	instead of the parent BOM's own item list. production_plan.py's
	create_work_order override and the Work Order before_validate hook
	(bsp_engineering.doc_events.work_order.sync_source_warehouse) now keep
	this flattened going forward. Flatten any such Work Order that already
	exists and hasn't had any stock movement yet, so it matches too.
	"""
	from bsp_engineering.overrides.production_plan import get_source_warehouse_for_production_plan

	work_orders = frappe.get_all(
		'Work Order',
		filters={
			'production_plan': ['is', 'set'],
			'docstatus': 1,
			'use_multi_level_bom': 1,
		},
		pluck='name',
	)

	for wo_name in work_orders:
		try:
			_flatten(wo_name, get_source_warehouse_for_production_plan)
		except Exception:
			frappe.log_error(
				title=f'flatten_production_plan_work_order_items: {wo_name}',
				message=frappe.get_traceback(),
			)


def _flatten(wo_name, get_source_warehouse_for_production_plan):
	wo_doc = frappe.get_doc('Work Order', wo_name)

	if any(flt(row.transferred_qty) or flt(row.consumed_qty) for row in wo_doc.required_items):
		# Production already started against these rows -- leave it alone.
		return

	if not wo_doc.bom_no or not flt(wo_doc.qty):
		return

	old_row_names = [row.name for row in wo_doc.required_items]

	source_warehouse = None
	if wo_doc.production_plan:
		production_plan = frappe.get_cached_doc('Production Plan', wo_doc.production_plan)
		source_warehouse = get_source_warehouse_for_production_plan(production_plan)

	wo_doc.use_multi_level_bom = 0
	wo_doc.set_required_items()  # rebuilds required_items in memory, flattened to the BOM's own items

	if source_warehouse:
		for row in wo_doc.required_items:
			row.source_warehouse = source_warehouse
		# set_required_items() already computed available_qty_at_source_warehouse,
		# but against each item's own default warehouse -- redo it now that every
		# row points at the plan's warehouse instead.
		wo_doc.set_available_qty()

	for row in wo_doc.required_items:
		row.db_insert()

	if old_row_names:
		frappe.db.delete('Work Order Item', {'name': ['in', old_row_names]})

	frappe.db.set_value('Work Order', wo_doc.name, 'use_multi_level_bom', 0, update_modified=False)
