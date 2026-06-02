# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import DocType
from pypika import Order


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

	query = (
		frappe.qb.from_(bin_dt)
		.inner_join(item_dt).on(item_dt.name == bin_dt.item_code)
		.inner_join(alert_dt).on(
			(alert_dt.parent == bin_dt.item_code)
			& (alert_dt.parenttype == "Item")
			& (alert_dt.warehouse == bin_dt.warehouse)
		)
		.select(
			bin_dt.warehouse,
			bin_dt.item_code,
			item_dt.item_name,
			item_dt.item_group,
			bin_dt.stock_uom,
			bin_dt.actual_qty,
			alert_dt.low_stock_qty,
		)
		.where(alert_dt.low_stock_qty > 0)
		.where(bin_dt.actual_qty < alert_dt.low_stock_qty)
		.orderby(bin_dt.warehouse, order=Order.asc)
		.orderby(bin_dt.item_code, order=Order.asc)
	)

	if filters.get("warehouse"):
		query = query.where(bin_dt.warehouse == filters.warehouse)

	if filters.get("item_group"):
		query = query.where(item_dt.item_group == filters.item_group)

	if filters.get("item_code"):
		query = query.where(bin_dt.item_code == filters.item_code)

	result = query.run(as_dict=True)

	for row in result:
		row["shortage_qty"] = frappe.utils.flt(row["low_stock_qty"]) - frappe.utils.flt(row["actual_qty"])

	return result
