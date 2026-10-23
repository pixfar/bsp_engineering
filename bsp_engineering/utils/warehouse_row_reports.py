# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Warehouse-as-row BSP reports: status counts, sales by Report Group,
management summary, and top selling by warehouse."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Coalesce, Count, Sum
from frappe.utils import flt, getdate

from bsp_engineering.utils.item_warehouse_matrix import (
	date_range,
	get_matrix_warehouses,
	hide_zero_flags,
	parse_list,
)
from bsp_engineering.utils.report_permissions import check_warehouse_filter

DEFAULT_REPORT_GROUPS = (
	'BSP Production',
	'Outsource Item',
	'RFL',
	'N. Poly',
)

REQUISITION_STATUSES = ('Draft', 'Sent', 'Seen', 'Completed', 'Rejected')
TRANSFER_STATUSES = ('In Transit', 'Fully Received', 'Partially Received', 'Rejected')
# Same workflow states as /app/posapp/production-plans/list.
PRODUCTION_PROGRESS_STATUSES = (
	'Draft',
	'Work In Progress',
	'Production Complete',
	'Cancelled',
)


def ensure_default_report_groups():
	for name in DEFAULT_REPORT_GROUPS:
		if not frappe.db.exists('Report Group', name):
			doc = frappe.get_doc({'doctype': 'Report Group', 'report_group_name': name})
			doc.insert(ignore_permissions=True)


def _status_fieldnames(statuses):
	return {status: frappe.scrub(status) for status in statuses}


def _warehouse_label_columns():
	return [
		{
			'label': _('Warehouse Name'),
			'fieldname': 'warehouse_name',
			'fieldtype': 'Data',
			'width': 220,
		}
	]


def _status_columns(statuses, fieldnames):
	return [
		{'label': _(status), 'fieldname': fieldnames[status], 'fieldtype': 'Int', 'width': 130}
		for status in statuses
	]


def _blank_status_row(warehouse, statuses, fieldnames):
	row = {
		'warehouse': warehouse.name,
		'warehouse_name': warehouse.warehouse_name or warehouse.name,
	}
	for status in statuses:
		row[fieldnames[status]] = 0
	return row


def _omit_zero_status_columns(columns, data, statuses, fieldnames):
	active = {
		fieldnames[status]
		for status in statuses
		if any(flt(row.get(fieldnames[status])) for row in data)
	}
	return [
		column
		for column in columns
		if column['fieldname'] == 'warehouse_name' or column['fieldname'] in active
	]


def _count_by_warehouse_status(rows, warehouses, statuses, fieldnames, warehouse_key='warehouse'):
	by_wh = {warehouse.name: _blank_status_row(warehouse, statuses, fieldnames) for warehouse in warehouses}
	for row in rows:
		bucket = by_wh.get(row.get(warehouse_key))
		if not bucket:
			continue
		status = row.get('status')
		if status in fieldnames:
			bucket[fieldnames[status]] += flt(row.get('count') or 0)
	return [by_wh[warehouse.name] for warehouse in warehouses]


def requisition_summary(filters=None):
	filters = frappe._dict(filters or {})
	hide_cols, hide_rows = hide_zero_flags(filters)
	warehouses = get_matrix_warehouses(filters)
	fieldnames = _status_fieldnames(REQUISITION_STATUSES)
	columns = _warehouse_label_columns() + _status_columns(REQUISITION_STATUSES, fieldnames)
	if not warehouses:
		return columns, []

	from_date, to_date = date_range(filters)
	req = DocType('Requisition')
	query = (
		frappe.qb.from_(req)
		.select(req.target_warehouse.as_('warehouse'), req.transfer_status.as_('status'), Count('*').as_('count'))
		.where(req.docstatus != 2)
		.where(req.transaction_date >= from_date)
		.where(req.transaction_date <= to_date)
		.where(req.target_warehouse.isin([warehouse.name for warehouse in warehouses]))
		.groupby(req.target_warehouse, req.transfer_status)
	)
	data = _count_by_warehouse_status(query.run(as_dict=True), warehouses, REQUISITION_STATUSES, fieldnames)
	if hide_rows:
		data = [
			row
			for row in data
			if any(flt(row.get(fieldnames[status])) for status in REQUISITION_STATUSES)
		]
	if hide_cols:
		columns = _omit_zero_status_columns(columns, data, REQUISITION_STATUSES, fieldnames)
	return columns, data


