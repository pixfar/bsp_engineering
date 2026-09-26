# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Expense Report -- Expense Claims line by line (one row per Expense Claim
Detail), or totalled by Expense Type / Employee / Warehouse / Department /
Expense Date.

Warehouse is the claim's custom_warehouse (set by POS Awesome's expense
screen). System Manager, BSP Admin and BSP Viewer see every warehouse;
everyone else only their permitted warehouse(s), the same scoping as the
rest of POS Awesome.

Cancelled claims are left out unless the Status filter asks for them.
"""

from collections import OrderedDict

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import flt, getdate, strip_html

from posawesome.posawesome.utils.warehouse_doc_permissions import get_expanded_permitted_warehouses

GROUP_BY = {
	"Expense Type": "expense_type",
	"Employee": "employee",
	"Warehouse": "warehouse",
	"Department": "department",
	"Date": "expense_date",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = get_rows(filters)
	group_by = filters.group_by if filters.group_by in GROUP_BY else None

	if group_by:
		columns, data = get_group_columns(group_by), summarise(rows, group_by)
	else:
		columns, data = get_detail_columns(), rows
	return columns, data, None, get_chart(rows), get_summary(rows)


def _as_list(value):
	if not value:
		return []
	if isinstance(value, str):
		value = value.strip()
		return [v for v in frappe.parse_json(value) if v] if value.startswith("[") else [value]
	return [v for v in value if v]


def get_rows(filters):
	claim = DocType("Expense Claim")
	detail = DocType("Expense Claim Detail")
	warehouse = DocType("Warehouse")

	query = (
		frappe.qb.from_(detail)
		.inner_join(claim)
		.on(claim.name == detail.parent)
		.left_join(warehouse)
		.on(warehouse.name == claim.custom_warehouse)
		.select(
			claim.name.as_("expense_claim"),
			claim.posting_date,
			detail.expense_date,
			claim.status,
			claim.approval_status,
			claim.employee,
			claim.employee_name,
			claim.department,
			claim.custom_warehouse.as_("warehouse"),
			warehouse.warehouse_name,
			detail.expense_type,
			detail.description,
			detail.amount.as_("claimed_amount"),
			claim.remark,
		)
		.where(detail.parenttype == "Expense Claim")
		.orderby(claim.posting_date, order=frappe.qb.desc)
		.orderby(claim.name, order=frappe.qb.desc)
		.orderby(detail.idx)
	)

	if filters.from_date:
		query = query.where(claim.posting_date >= getdate(filters.from_date))
	if filters.to_date:
		query = query.where(claim.posting_date <= getdate(filters.to_date))
	if filters.company:
		query = query.where(claim.company == filters.company)
	if filters.employee:
		query = query.where(claim.employee == filters.employee)
	if filters.department:
		query = query.where(claim.department == filters.department)
	if filters.approval_status:
		query = query.where(claim.approval_status == filters.approval_status)
	if filters.status:
		query = query.where(claim.status == filters.status)
	else:
		query = query.where(claim.docstatus < 2)

	warehouses = _as_list(filters.warehouse)
	if warehouses:
		query = query.where(claim.custom_warehouse.isin(warehouses))
	expense_types = _as_list(filters.expense_type)
	if expense_types:
		query = query.where(detail.expense_type.isin(expense_types))

	permitted = get_expanded_permitted_warehouses()
	if permitted is not None:
		if not permitted:
			return []
		query = query.where(claim.custom_warehouse.isin(permitted))

	rows = query.run(as_dict=True)
	for row in rows:
		row.description = strip_html(row.description or "").strip()
		row.claimed_amount = flt(row.claimed_amount)
	return rows


def summarise(rows, group_by):
	key = GROUP_BY[group_by]
	groups = OrderedDict()
	for row in rows:
		entry = groups.get(row.get(key))
		if entry is None:
			entry = groups[row.get(key)] = frappe._dict(
				expense_type=row.expense_type,
				employee=row.employee,
				employee_name=row.employee_name,
				warehouse=row.warehouse,
				warehouse_name=row.warehouse_name,
				department=row.department,
				expense_date=row.expense_date,
				claims=set(),
				no_of_lines=0,
				claimed_amount=0.0,
			)
		entry.claims.add(row.expense_claim)
		entry.no_of_lines += 1
		entry.claimed_amount += row.claimed_amount

	data = []
	for entry in groups.values():
		entry.no_of_claims = len(entry.pop("claims"))
		data.append(entry)
	if group_by == "Date":
		data.sort(key=lambda r: r.expense_date, reverse=True)
	else:
		data.sort(key=lambda r: r.claimed_amount, reverse=True)
	return data


def _currency(label, fieldname, width=130):
	return {"label": _(label), "fieldname": fieldname, "fieldtype": "Currency", "width": width}


def get_detail_columns():
	return [
		{"label": _("Expense Date"), "fieldname": "expense_date", "fieldtype": "Date", "width": 110},
		{
			"label": _("Expense Claim"),
			"fieldname": "expense_claim",
			"fieldtype": "Link",
			"options": "Expense Claim",
			"width": 160,
		},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 200},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 190},
		{
			"label": _("Expense Type"),
			"fieldname": "expense_type",
			"fieldtype": "Link",
			"options": "Expense Claim Type",
			"width": 170,
		},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 240},
		_currency("Claimed Amount", "claimed_amount", 150),
	]


def get_group_columns(group_by):
	key_columns = {
		"Expense Type": [
			{
				"label": _("Expense Type"),
				"fieldname": "expense_type",
				"fieldtype": "Link",
				"options": "Expense Claim Type",
				"width": 200,
			}
		],
		"Employee": [{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 220}],
		"Warehouse": [
			{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 220}
		],
		"Department": [
			{"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 200}
		],
		"Date": [{"label": _("Expense Date"), "fieldname": "expense_date", "fieldtype": "Date", "width": 120}],
	}[group_by]
	return key_columns + [
		{"label": _("No. of Claims"), "fieldname": "no_of_claims", "fieldtype": "Int", "width": 110},
		{"label": _("No. of Lines"), "fieldname": "no_of_lines", "fieldtype": "Int", "width": 100},
		_currency("Claimed Amount", "claimed_amount", 160),
	]


def get_summary(rows):
	claimed = sum(r.claimed_amount for r in rows)
	return [
		{"value": len({r.expense_claim for r in rows}), "label": _("Expense Claims"), "datatype": "Int", "indicator": "Blue"},
		{"value": claimed, "label": _("Total Claimed"), "datatype": "Currency", "indicator": "Orange"},
		{
			"value": len({r.employee for r in rows}),
			"label": _("Employees"),
			"datatype": "Int",
			"indicator": "Blue",
		},
	]


def get_chart(rows):
	"""Top 10 expense types by claimed amount."""
	totals = {}
	for row in rows:
		totals[row.expense_type] = totals.get(row.expense_type, 0.0) + row.claimed_amount
	top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:10]
	if not top:
		return None
	return {
		"data": {
			"labels": [label or _("Not Set") for label, _value in top],
			"datasets": [{"name": _("Claimed Amount"), "values": [value for _label, value in top]}],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"colors": ["#5e64ff"],
	}
