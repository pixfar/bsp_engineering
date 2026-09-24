import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from erpnext.manufacturing.doctype.production_plan.production_plan import (
	ProductionPlan as ERPNextProductionPlan,
)
from erpnext.manufacturing.doctype.work_order.work_order import (
	OverProductionError,
	get_default_warehouse,
)


def get_source_warehouse_for_production_plan(production_plan):
	if production_plan.get('for_warehouse'):
		return production_plan.for_warehouse

	default_warehouses = get_default_warehouse()
	return default_warehouses.get('wip_warehouse')


def apply_raw_material_overrides(wo, overrides):
	"""Replace the BOM-derived required_items with a user-edited raw material
	list (qty changed, rows removed or added) for this one Work Order only --
	the BOM itself is left untouched.

	`overrides` is a list of {"item_code", "qty"} with qty being the total for
	the whole Work Order qty. Passed in through the Production Plan's
	flags.raw_material_overrides (keyed by production item) by POS Awesome's
	create_production_plan, because the Work Order is created and
	auto-submitted inside the plan's own insert -- there is no later point at
	which required_items could still be edited.

	Only safe because the Work Order is inserted/submitted with
	flags.ignore_validate (see create_work_order), which skips ERPNext's
	validate() and so its reset of required_items back to BOM quantities.
	"""
	if not overrides:
		return

	existing = {row.item_code: row for row in wo.required_items}
	rows = []
	for override in overrides:
		item_code = override.get('item_code')
		qty = flt(override.get('qty'))
		if not item_code or qty <= 0:
			continue
		row = existing.get(item_code)
		if row:
			row.required_qty = qty
			row.amount = flt(row.rate) * qty
			rows.append(row)
			continue
		item = frappe.get_cached_value(
			'Item', item_code, ['item_name', 'stock_uom', 'description', 'valuation_rate'], as_dict=True
		)
		if not item:
			frappe.throw(_('Raw material {0} does not exist.').format(item_code))
		rows.append(
			frappe._dict(
				item_code=item_code,
				item_name=item.item_name,
				stock_uom=item.stock_uom,
				description=item.description,
				required_qty=qty,
				rate=flt(item.valuation_rate),
				amount=flt(item.valuation_rate) * qty,
				include_item_in_manufacturing=1,
				operation=wo.operations[0].operation if len(wo.get('operations') or []) == 1 else None,
			)
		)

	if not rows:
		frappe.throw(_('At least one raw material is required for {0}.').format(wo.production_item))

	skip = {'name', 'idx', 'parent', 'parentfield', 'parenttype', 'doctype'}
	wo.required_items = []
	for row in rows:
		values = row.as_dict() if isinstance(row, Document) else row
		wo.append('required_items', {k: v for k, v in values.items() if k not in skip})
	wo.set_available_qty()


class ProductionPlan(ERPNextProductionPlan):
	def create_work_order(self, item):
		if flt(item.get('qty')) <= 0:
			return

		wo = frappe.new_doc('Work Order')
		wo.update(item)
		wo.planned_start_date = item.get('planned_start_date') or item.get('schedule_date')

		if item.get('warehouse'):
			wo.fg_warehouse = item.get('warehouse')

		# BSP doesn't manufacture sub-assemblies as separate stock -- required_items
		# should list exactly what's on the BOM itself (checked against stock as-is),
		# never exploded into a linked sub-BOM's own raw materials. Must be set
		# before set_required_items(), which reads this to decide whether to explode.
		wo.use_multi_level_bom = 0

		wo.set_work_order_operations()
		wo.set_required_items()
		apply_raw_material_overrides(wo, (self.flags.get('raw_material_overrides') or {}).get(wo.production_item))

		source_warehouse = get_source_warehouse_for_production_plan(self)
		if source_warehouse:
			wo.source_warehouse = source_warehouse
			for row in wo.required_items:
				row.source_warehouse = source_warehouse
		else:
			frappe.msgprint(
				_(
					'Source Warehouse could not be set. Please set '
					'<b>Raw Materials Warehouse</b> on the Production Plan '
					'or <b>Default Work In Progress Warehouse</b> in '
					'Manufacturing Settings.'
				),
				indicator='orange',
				alert=True,
			)

		try:
			wo.flags.ignore_mandatory = True
			wo.flags.ignore_validate = True
			wo.insert()
			return wo.name
		except OverProductionError:
			pass