def transfer_summary(filters=None):
	filters = frappe._dict(filters or {})
	hide_cols, hide_rows = hide_zero_flags(filters)
	warehouses = get_matrix_warehouses(filters)
	fieldnames = _status_fieldnames(TRANSFER_STATUSES)
	columns = _warehouse_label_columns() + _status_columns(TRANSFER_STATUSES, fieldnames)
	if not warehouses:
		return columns, []

	from_date, to_date = date_range(filters)
	transfer = DocType('Material Transfer')
	query = (
		frappe.qb.from_(transfer)
		.select(
			transfer.to_warehouse.as_('warehouse'),
			transfer.transfer_status.as_('status'),
			Count('*').as_('count'),
		)
		.where(transfer.docstatus == 1)
		.where(transfer.transaction_date >= from_date)
		.where(transfer.transaction_date <= to_date)
		.where(transfer.to_warehouse.isin([warehouse.name for warehouse in warehouses]))
		.groupby(transfer.to_warehouse, transfer.transfer_status)
	)
	data = _count_by_warehouse_status(query.run(as_dict=True), warehouses, TRANSFER_STATUSES, fieldnames)
	if hide_rows:
		data = [
			row
			for row in data
			if any(flt(row.get(fieldnames[status])) for status in TRANSFER_STATUSES)
		]
	if hide_cols:
		columns = _omit_zero_status_columns(columns, data, TRANSFER_STATUSES, fieldnames)
	return columns, data


def production_progress(filters=None):
	"""Count Production Plans per source warehouse (for_warehouse), using the
	same workflow states as the POS production-plans list. Dates are optional
	(like the list): leave them blank to match the list cards exactly."""
	filters = frappe._dict(filters or {})
	warehouses = get_matrix_warehouses(filters)
	fieldnames = _status_fieldnames(PRODUCTION_PROGRESS_STATUSES)
	columns = _warehouse_label_columns() + _status_columns(PRODUCTION_PROGRESS_STATUSES, fieldnames)
	if not warehouses:
		return columns, []

	plan = DocType('Production Plan')
	query = (
		frappe.qb.from_(plan)
		.select(plan.for_warehouse.as_('warehouse'), plan.workflow_state.as_('status'), Count('*').as_('count'))
		.where(plan.for_warehouse.isin([warehouse.name for warehouse in warehouses]))
		.where(plan.workflow_state.isin(list(PRODUCTION_PROGRESS_STATUSES)))
		.groupby(plan.for_warehouse, plan.workflow_state)
	)
	# Same as /app/posapp/production-plans/list: only filter when dates are set.
	if filters.get('from_date'):
		query = query.where(plan.posting_date >= getdate(filters.from_date))
	if filters.get('to_date'):
		query = query.where(plan.posting_date <= getdate(filters.to_date))
	if filters.get('from_date') and filters.get('to_date'):
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw(_('From Date cannot be after To Date'))
	if filters.get('company'):
		query = query.where(plan.company == filters.company)

	data = _count_by_warehouse_status(
		query.run(as_dict=True), warehouses, PRODUCTION_PROGRESS_STATUSES, fieldnames
	)
	_hide_cols, hide_rows = hide_zero_flags(filters)
	if hide_rows:
		data = [
			row
			for row in data
			if any(flt(row.get(fieldnames[status])) for status in PRODUCTION_PROGRESS_STATUSES)
		]
	return columns, data


