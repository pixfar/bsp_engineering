# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	currency_options = "Company:company:default_currency"

	return [
		{"label": _("S.L"), "fieldname": "sl", "fieldtype": "Int", "width": 50},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 140,
		},
		{
			"label": _("Stock UOM"),
			"fieldname": "stock_uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 90,
		},
		{
			"label": _("Current Stock Qty"),
			"fieldname": "current_stock_qty",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Current Stock Value"),
			"fieldname": "current_stock_value",
			"fieldtype": "Currency",
			"options": currency_options,
			"width": 140,
		},
		{"label": _("Opening Qty"), "fieldname": "opening_qty", "fieldtype": "Float", "width": 100},
		{
			"label": _("Opening Value"),
			"fieldname": "opening_value",
			"fieldtype": "Currency",
			"options": currency_options,
			"width": 120,
		},
		{"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 90},
		{
			"label": _("In Value"),
			"fieldname": "in_value",
			"fieldtype": "Currency",
			"options": currency_options,
			"width": 100,
		},
		{"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 90},
		{
			"label": _("Out Value"),
			"fieldname": "out_value",
			"fieldtype": "Currency",
			"options": currency_options,
			"width": 100,
		},
		{
			"label": _("Valuation Rate"),
			"fieldname": "valuation_rate",
			"fieldtype": "Currency",
			"options": currency_options,
			"width": 110,
		},
	]


def as_list(value):
	if not value:
		return []
	return value if isinstance(value, list) else [value]


def get_warehouse_names(filters):
	warehouse_filters = {"disabled": 0, "is_group": 0}
	if filters.get("company"):
		warehouse_filters["company"] = filters.company

	return frappe.get_all("Warehouse", filters=warehouse_filters, pluck="name")


def get_items(filters):
	item_filters = {"disabled": 0}

	item_groups = as_list(filters.get("item_group"))
	if item_groups:
		item_filters["item_group"] = ["in", item_groups]

	item_codes = as_list(filters.get("item_code"))
	if item_codes:
		item_filters["name"] = ["in", item_codes]

	return frappe.get_all(
		"Item",
		filters=item_filters,
		fields=["name as item_code", "item_name", "item_group", "stock_uom"],
		order_by="item_group asc, item_code asc",
	)


def get_opening_map(warehouse_names, item_codes, from_date):
	sle = frappe.qb.DocType("Stock Ledger Entry")

	rows = (
		frappe.qb.from_(sle)
		.select(
			sle.item_code,
			Sum(sle.actual_qty).as_("qty"),
			Sum(sle.stock_value_difference).as_("value"),
		)
		.where(sle.warehouse.isin(warehouse_names))
		.where(sle.item_code.isin(item_codes))
		.where(sle.docstatus < 2)
		.where(sle.is_cancelled == 0)
		.where(sle.posting_date < from_date)
		.groupby(sle.item_code)
		.run(as_dict=True)
	)

	return {row.item_code: row for row in rows}


def get_movement_map(warehouse_names, item_codes, from_date, to_date):
	sle = frappe.qb.DocType("Stock Ledger Entry")

	query = (
		frappe.qb.from_(sle)
		.select(sle.item_code, sle.actual_qty, sle.stock_value_difference)
		.where(sle.warehouse.isin(warehouse_names))
		.where(sle.item_code.isin(item_codes))
		.where(sle.docstatus < 2)
		.where(sle.is_cancelled == 0)
		.where(sle.posting_date <= to_date)
	)

	if from_date:
		query = query.where(sle.posting_date >= from_date)

	movement_map = {}
	for row in query.run(as_dict=True):
		entry = movement_map.setdefault(
			row.item_code, frappe._dict(in_qty=0.0, in_value=0.0, out_qty=0.0, out_value=0.0)
		)
		qty = flt(row.actual_qty)
		value = flt(row.stock_value_difference)

		if qty >= 0:
			entry.in_qty += qty
			entry.in_value += value
		else:
			entry.out_qty += abs(qty)
			entry.out_value += abs(value)

	return movement_map


def get_current_stock_map(warehouse_names, item_codes, to_date):
	if getdate(to_date) < getdate(nowdate()):
		return None

	bin_dt = frappe.qb.DocType("Bin")

	rows = (
		frappe.qb.from_(bin_dt)
		.select(
			bin_dt.item_code,
			Sum(bin_dt.actual_qty).as_("qty"),
			Sum(bin_dt.stock_value).as_("value"),
		)
		.where(bin_dt.warehouse.isin(warehouse_names))
		.where(bin_dt.item_code.isin(item_codes))
		.groupby(bin_dt.item_code)
		.run(as_dict=True)
	)

	return {row.item_code: row for row in rows}


def get_data(filters):
	from_date = getdate(filters.from_date) if filters.get("from_date") else None
	to_date = getdate(filters.get("to_date") or nowdate())

	items = get_items(filters)
	if not items:
		return []

	warehouse_names = get_warehouse_names(filters)
	if not warehouse_names:
		return []

	item_codes = [item.item_code for item in items]

	opening_map = get_opening_map(warehouse_names, item_codes, from_date) if from_date else {}
	movement_map = get_movement_map(warehouse_names, item_codes, from_date, to_date)
	current_map = get_current_stock_map(warehouse_names, item_codes, to_date)

	rows = []
	for item in items:
		opening = opening_map.get(item.item_code, frappe._dict())
		movement = movement_map.get(item.item_code, frappe._dict())
		current = current_map.get(item.item_code) if current_map is not None else None

		opening_qty = flt(opening.get("qty"))
		opening_value = flt(opening.get("value"))
		in_qty = flt(movement.get("in_qty"))
		in_value = flt(movement.get("in_value"))
		out_qty = flt(movement.get("out_qty"))
		out_value = flt(movement.get("out_value"))

		if current is not None:
			current_stock_qty = flt(current.get("qty"))
			current_stock_value = flt(current.get("value"))
		else:
			current_stock_qty = opening_qty + in_qty - out_qty
			current_stock_value = opening_value + in_value - out_value

		if not filters.get("include_zero_stock_items") and not any(
			[
				opening_qty,
				opening_value,
				in_qty,
				in_value,
				out_qty,
				out_value,
				current_stock_qty,
				current_stock_value,
			]
		):
			continue

		valuation_rate = current_stock_value / current_stock_qty if current_stock_qty else 0.0

		rows.append(
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"item_group": item.item_group,
				"stock_uom": item.stock_uom,
				"current_stock_qty": current_stock_qty,
				"current_stock_value": current_stock_value,
				"opening_qty": opening_qty,
				"opening_value": opening_value,
				"in_qty": in_qty,
				"in_value": in_value,
				"out_qty": out_qty,
				"out_value": out_value,
				"valuation_rate": valuation_rate,
			}
		)

	for idx, row in enumerate(rows, start=1):
		row["sl"] = idx

	return rows
