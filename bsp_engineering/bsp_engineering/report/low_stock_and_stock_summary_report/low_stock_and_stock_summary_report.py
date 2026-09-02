# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Showroom-wise Low Stock & Stock Summary Report ("For Dalai Order").

Low Stock Alert Report already lists individual (item, warehouse) rows that
are currently below their configured threshold. This report instead shows
the full, at-a-glance picture per item -- for every warehouse that has a
Low Stock Qty configured on any item (or the warehouses explicitly picked in
the filter), a "Low Qty" / "Stock" column pair, plus a Total Low Qty and
Total Stock across those columns. It lists every item that has at least one
Item Low Stock Alert row configured (the same universe Low Stock Alert
Report draws from), not just the ones currently short -- the point is to see
every tracked item's status at a glance, with Total Stock flagged (in red,
client-side) whenever it has fallen below Total Low Qty, rather than
filtering rows out entirely.

NOTE: the Report doctype's own "Add Total Row" checkbox must stay OFF for
this report. When it's on, Frappe's report view assumes the *last* row
returned by execute() is a special grand-total row and silently splices it
out of the data before rendering -- since this report doesn't emit one in
that shape, that was corrupting the row/column alignment on every load.
"""

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	warehouses = get_warehouses(filters)
	columns = get_columns(warehouses)
	data = get_data(filters, warehouses)
	return columns, data


def get_warehouses(filters):
	"""Ordered list of {name, warehouse_name} dicts -- one per showroom column
	pair. Explicit `warehouse` filter (multi-select) picks the columns shown;
	otherwise every warehouse that has at least one Item Low Stock Alert row
	anywhere, so the report's column set doesn't jump around as item/item
	group filters change."""
	alert_dt = DocType("Item Low Stock Alert")
	wh_dt = DocType("Warehouse")

	query = (
		frappe.qb.from_(alert_dt)
		.inner_join(wh_dt)
		.on(wh_dt.name == alert_dt.warehouse)
		.select(wh_dt.name, wh_dt.warehouse_name)
		.where(alert_dt.parenttype == "Item")
		.distinct()
		.orderby(wh_dt.warehouse_name)
	)

	selected = filters.get("warehouse")
	if selected:
		if isinstance(selected, str):
			selected = frappe.parse_json(selected)
		if selected:
			query = query.where(wh_dt.name.isin(selected))

	return query.run(as_dict=True)


def get_columns(warehouses):
	columns = [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
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
	"""Items that have at least one Item Low Stock Alert row in one of the
	shown warehouses -- the same "tracked for low stock" universe Low Stock
	Alert Report itself draws from."""
	if not warehouse_names:
		return []

	alert_dt = DocType("Item Low Stock Alert")
	item_dt = DocType("Item")

	query = (
		frappe.qb.from_(alert_dt)
		.inner_join(item_dt)
		.on(item_dt.name == alert_dt.parent)
		.select(item_dt.name, item_dt.item_name)
		.distinct()
		.where(alert_dt.parenttype == "Item")
		.where(alert_dt.warehouse.isin(warehouse_names))
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
		row = {"item_code": item.name, "item_name": item.item_name}
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
	# formatter (low_stock_and_stock_summary_report.js) highlights with,
	# rather than just filtering visually. Applied last since it depends on
	# the totals just computed above.
	stock_status = filters.get("stock_status")
	if stock_status == "Low Stock":
		data = [row for row in data if flt(row["total_stock"]) < flt(row["total_low_qty"])]
	elif stock_status == "Sufficient Stock":
		data = [row for row in data if flt(row["total_stock"]) >= flt(row["total_low_qty"])]

	return data