def sales_value_by_report_group(filters=None):
	"""One warehouse row; columns are Item.custom_report_group values."""
	filters = frappe._dict(filters or {})
	ensure_default_report_groups()
	warehouses = get_matrix_warehouses(filters)
	groups = _report_groups()
	fieldnames = {group: frappe.scrub(group) or f'group_{idx}' for idx, group in enumerate(groups)}
	columns = _warehouse_label_columns() + [
		{'label': group, 'fieldname': fieldnames[group], 'fieldtype': 'Currency', 'width': 140}
		for group in groups
	]
	if not warehouses:
		return columns, []

	from_date, to_date = date_range(filters)
	invoice = DocType('Sales Invoice')
	line = DocType('Sales Invoice Item')
	item = DocType('Item')
	query = (
		frappe.qb.from_(line)
		.inner_join(invoice)
		.on(invoice.name == line.parent)
		.inner_join(item)
		.on(item.name == line.item_code)
		.select(
			line.warehouse,
			Coalesce(item.custom_report_group, 'Not Set').as_('report_group'),
			Sum(Coalesce(line.base_net_amount, 0)).as_('amount'),
		)
		.where(invoice.docstatus == 1)
		.where(invoice.is_return == 0)
		.where(line.parenttype == 'Sales Invoice')
		.where(invoice.posting_date >= from_date)
		.where(invoice.posting_date <= to_date)
		.where(line.warehouse.isin([warehouse.name for warehouse in warehouses]))
		.groupby(line.warehouse, item.custom_report_group)
	)
	if filters.get('company'):
		query = query.where(invoice.company == filters.company)
	if filters.get('customer'):
		query = query.where(invoice.customer == filters.customer)
	item_groups = parse_list(filters.get('item_group'))
	if item_groups:
		query = query.where(item.item_group.isin(item_groups))
	report_groups = parse_list(filters.get('report_group'))
	if report_groups:
		query = query.where(item.custom_report_group.isin(report_groups))

	by_wh = {
		warehouse.name: {
			'warehouse': warehouse.name,
			'warehouse_name': warehouse.warehouse_name or warehouse.name,
			**{fieldnames[group]: 0.0 for group in groups},
		}
		for warehouse in warehouses
	}
	for row in query.run(as_dict=True):
		bucket = by_wh.get(row.warehouse)
		field = fieldnames.get(row.report_group)
		if bucket is not None and field:
			bucket[field] = flt(bucket[field]) + flt(row.amount)

	data = [by_wh[warehouse.name] for warehouse in warehouses]
	hide_cols, hide_rows = hide_zero_flags(filters)
	if hide_rows:
		data = [
			row
			for row in data
			if any(flt(row.get(field)) for field in fieldnames.values())
		]
	if hide_cols:
		active = {field for field in fieldnames.values() if any(flt(row.get(field)) for row in data)}
		columns = [
			column
			for column in columns
			if column['fieldname'] == 'warehouse_name' or column['fieldname'] in active
		]
	return columns, data


def _report_groups():
	names = frappe.get_all('Report Group', pluck='name', order_by='name')
	ordered = [name for name in DEFAULT_REPORT_GROUPS if name in names]
	ordered.extend(name for name in names if name not in ordered)
	if 'Not Set' not in ordered:
		ordered.append('Not Set')
	return ordered


def top_selling_by_warehouse(filters=None):
	filters = frappe._dict(filters or {})
	_hide_cols, hide_rows = hide_zero_flags(filters)
	warehouses = get_matrix_warehouses(filters)
	columns = _warehouse_label_columns() + [
		{'label': _('Grand Total Qty'), 'fieldname': 'quantity', 'fieldtype': 'Float', 'width': 120},
		{'label': _('Grand Total Value'), 'fieldname': 'value', 'fieldtype': 'Currency', 'width': 140},
	]
	if not warehouses:
		return columns, []

	from_date, to_date = date_range(filters)
	invoice = DocType('Sales Invoice')
	line = DocType('Sales Invoice Item')
	query = (
		frappe.qb.from_(line)
		.inner_join(invoice)
		.on(invoice.name == line.parent)
		.select(
			line.warehouse,
			Sum(Coalesce(line.stock_qty, line.qty, 0)).as_('quantity'),
			Sum(Coalesce(line.base_net_amount, 0)).as_('value'),
		)
		.where(invoice.docstatus == 1)
		.where(invoice.is_return == 0)
		.where(line.parenttype == 'Sales Invoice')
		.where(invoice.posting_date >= from_date)
		.where(invoice.posting_date <= to_date)
		.where(line.warehouse.isin([warehouse.name for warehouse in warehouses]))
		.groupby(line.warehouse)
	)
	if filters.get('company'):
		query = query.where(invoice.company == filters.company)

	totals = {row.warehouse: row for row in query.run(as_dict=True)}
	data = []
	for warehouse in warehouses:
		row = totals.get(warehouse.name)
		quantity = flt(row.quantity) if row else 0.0
		value = flt(row.value) if row else 0.0
		if hide_rows and not quantity and not value:
			continue
		data.append(
			{
				'warehouse': warehouse.name,
				'warehouse_name': warehouse.warehouse_name or warehouse.name,
				'quantity': quantity,
				'value': value,
			}
		)
	data.sort(key=lambda entry: (-flt(entry['value']), entry['warehouse_name']))
	return columns, data


