# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Shared helpers for Production Requirement:

- get_current_shortage: today's shortage per item from the Production
  Requirement Report, recorded on the document when an item is added.
- get_requirement_item_rows / get_report_summary: data source for the
  Production Plan Report and Production Report -- one row per Production
  Requirement Item, joined to its parent and Item, with the report filters
  and the same warehouse scoping as the doctype itself.
"""

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import flt, getdate

from posawesome.posawesome.utils.warehouse_doc_permissions import (
	get_expanded_permitted_warehouses,
)


def get_current_shortage(item_codes):
	"""{item_code: max(Total Low Qty - Total Stock, 0)} as the Production
	Requirement Report computes it right now."""
	from bsp_engineering.bsp_engineering.report.production_requirement_report.production_requirement_report import (
		execute,
	)

	item_codes = [code for code in item_codes or [] if code]
	if not item_codes:
		return {}
	_columns, data = execute({'item_code': item_codes})
	return {
		row['item_code']: max(flt(row.get('total_low_qty')) - flt(row.get('total_stock')), 0.0) for row in data
	}


def _as_list(value):
	if not value:
		return []
	if isinstance(value, str):
		value = value.strip()
		if value.startswith('['):
			return [v for v in frappe.parse_json(value) if v]
		return [value]
	return [v for v in value if v]


def get_requirement_item_rows(filters):
	filters = frappe._dict(filters or {})
	parent = DocType('Production Requirement')
	child = DocType('Production Requirement Item')
	item = DocType('Item')

	query = (
		frappe.qb.from_(child)
		.inner_join(parent)
		.on(parent.name == child.parent)
		.left_join(item)
		.on(item.name == child.item_code)
		.select(
			parent.name.as_('production_requirement'),
			parent.production_date,
			parent.posting_date,
			parent.warehouse,
			parent.production_by,
			child.item_code,
			child.item_name,
			child.uom,
			child.shortage_qty,
			child.plan_qty,
			item.item_group,
			item.custom_production_group.as_('production_group'),
		)
		.where(child.parenttype == 'Production Requirement')
		.where(parent.docstatus < 2)
		.orderby(parent.production_date, order=frappe.qb.desc)
		.orderby(parent.name, order=frappe.qb.desc)
		.orderby(child.idx)
	)

	if filters.from_date:
		query = query.where(parent.production_date >= getdate(filters.from_date))
	if filters.to_date:
		query = query.where(parent.production_date <= getdate(filters.to_date))
	if filters.production_by:
		query = query.where(parent.production_by == filters.production_by)

	warehouses = _as_list(filters.warehouse)
	if warehouses:
		query = query.where(parent.warehouse.isin(warehouses))

	permitted = get_expanded_permitted_warehouses()
	if permitted is not None:
		if not permitted:
			return []
		query = query.where(parent.warehouse.isin(permitted))

	item_codes = _as_list(filters.item_code)
	if item_codes:
		query = query.where(child.item_code.isin(item_codes))
	item_groups = _as_list(filters.item_group)
	if item_groups:
		query = query.where(item.item_group.isin(item_groups))
	production_groups = _as_list(filters.production_group)
	if production_groups:
		query = query.where(item.custom_production_group.isin(production_groups))

	rows = query.run(as_dict=True)
	for row in rows:
		row.shortage_qty = flt(row.shortage_qty)
		row.plan_qty = flt(row.plan_qty)
		# Shortage the plan leaves uncovered (planned less than was short).
		row.uncovered_qty = max(row.shortage_qty - row.plan_qty, 0.0)
	return rows


def get_report_summary(rows):
	shortage = sum(r.shortage_qty for r in rows)
	plan = sum(r.plan_qty for r in rows)
	uncovered = sum(r.uncovered_qty for r in rows)
	return [
		{'value': shortage, 'label': _('Total Shortage Qty'), 'datatype': 'Float', 'indicator': 'Red' if shortage else 'Green'},
		{'value': plan, 'label': _('Total Plan Qty'), 'datatype': 'Float', 'indicator': 'Blue'},
		{
			'value': uncovered,
			'label': _('Uncovered Shortage'),
			'datatype': 'Float',
			'indicator': 'Red' if uncovered else 'Green',
		},
	]
