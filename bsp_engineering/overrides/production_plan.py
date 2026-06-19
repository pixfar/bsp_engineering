import frappe
from frappe import _
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


class ProductionPlan(ERPNextProductionPlan):
	def create_work_order(self, item):
		if flt(item.get('qty')) <= 0:
			return

		wo = frappe.new_doc('Work Order')
		wo.update(item)
		wo.planned_start_date = item.get('planned_start_date') or item.get('schedule_date')

		if item.get('warehouse'):
			wo.fg_warehouse = item.get('warehouse')

		wo.set_work_order_operations()
		wo.set_required_items()

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