def management_summary(filters=None):
	"""Warehouse management P&L-style row: cash, sales, purchase, stock, dues."""
	filters = frappe._dict(filters or {})
	if not filters.get('company'):
		frappe.throw(_('Please select a Company.'))
	from_date, to_date = date_range(filters)
	check_warehouse_filter(filters.get('warehouse'))

	from bsp_engineering.bsp_engineering.report.daily_cash_summary_report.daily_cash_summary_report import (
		get_expense_claims,
		get_opening_balances,
		get_purchase_invoices,
		get_sales_invoices,
	)
	from bsp_engineering.bsp_engineering.report.warehouse_wise_daily_cash_summary_report.warehouse_wise_daily_cash_summary_report import (
		get_data as get_cash_summary_data,
	)

	warehouses = get_matrix_warehouses(filters)
	columns = [
		{'label': _('Warehouse Name'), 'fieldname': 'warehouse_name', 'fieldtype': 'Data', 'width': 200},
		{'label': _('Opening Balance'), 'fieldname': 'opening_balance', 'fieldtype': 'Currency', 'width': 130},
		{'label': _('Total Sales'), 'fieldname': 'total_sales', 'fieldtype': 'Currency', 'width': 130},
		{'label': _('Total Purchase'), 'fieldname': 'total_purchase', 'fieldtype': 'Currency', 'width': 130},
		{'label': _('Gross Profit'), 'fieldname': 'gross_profit', 'fieldtype': 'Currency', 'width': 130},
		{'label': _('Total Expense'), 'fieldname': 'total_expense', 'fieldtype': 'Currency', 'width': 130},
		{'label': _('Net Profit'), 'fieldname': 'net_profit', 'fieldtype': 'Currency', 'width': 130},
		{'label': _('Customer Due'), 'fieldname': 'customer_due', 'fieldtype': 'Currency', 'width': 130},
		{'label': _('Supplier Payable'), 'fieldname': 'supplier_payable', 'fieldtype': 'Currency', 'width': 130},
		{'label': _('Current Stock Value'), 'fieldname': 'current_stock_value', 'fieldtype': 'Currency', 'width': 150},
		{'label': _('Closing Balance'), 'fieldname': 'closing_balance', 'fieldtype': 'Currency', 'width': 130},
	]
	if not warehouses:
		return columns, []

	company = filters.company
	allowed = {warehouse.name for warehouse in warehouses}
	warehouse_filter = None
	selected = parse_list(filters.get('warehouse'))
	if len(selected) == 1:
		warehouse_filter = selected[0]

	sales = get_sales_invoices(company, warehouse_filter, from_date, to_date)
	purchases = get_purchase_invoices(company, warehouse_filter, from_date, to_date)
	expenses = get_expense_claims(company, warehouse_filter, from_date, to_date)
	openings = get_opening_balances(company, warehouse_filter, from_date)
	cash_by_name = {
		row['warehouse_name']: row for row in get_cash_summary_data(filters, from_date, to_date)
	}
	stock_values = _stock_values([warehouse.name for warehouse in warehouses])
	customer_due = _outstanding_by_warehouse('Sales Invoice', warehouses, company, to_date)
	supplier_payable = _outstanding_by_warehouse('Purchase Invoice', warehouses, company, to_date)

	totals = defaultdict(lambda: {'total_sales': 0.0, 'total_purchase': 0.0, 'total_expense': 0.0})
	for inv in sales:
		if inv.warehouse in allowed:
			totals[inv.warehouse]['total_sales'] += flt(inv.grand_total) + flt(inv.discount_amount)
	for inv in purchases:
		if inv.warehouse in allowed:
			totals[inv.warehouse]['total_purchase'] += flt(inv.grand_total) + flt(inv.discount_amount)
	for claim in expenses:
		if claim.warehouse in allowed:
			totals[claim.warehouse]['total_expense'] += flt(claim.grand_total)

	data = []
	for warehouse in warehouses:
		bucket = totals[warehouse.name]
		total_sales = flt(bucket['total_sales'])
		total_purchase = flt(bucket['total_purchase'])
		total_expense = flt(bucket['total_expense'])
		gross_profit = total_sales - total_purchase
		net_profit = gross_profit - total_expense
		label = warehouse.warehouse_name or warehouse.name
		row = {
			'warehouse': warehouse.name,
			'warehouse_name': label,
			'opening_balance': flt(openings.get(warehouse.name)),
			'total_sales': total_sales,
			'total_purchase': total_purchase,
			'gross_profit': gross_profit,
			'total_expense': total_expense,
			'net_profit': net_profit,
			'customer_due': flt(customer_due.get(warehouse.name)),
			'supplier_payable': flt(supplier_payable.get(warehouse.name)),
			'current_stock_value': flt(stock_values.get(warehouse.name)),
			'closing_balance': flt((cash_by_name.get(label) or {}).get('closing_cash_balance')),
		}
		if any(flt(row[field]) for field in row if field not in ('warehouse', 'warehouse_name')):
			data.append(row)
	return columns, data


