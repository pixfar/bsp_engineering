# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Production Requirement Report -- a fixed-warehouse copy of Low Stock and
Stock Summary Report ("For Dalai Order"). Same Low Qty/Stock/Total columns
and same red "needs a Dalai order" flag, but instead of a warehouse picker
it always shows exactly these three warehouses, in this fixed order, since
this report exists specifically to look at production-feeder stock:

    Noakhali Karkhana - BSP, Konapara Service Center - BSP, Store Room - BSP

See low_stock_and_stock_summary_report.py for the full column/data shape
this mirrors.

NOTE: the Report doctype's own "Add Total Row" checkbox must stay OFF for
this report, for the same reason as the report it's copied from -- see that
file's note.
"""

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import flt

from bsp_engineering.utils.item_category_sort import get_item_sort_map, sort_rows_by_item_category

# Fixed, in display order -- not user-selectable, unlike the report this is
# copied from.
FIXED_WAREHOUSES = [
	"Noakhali Karkhana - BSP",
	"Konapara Service Center - BSP",
	"Store Room - BSP",
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	warehouses = get_warehouses()
	columns = get_columns(warehouses)
	data = get_data(filters, warehouses)
	return columns, data


def get_warehouses():
	"""The fixed three warehouses, in FIXED_WAREHOUSES order -- looked up
	rather than hardcoding warehouse_name too, so a Warehouse rename is
	picked up automatically. A warehouse that's been deleted/renamed out
	from under FIXED_WAREHOUSES is silently skipped rather than erroring,
	so the report still renders with whichever of the three still exist."""
	wh_dt = DocType("Warehouse")
	rows = (
		frappe.qb.from_(wh_dt)
		.select(wh_dt.name, wh_dt.warehouse_name)
		.where(wh_dt.name.isin(FIXED_WAREHOUSES))
		.run(as_dict=True)
	)
	by_name = {row.name: row for row in rows}
	return [by_name[name] for name in FIXED_WAREHOUSES if name in by_name]


def get_columns(warehouses):
	columns = [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 130,
		},
	]

	for idx, wh in enumerate(warehouses):
		label = wh.warehouse_name or wh.name
		columns.append(
			{
				"label": _("{0} Low Qty").format(label),
				"fieldname": f"wh_{idx}_low_qty",
				"fieldtype": "Float",
				"width": 130,
			}
		)
		columns.append(
			{
				"label": _("{0} Stock").format(label),
				"fieldname": f"wh_{idx}_stock",
				"fieldtype": "Float",
				"width": 130,
			}
		)

	columns.append(
		{"label": _("Total Low Quantity"), "fieldname": "total_low_qty", "fieldtype": "Float", "width": 130}
	)
	columns.append({"label": _("Total Stock"), "fieldname": "total_stock", "fieldtype": "Float", "width": 130})
	return columns


def get_items(filters, warehouse_names):
	"""Every item in the system (subject only to the Item Group/Item/
	Production Group filters below) -- not just ones with a configured Item
	Low Stock Alert row. Previously scoped to that alert-configured universe
	(226 of 1094 items) the same way Low Stock Alert Report itself draws
	from; reported live as "not getting all the item reports" and changed
	by explicit request to show every item, no exceptions -- an item with
	no alert configured for these three warehouses just shows a real Stock
	figure from Bin (see get_data below) alongside a Low Qty of 0, rather
	than being left out of the report entirely."""
	if not warehouse_names:
		return []

	item_dt = DocType("Item")

	query = (
		frappe.qb.from_(item_dt)
		.select(item_dt.name, item_dt.item_name, item_dt.item_group)
		.orderby(item_dt.item_name)
	)

	item_groups = filters.get("item_group")
	if item_groups:
		if isinstance(item_groups, str):
			item_groups = frappe.parse_json(item_groups)
		if item_groups:
			query = query.where(item_dt.item_group.isin(item_groups))

	item_codes = filters.get("item_code")
	if item_codes:
		if isinstance(item_codes, str):
			item_codes = frappe.parse_json(item_codes)
		if item_codes:
			query = query.where(item_dt.name.isin(item_codes))

	production_groups = filters.get("production_group")
	if production_groups:
		if isinstance(production_groups, str):
			production_groups = frappe.parse_json(production_groups)
		if production_groups:
			query = query.where(item_dt.custom_production_group.isin(production_groups))

	return query.run(as_dict=True)


def get_data(filters, warehouses):
	warehouse_names = [wh.name for wh in warehouses]
	items = get_items(filters, warehouse_names)
	if not items:
		return []

	item_codes = [item.name for item in items]

	alert_dt = DocType("Item Low Stock Alert")
	low_qty_by_item_wh = {}
	for row in (
		frappe.qb.from_(alert_dt)
		.select(alert_dt.parent, alert_dt.warehouse, alert_dt.low_stock_qty)
		.where(alert_dt.parenttype == "Item")
		.where(alert_dt.parent.isin(item_codes))
		.where(alert_dt.warehouse.isin(warehouse_names))
		.run(as_dict=True)
	):
		low_qty_by_item_wh[(row.parent, row.warehouse)] = flt(row.low_stock_qty)

	bin_dt = DocType("Bin")
	stock_by_item_wh = {}
	for row in (
		frappe.qb.from_(bin_dt)
		.select(bin_dt.item_code, bin_dt.warehouse, bin_dt.actual_qty)
		.where(bin_dt.item_code.isin(item_codes))
		.where(bin_dt.warehouse.isin(warehouse_names))
		.run(as_dict=True)
	):
		stock_by_item_wh[(row.item_code, row.warehouse)] = flt(row.actual_qty)

	data = []
	for item in items:
		row = {"item_code": item.name, "item_name": item.item_name, "item_group": item.item_group}
		total_low_qty = 0.0
		total_stock = 0.0
		for wh_idx, wh in enumerate(warehouses):
			low_qty = low_qty_by_item_wh.get((item.name, wh.name), 0.0)
			stock = stock_by_item_wh.get((item.name, wh.name), 0.0)
			row[f"wh_{wh_idx}_low_qty"] = low_qty
			row[f"wh_{wh_idx}_stock"] = stock
			total_low_qty += low_qty
			total_stock += stock
		row["total_low_qty"] = total_low_qty
		row["total_stock"] = total_stock
		data.append(row)

	# "Filter using color" -- restrict to the same red/not-red split the
	# formatter (production_requirement_report.js) highlights with, rather
	# than just filtering visually. Applied last since it depends on the
	# totals just computed above.
	stock_status = filters.get("stock_status")
	if stock_status == "Low Stock":
		data = [row for row in data if flt(row["total_stock"]) < flt(row["total_low_qty"])]
	elif stock_status == "Sufficient Stock":
		data = [row for row in data if flt(row["total_stock"]) >= flt(row["total_low_qty"])]

	# BSP's official item-category order (see item_category_sort.py), replacing
	# the item_name ordering get_items() queried in.
	data = sort_rows_by_item_category(data, get_item_sort_map())
	return data
