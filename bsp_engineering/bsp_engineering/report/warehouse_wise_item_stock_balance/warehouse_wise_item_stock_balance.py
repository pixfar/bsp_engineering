# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	warehouses = get_warehouses(filters)
	columns = get_columns(warehouses)
	data = get_data(filters, warehouses)
	return columns, data


def get_warehouses(filters):
	warehouse_filters = {"disabled": 0, "is_group": 0}

	if filters.get("company"):
		warehouse_filters["company"] = filters.company

	warehouses = frappe.get_all(
		"Warehouse",
		filters=warehouse_filters,
		fields=["name"],
		order_by="lft asc",
	)

	for idx, warehouse in enumerate(warehouses):
		warehouse["fieldname"] = f"warehouse_{idx}"

	return warehouses


def get_columns(warehouses):
	columns = [
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 140,
		},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 200,
		},
	]

	for warehouse in warehouses:
		columns.append(
			{
				"label": warehouse.name,
				"fieldname": warehouse.fieldname,
				"fieldtype": "Float",
				"width": 130,
			}
		)

	columns.append(
		{
			"label": _("Grand Total"),
			"fieldname": "grand_total",
			"fieldtype": "Float",
			"width": 130,
		}
	)

	return columns


def as_list(value):
	if not value:
		return []
	return value if isinstance(value, list) else [value]


def build_qty_map(rows):
	item_warehouse_qty = {}
	for row in rows:
		item_warehouse_qty.setdefault(row.item_code, {})[row.warehouse] = flt(row.actual_qty)
	return item_warehouse_qty


def get_current_stock_map(warehouse_names, item_codes):
	bin_dt = frappe.qb.DocType("Bin")

	query = (
		frappe.qb.from_(bin_dt)
		.select(bin_dt.item_code, bin_dt.warehouse, bin_dt.actual_qty)
		.where(bin_dt.warehouse.isin(warehouse_names))
	)

	if item_codes:
		query = query.where(bin_dt.item_code.isin(item_codes))

	return build_qty_map(query.run(as_dict=True))


def get_balance_as_on_date(filters, warehouse_names, item_codes, to_date):
	sle = frappe.qb.DocType("Stock Ledger Entry")

	query = (
		frappe.qb.from_(sle)
		.select(sle.item_code, sle.warehouse, Sum(sle.actual_qty).as_("actual_qty"))
		.where(sle.warehouse.isin(warehouse_names))
		.where(sle.docstatus < 2)
		.where(sle.is_cancelled == 0)
		.where(sle.posting_date <= to_date)
		.groupby(sle.item_code, sle.warehouse)
	)

	if filters.get("company"):
		query = query.where(sle.company == filters.company)

	if item_codes:
		query = query.where(sle.item_code.isin(item_codes))

	return build_qty_map(query.run(as_dict=True))


def get_item_warehouse_qty_map(filters, warehouse_names):
	to_date = getdate(filters.get("to_date") or nowdate())
	item_codes = as_list(filters.get("item_code"))

	if to_date >= getdate(nowdate()):
		return get_current_stock_map(warehouse_names, item_codes)

	return get_balance_as_on_date(filters, warehouse_names, item_codes, to_date)


def get_items_with_movement(filters, warehouse_names):
	"""Item codes with a Stock Ledger Entry within the selected date range, or None if no From Date is set."""
	if not filters.get("from_date"):
		return None

	sle = frappe.qb.DocType("Stock Ledger Entry")
	from_date = getdate(filters.from_date)
	to_date = getdate(filters.get("to_date") or nowdate())

	query = (
		frappe.qb.from_(sle)
		.select(sle.item_code)
		.distinct()
		.where(sle.warehouse.isin(warehouse_names))
		.where(sle.docstatus < 2)
		.where(sle.is_cancelled == 0)
		.where(sle.posting_date >= from_date)
		.where(sle.posting_date <= to_date)
	)

	if filters.get("company"):
		query = query.where(sle.company == filters.company)

	return {row.item_code for row in query.run(as_dict=True)}


def get_items(filters, item_codes_with_stock, items_with_movement):
	item_filters = {"disabled": 0}

	item_groups = as_list(filters.get("item_group"))
	if item_groups:
		item_filters["item_group"] = ["in", item_groups]

	item_code_filter = set(as_list(filters.get("item_code"))) or None

	if items_with_movement is not None:
		item_code_filter = (
			items_with_movement if item_code_filter is None else item_code_filter & items_with_movement
		)

	if not filters.get("include_zero_stock_items"):
		stock_set = set(item_codes_with_stock)
		item_code_filter = stock_set if item_code_filter is None else item_code_filter & stock_set

	if item_code_filter is not None:
		if not item_code_filter:
			return []
		item_filters["name"] = ["in", list(item_code_filter)]

	return frappe.get_all(
		"Item",
		filters=item_filters,
		fields=["name as item_code", "item_name", "item_group"],
		order_by="item_group asc, item_code asc",
	)


def get_data(filters, warehouses):
	warehouse_names = [warehouse.name for warehouse in warehouses]
	if not warehouse_names:
		return []

	item_warehouse_qty = get_item_warehouse_qty_map(filters, warehouse_names)
	items_with_movement = get_items_with_movement(filters, warehouse_names)
	items = get_items(filters, list(item_warehouse_qty.keys()), items_with_movement)

	data = []
	for item in items:
		row = {
			"item_group": item.item_group,
			"item_code": item.item_code,
			"item_name": item.item_name,
		}

		grand_total = 0.0
		qty_by_warehouse = item_warehouse_qty.get(item.item_code, {})

		for warehouse in warehouses:
			qty = qty_by_warehouse.get(warehouse.name, 0.0)
			row[warehouse.fieldname] = qty
			grand_total += qty

		if not filters.get("include_zero_stock_items") and grand_total == 0:
			continue

		row["grand_total"] = grand_total
		data.append(row)

	return data