def _stock_values(warehouse_names):
	if not warehouse_names:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT warehouse, SUM(stock_value) AS stock_value
		FROM `tabBin`
		WHERE warehouse IN %(warehouses)s
		GROUP BY warehouse
		""",
		{'warehouses': warehouse_names},
		as_dict=True,
	)
	return {row.warehouse: flt(row.stock_value) for row in rows}


def _outstanding_by_warehouse(doctype, warehouses, company, to_date):
	"""Outstanding on invoices still open as of to_date, by set_warehouse."""
	names = [warehouse.name for warehouse in warehouses]
	if not names:
		return {}
	rows = frappe.db.sql(
		f"""
		SELECT set_warehouse AS warehouse, SUM(outstanding_amount) AS outstanding
		FROM `tab{doctype}`
		WHERE docstatus = 1
			AND company = %(company)s
			AND posting_date <= %(to_date)s
			AND IFNULL(outstanding_amount, 0) != 0
			AND set_warehouse IN %(warehouses)s
		GROUP BY set_warehouse
		""",
		{'company': company, 'to_date': to_date, 'warehouses': names},
		as_dict=True,
	)
	return {row.warehouse: abs(flt(row.outstanding)) for row in rows}


def molding_production(filters=None):
	"""Finished goods from Manufacture stock entries, with item weight."""
	filters = frappe._dict(filters or {})
	from_date, to_date = date_range(filters)
	warehouses = get_matrix_warehouses(filters)
	warehouse_names = [warehouse.name for warehouse in warehouses]
	columns = [
		{'label': _('Item Code'), 'fieldname': 'item_code', 'fieldtype': 'Link', 'options': 'Item', 'width': 130},
		{'label': _('Item Group'), 'fieldname': 'item_group', 'fieldtype': 'Link', 'options': 'Item Group', 'width': 140},
		{'label': _('Item Name'), 'fieldname': 'item_name', 'fieldtype': 'Data', 'width': 200},
		{'label': _('Item Quantity'), 'fieldname': 'quantity', 'fieldtype': 'Float', 'width': 120},
		{'label': _('Weight'), 'fieldname': 'weight', 'fieldtype': 'Float', 'width': 120},
	]
	if not warehouse_names:
		return columns, []

	entry = DocType('Stock Entry')
	line = DocType('Stock Entry Detail')
	item = DocType('Item')
	query = (
		frappe.qb.from_(line)
		.inner_join(entry)
		.on(entry.name == line.parent)
		.inner_join(item)
		.on(item.name == line.item_code)
		.select(
			item.name.as_('item_code'),
			item.item_name,
			item.item_group,
			Sum(Coalesce(line.transfer_qty, line.qty, 0)).as_('quantity'),
			Sum(
				Coalesce(line.transfer_qty, line.qty, 0) * Coalesce(item.custom_default_weigt_of_measure, 0)
			).as_('weight'),
		)
		.where(entry.docstatus == 1)
		.where(entry.purpose == 'Manufacture')
		.where(entry.posting_date >= from_date)
		.where(entry.posting_date <= to_date)
		.where(line.t_warehouse.isin(warehouse_names))
		.where(Coalesce(line.t_warehouse, '') != '')
		.groupby(item.name, item.item_name, item.item_group)
	)
	if filters.get('company'):
		query = query.where(entry.company == filters.company)
	item_codes = parse_list(filters.get('item_code'))
	if item_codes:
		query = query.where(item.name.isin(item_codes))
	item_groups = parse_list(filters.get('item_group'))
	if item_groups:
		query = query.where(item.item_group.isin(item_groups))

	data = query.run(as_dict=True)
	data.sort(key=lambda row: (row.item_group or '', row.item_name or row.item_code or ''))
	return columns, data
