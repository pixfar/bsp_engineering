# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import IfNull

from bsp_engineering.utils.item_category_sort import get_item_sort_map, item_category_sort_key
from bsp_engineering.utils.warehouse_sort import get_warehouse_sort_map, warehouse_sort_key


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 200,
		},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 180,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 140,
		},
		{
			"label": _("UOM"),
			"fieldname": "stock_uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 90,
		},
		{
			"label": _("Actual Qty"),
			"fieldname": "actual_qty",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Low Stock Qty"),
			"fieldname": "low_stock_qty",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Shortage Qty"),
			"fieldname": "shortage_qty",
			"fieldtype": "Float",
			"width": 110,
		},
	]


def get_data(filters):
	bin_dt = DocType("Bin")
	item_dt = DocType("Item")
	alert_dt = DocType("Item Low Stock Alert")

	# Start from the alert rows and LEFT JOIN Bin: an item that has never had
	# stock in a warehouse has no Bin row at all, and its stock is 0 -- an
	# INNER JOIN on Bin silently dropped exactly those (most urgent) rows.
	actual_qty = IfNull(bin_dt.actual_qty, 0)
	query = (
		frappe.qb.from_(alert_dt)
		.inner_join(item_dt).on(item_dt.name == alert_dt.parent)
		.left_join(bin_dt).on(
			(bin_dt.item_code == alert_dt.parent)
			& (bin_dt.warehouse == alert_dt.warehouse)
		)
		.select(
			alert_dt.warehouse,
			alert_dt.parent.as_("item_code"),
			item_dt.item_name,
			item_dt.item_group,
			IfNull(bin_dt.stock_uom, item_dt.stock_uom).as_("stock_uom"),
			actual_qty.as_("actual_qty"),
			alert_dt.low_stock_qty,
		)
		.where(alert_dt.parenttype == "Item")
		.where(alert_dt.low_stock_qty > 0)
		.where(actual_qty < alert_dt.low_stock_qty)
	)

	if filters.get("warehouse"):
		query = query.where(alert_dt.warehouse == filters.warehouse)

	if filters.get("item_group"):
		query = query.where(item_dt.item_group == filters.item_group)

	if filters.get("item_code"):
		query = query.where(alert_dt.parent == filters.item_code)

	result = query.run(as_dict=True)

	for row in result:
		row["shortage_qty"] = frappe.utils.flt(row["low_stock_qty"]) - frappe.utils.flt(row["actual_qty"])

	# Same item order as Low Stock and Stock Summary Report: BSP's official
	# item-category order (see item_category_sort.py), ties by item_name.
	# Warehouse is secondary, so one item's rows across warehouses sit together.
	sort_map = get_item_sort_map()
	wh_sort_map = get_warehouse_sort_map()
	result.sort(
		key=lambda row: (
			item_category_sort_key(sort_map, row['item_code']),
			row['item_name'] or '',
			warehouse_sort_key(wh_sort_map, row['warehouse']),
		)
	)

	return result
