# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Production Report -- shortage vs. planned quantity from Production
Requirement, summarised by Item (default), Production Date, Warehouse or
Production Group."""

from collections import OrderedDict

import frappe
from frappe import _

from bsp_engineering.bsp_engineering.utils.production_requirement import (
	get_report_summary,
	get_requirement_item_rows,
)

GROUP_BY_FIELDS = {
	"Item": ("item_code",),
	"Production Date": ("production_date",),
	"Warehouse": ("warehouse",),
	"Production Group": ("production_group",),
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group_by = filters.group_by if filters.group_by in GROUP_BY_FIELDS else "Item"
	rows = get_requirement_item_rows(filters)
	data = summarise(rows, group_by)
	return get_columns(group_by), data, None, None, get_report_summary(rows)


def summarise(rows, group_by):
	key_fields = GROUP_BY_FIELDS[group_by]
	groups = OrderedDict()
	for row in rows:
		key = tuple(row.get(f) for f in key_fields)
		entry = groups.get(key)
		if entry is None:
			entry = groups[key] = frappe._dict(
				item_code=row.item_code,
				item_name=row.item_name,
				item_group=row.item_group,
				production_group=row.production_group,
				uom=row.uom,
				production_date=row.production_date,
				warehouse=row.warehouse,
				requirements=set(),
				shortage_qty=0.0,
				plan_qty=0.0,
				uncovered_qty=0.0,
			)
		entry.requirements.add(row.production_requirement)
		entry.shortage_qty += row.shortage_qty
		entry.plan_qty += row.plan_qty
		entry.uncovered_qty += row.uncovered_qty

	data = []
	for entry in groups.values():
		entry.no_of_requirements = len(entry.pop("requirements"))
		data.append(entry)

	if group_by == "Item":
		data.sort(key=lambda r: (r.item_group or "", r.item_name or r.item_code or ""))
	elif group_by == "Production Date":
		data.sort(key=lambda r: r.production_date, reverse=True)
	else:
		data.sort(key=lambda r: r.get(key_fields[0]) or "")
	return data


def get_columns(group_by):
	qty_columns = [
		{"label": _("No. of Requirements"), "fieldname": "no_of_requirements", "fieldtype": "Int", "width": 100},
		{"label": _("Shortage Qty"), "fieldname": "shortage_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Plan Qty"), "fieldname": "plan_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Uncovered Qty"), "fieldname": "uncovered_qty", "fieldtype": "Float", "width": 120},
	]

	if group_by == "Production Date":
		key_columns = [{"label": _("Production Date"), "fieldname": "production_date", "fieldtype": "Date", "width": 130}]
	elif group_by == "Warehouse":
		key_columns = [
			{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 220}
		]
	elif group_by == "Production Group":
		key_columns = [
			{
				"label": _("Production Group"),
				"fieldname": "production_group",
				"fieldtype": "Link",
				"options": "Production Group",
				"width": 200,
			}
		]
	else:
		key_columns = [
			{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
			{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 220},
			{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 130},
			{
				"label": _("Production Group"),
				"fieldname": "production_group",
				"fieldtype": "Link",
				"options": "Production Group",
				"width": 130,
			},
			{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 70},
		]
	return key_columns + qty_columns
