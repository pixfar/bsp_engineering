# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Production Plan Report -- every planned line from Production Requirement,
one row per item per document: the shortage recorded when it was planned,
the Plan Qty set against it, and any shortage the plan leaves uncovered."""

from frappe import _

from bsp_engineering.bsp_engineering.utils.production_requirement import (
	get_report_summary,
	get_requirement_item_rows,
)


def execute(filters=None):
	rows = get_requirement_item_rows(filters)
	return get_columns(), rows, None, None, get_report_summary(rows)


def get_columns():
	return [
		{"label": _("Production Date"), "fieldname": "production_date", "fieldtype": "Date", "width": 110},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 105},
		{
			"label": _("Production Requirement"),
			"fieldname": "production_requirement",
			"fieldtype": "Link",
			"options": "Production Requirement",
			"width": 160,
		},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 170},
		{"label": _("Production By"), "fieldname": "production_by", "fieldtype": "Link", "options": "User", "width": 150},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 120},
		{
			"label": _("Production Group"),
			"fieldname": "production_group",
			"fieldtype": "Link",
			"options": "Production Group",
			"width": 120,
		},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 70},
		{"label": _("Shortage Qty"), "fieldname": "shortage_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Plan Qty"), "fieldname": "plan_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Uncovered Qty"), "fieldname": "uncovered_qty", "fieldtype": "Float", "width": 115},
	]
