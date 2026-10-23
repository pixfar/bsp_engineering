# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Item rows by warehouse columns for the BSP summary reports.

Columns are every leaf warehouse (company and permission scoped), in
Warehouse Sort Order -- not the showrooms drawn on the sample sheet. A
warehouse added later shows up on its own; a group warehouse such as
"All Warehouses" does not get a column.
"""

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Coalesce, Sum
from frappe.utils import cint, flt, get_first_day, getdate, today

from bsp_engineering.utils.item_category_sort import (
	get_item_sort_map,
	item_category_sort_key,
	sort_rows_by_item_category,
)
from bsp_engineering.utils.report_permissions import (
	check_warehouse_filter,
	filter_permitted_warehouses,
)
from bsp_engineering.utils.warehouse_sort import sort_warehouses

WEIGHT_FIELD = 'custom_default_weigt_of_measure'


def parse_list(value):
	"""MultiSelectList filters arrive as a JSON string, a list, or one name."""
	if not value:
		return []
	if isinstance(value, (list, tuple)):
		return [entry for entry in value if entry]
	if isinstance(value, str):
		value = value.strip()
		if not value:
			return []
		if value.startswith('['):
			return [entry for entry in (frappe.parse_json(value) or []) if entry]
		return [value]
	return []


def date_range(filters):
	from_date = getdate(filters.get('from_date') or get_first_day(today()))
	to_date = getdate(filters.get('to_date') or today())
	if from_date > to_date:
		frappe.throw(_('From Date cannot be after To Date'))
	return from_date, to_date


def warehouse_fieldnames(warehouses):
	"""Stable column ids. Warehouse names are not safe fieldnames."""
	used = set()
	mapping = {}
	for warehouse in warehouses:
		base = frappe.scrub(warehouse.name) or 'warehouse'
		fieldname = base
		suffix = 2
		while fieldname in used:
			fieldname = f'{base}_{suffix}'
			suffix += 1
		used.add(fieldname)
		mapping[warehouse.name] = fieldname
	return mapping


def get_matrix_warehouses(filters):
	"""Leaf warehouses in official order. An explicit warehouse filter
	narrows the columns; a group warehouse expands to its leaves."""
	selected = _expand_selected_warehouses(parse_list(filters.get('warehouse')))
	if selected:
		check_warehouse_filter(selected)

	warehouse = DocType('Warehouse')
	query = (
		frappe.qb.from_(warehouse)
		.select(warehouse.name, warehouse.warehouse_name)
		.where(warehouse.is_group == 0)
	)
	if filters.get('company'):
		query = query.where(warehouse.company == filters.company)
	if selected:
		query = query.where(warehouse.name.isin(selected))

	rows = sort_warehouses(query.run(as_dict=True), key='name')
	return filter_permitted_warehouses(rows, key='name')


def _expand_selected_warehouses(selected):
	if not selected:
		return []
	expanded = []
	for name in selected:
		if frappe.db.get_value('Warehouse', name, 'is_group'):
			expanded.extend(frappe.db.get_descendants('Warehouse', name) or [])
		else:
			expanded.append(name)
	return expanded


def item_columns():
	return [
		{
			'label': _('Item Code'),
			'fieldname': 'item_code',
			'fieldtype': 'Link',
			'options': 'Item',
			'width': 140,
		},
		{'label': _('Item Name'), 'fieldname': 'item_name', 'fieldtype': 'Data', 'width': 180},
		{
			'label': _('Item Group'),
			'fieldname': 'item_group',
			'fieldtype': 'Link',
			'options': 'Item Group',
			'width': 140,
		},
	]


def party_columns(party_field):
	"""Customer/Supplier name + mobile for return summary rows."""
	if party_field == 'customer':
		name_label = _('Customer Name')
	else:
		name_label = _('Supplier Name')
	return [
		{'label': name_label, 'fieldname': 'party_name', 'fieldtype': 'Data', 'width': 180},
		{'label': _('Mobile'), 'fieldname': 'mobile', 'fieldtype': 'Data', 'width': 120},
	]


def _value_fieldname(qty_fieldname):
	return f'{qty_fieldname}_value'


def warehouse_columns(warehouses, fieldnames, with_value=False):
	columns = []
	for warehouse in warehouses:
		label = warehouse.warehouse_name or warehouse.name
		qty_fieldname = fieldnames[warehouse.name]
		columns.append(
			{
				'label': _('{0} Qty').format(label) if with_value else label,
				'fieldname': qty_fieldname,
				'fieldtype': 'Float',
				'width': 120,
			}
		)
		if with_value:
			columns.append(
				{
					'label': _('{0} Value').format(label),
					'fieldname': _value_fieldname(qty_fieldname),
					'fieldtype': 'Currency',
					'width': 130,
				}
			)
	return columns


def total_columns():
	"""Cross-warehouse totals — shown before warehouse columns for a quick sum."""
	return [
		{'label': _('Grand Total Qty'), 'fieldname': 'quantity', 'fieldtype': 'Float', 'width': 120},
		{'label': _('Grand Total Value'), 'fieldname': 'value', 'fieldtype': 'Currency', 'width': 140},
	]


def hide_zero_flags(filters):
	"""Optional report Checks: default off so all zero columns/rows stay visible."""
	filters = filters or {}
	return cint(filters.get('hide_zero_columns')), cint(filters.get('hide_zero_rows'))


def restrict_items(query, item, filters):
	item_codes = parse_list(filters.get('item_code'))
	if item_codes:
		query = query.where(item.name.isin(item_codes))

	item_groups = parse_list(filters.get('item_group'))
	if item_groups:
		query = query.where(item.item_group.isin(item_groups))

	if filters.get('brand'):
		query = query.where(item.brand == filters.brand)

	if filters.get('stock_uom'):
		query = query.where(item.stock_uom == filters.stock_uom)

	production_groups = parse_list(filters.get('production_group'))
	if production_groups and frappe.get_meta('Item').has_field('custom_production_group'):
		query = query.where(item.custom_production_group.isin(production_groups))

	return query


def assemble_rows(
	raw_rows,
	warehouses,
	fieldnames,
	include_items=None,
	value_field='qty',
	with_value=False,
	group_by_party=False,
	hide_zero_rows=False,
):
	"""One row per item (or per party+item when group_by_party). Warehouse
	cells sum `value_field`. `with_value` also keeps the invoice amount beside
	each warehouse qty. When `hide_zero_rows`, items with no quantity or amount
	in any shown warehouse are left out (unless `include_items` forces them)."""
	blank = {}
	for warehouse in warehouses:
		qty_fieldname = fieldnames[warehouse.name]
		blank[qty_fieldname] = 0.0
		if with_value:
			blank[_value_fieldname(qty_fieldname)] = 0.0
	by_key = {}

	def ensure(raw):
		item_code = raw.get('item_code')
		key = (raw.get('party'), item_code) if group_by_party else item_code
		row = by_key.get(key)
		if row is None:
			row = {
				'item_code': item_code,
				'item_name': raw.get('item_name'),
				'item_group': raw.get('item_group'),
				'quantity': 0.0,
				'value': 0.0,
				**blank,
			}
			if group_by_party:
				row['party'] = raw.get('party')
				row['party_name'] = raw.get('party_name') or raw.get('party') or ''
				row['mobile'] = raw.get('mobile') or ''
			by_key[key] = row
		return row

	for raw in raw_rows:
		fieldname = fieldnames.get(raw.get('warehouse'))
		if not fieldname or not raw.get('item_code'):
			continue
		row = ensure(raw)
		row[fieldname] = flt(row[fieldname]) + flt(raw.get(value_field))
		row['quantity'] = flt(row['quantity']) + flt(raw.get('qty'))
		amount = flt(raw.get('amount'))
		row['value'] = flt(row['value']) + amount
		if with_value:
			amount_field = _value_fieldname(fieldname)
			row[amount_field] = flt(row[amount_field]) + amount

	if include_items is not None:
		for item in include_items:
			ensure(
				{
					'item_code': item.get('item_code') or item.get('name'),
					'item_name': item.get('item_name'),
					'item_group': item.get('item_group'),
				}
			)
		return list(by_key.values())

	rows = list(by_key.values())
	if not hide_zero_rows:
		return rows

	def has_figure(row):
		for warehouse in warehouses:
			qty_fieldname = fieldnames[warehouse.name]
			if flt(row[qty_fieldname]):
				return True
			if with_value and flt(row[_value_fieldname(qty_fieldname)]):
				return True
		return False

	return [row for row in rows if has_figure(row)]


_FIXED_FIELDS = {
	'item_code',
	'item_name',
	'item_group',
	'quantity',
	'value',
	'party',
	'party_name',
	'mobile',
}


def omit_empty_warehouse_columns(columns, data, warehouses, fieldnames, with_value=False):
	"""Drop a warehouse when every row is 0 there. Qty and value stay
	together: one non-zero side keeps both columns. Only used when the
	Hide Zero Columns filter is on."""
	active = set()
	for warehouse in warehouses:
		qty_field = fieldnames[warehouse.name]
		fields = [qty_field]
		if with_value:
			fields.append(_value_fieldname(qty_field))
		if any(flt(row.get(field)) for row in data for field in fields):
			active.update(fields)
	return [
		column
		for column in columns
		if column['fieldname'] in _FIXED_FIELDS or column['fieldname'] in active
	]


def _finish(
	columns,
	data,
	warehouses,
	fieldnames,
	with_value=False,
	sort_by_value=False,
	group_by_party=False,
	filters=None,
):
	if not warehouses:
		return columns, []
	if sort_by_value:
		data.sort(key=lambda row: (-flt(row.get('value')), -flt(row.get('quantity')), row.get('item_code') or ''))
	elif group_by_party:
		sort_map = get_item_sort_map()
		data.sort(
			key=lambda row: (
				(row.get('party_name') or '').lower(),
				item_category_sort_key(sort_map, row.get('item_code')),
			)
		)
	else:
		data = sort_rows_by_item_category(data, get_item_sort_map())
	hide_cols, _hide_rows = hide_zero_flags(filters)
	if hide_cols:
		columns = omit_empty_warehouse_columns(columns, data, warehouses, fieldnames, with_value)
	return columns, data


def _invoice_matrix_columns(warehouses, fieldnames, party_field=None):
	columns = []
	if party_field:
		columns.extend(party_columns(party_field))
	columns.extend(item_columns())
	columns.extend(total_columns())
	columns.extend(warehouse_columns(warehouses, fieldnames, with_value=True))
	return columns


def sales_summary(filters=None, include_all_items=False, returns_only=False):
	filters = frappe._dict(filters or {})
	hide_cols, hide_rows = hide_zero_flags(filters)
	warehouses = get_matrix_warehouses(filters)
	fieldnames = warehouse_fieldnames(warehouses)
	party_field = 'customer' if returns_only else None
	columns = _invoice_matrix_columns(warehouses, fieldnames, party_field=party_field)
	if not warehouses:
		return columns, []

	raw = _invoice_rows(
		filters,
		[warehouse.name for warehouse in warehouses],
		parent='Sales Invoice',
		child='Sales Invoice Item',
		party_field='customer',
		party_group_field='customer_group',
		returns_only=returns_only,
	)
	include = _filtered_items(filters) if include_all_items else None
	data = assemble_rows(
		raw,
		warehouses,
		fieldnames,
		include_items=include,
		with_value=True,
		group_by_party=returns_only,
		hide_zero_rows=hide_rows,
	)
	return _finish(
		columns,
		data,
		warehouses,
		fieldnames,
		with_value=True,
		sort_by_value=include_all_items,
		group_by_party=returns_only,
		filters=filters,
	)


def purchase_summary(filters=None, returns_only=False):
	filters = frappe._dict(filters or {})
	_hide_cols, hide_rows = hide_zero_flags(filters)
	warehouses = get_matrix_warehouses(filters)
	fieldnames = warehouse_fieldnames(warehouses)
	party_field = 'supplier' if returns_only else None
	columns = _invoice_matrix_columns(warehouses, fieldnames, party_field=party_field)
	if not warehouses:
		return columns, []

	raw = _invoice_rows(
		filters,
		[warehouse.name for warehouse in warehouses],
		parent='Purchase Invoice',
		child='Purchase Invoice Item',
		party_field='supplier',
		party_group_field='supplier_group',
		returns_only=returns_only,
	)
	data = assemble_rows(
		raw,
		warehouses,
		fieldnames,
		with_value=True,
		group_by_party=returns_only,
		hide_zero_rows=hide_rows,
	)
	return _finish(
		columns, data, warehouses, fieldnames, with_value=True, group_by_party=returns_only, filters=filters
	)


def stock_entry_summary(filters=None, purpose=None, warehouse_field='t_warehouse'):
	filters = frappe._dict(filters or {})
	_hide_cols, hide_rows = hide_zero_flags(filters)
	warehouses = get_matrix_warehouses(filters)
	fieldnames = warehouse_fieldnames(warehouses)
	columns = item_columns() + [
		{'label': _('Grand Total Qty'), 'fieldname': 'quantity', 'fieldtype': 'Float', 'width': 120},
	] + warehouse_columns(warehouses, fieldnames)
	if not warehouses:
		return columns, []

	raw = _stock_entry_rows(
		filters,
		[warehouse.name for warehouse in warehouses],
		purpose=purpose,
		warehouse_field=warehouse_field,
	)
	data = assemble_rows(raw, warehouses, fieldnames, hide_zero_rows=hide_rows)
	return _finish(columns, data, warehouses, fieldnames, filters=filters)


def weight_summary(filters=None):
	"""Stock on hand as of `to_date`, times the item's default weight,
	per warehouse. Current Bin qty would ignore the As On Date filter."""
	filters = frappe._dict(filters or {})
	_hide_cols, hide_rows = hide_zero_flags(filters)
	as_on = getdate(filters.get('to_date') or today())
	warehouses = get_matrix_warehouses(filters)
	fieldnames = warehouse_fieldnames(warehouses)
	columns = item_columns() + [
		{'label': _('Grand Total Weight'), 'fieldname': 'quantity', 'fieldtype': 'Float', 'width': 130},
	] + warehouse_columns(warehouses, fieldnames)
	if not warehouses:
		return columns, []

	raw = _balance_rows(filters, [warehouse.name for warehouse in warehouses], as_on)
	_apply_item_weight(raw)
	data = assemble_rows(raw, warehouses, fieldnames, value_field='weight', hide_zero_rows=hide_rows)
	# Warehouse cells hold weight; Grand Total should sum those, not stock qty.
	for row in data:
		row['quantity'] = sum(flt(row.get(fieldnames[warehouse.name])) for warehouse in warehouses)
	return _finish(columns, data, warehouses, fieldnames, filters=filters)


def _invoice_rows(filters, warehouse_names, parent, child, party_field, party_group_field, returns_only=False):
	from_date, to_date = date_range(filters)
	invoice = DocType(parent)
	line = DocType(child)
	item = DocType('Item')
	party_doctype = 'Customer' if party_field == 'customer' else 'Supplier'
	party = DocType(party_doctype)
	party_name_field = party.customer_name if party_field == 'customer' else party.supplier_name

	select_fields = [
		item.name.as_('item_code'),
		item.item_name,
		item.item_group,
		line.warehouse,
		Sum(Coalesce(line.stock_qty, line.qty, 0)).as_('qty'),
		Sum(Coalesce(line.base_net_amount, 0)).as_('amount'),
	]
	group_fields = [item.name, item.item_name, item.item_group, line.warehouse]
	if returns_only:
		select_fields.extend(
			[
				getattr(invoice, party_field).as_('party'),
				party_name_field.as_('party_name'),
				party.mobile_no.as_('mobile'),
			]
		)
		group_fields.extend([getattr(invoice, party_field), party_name_field, party.mobile_no])

	query = (
		frappe.qb.from_(line)
		.inner_join(invoice)
		.on(invoice.name == line.parent)
		.inner_join(item)
		.on(item.name == line.item_code)
	)
	if returns_only:
		query = query.left_join(party).on(party.name == getattr(invoice, party_field))
	query = (
		query.select(*select_fields)
		.where(invoice.docstatus == 1)
		.where(line.parenttype == parent)
		.where(line.parentfield == 'items')
		.where(invoice.posting_date >= from_date)
		.where(invoice.posting_date <= to_date)
		.where(line.warehouse.isin(warehouse_names))
		.groupby(*group_fields)
	)
	if filters.get('company'):
		query = query.where(invoice.company == filters.company)
	if filters.get(party_field):
		query = query.where(getattr(invoice, party_field) == filters.get(party_field))
	if filters.get(party_group_field):
		query = query.where(getattr(invoice, party_group_field) == filters.get(party_group_field))
	if filters.get('mode_of_payment'):
		query = _where_mode_of_payment(query, invoice, parent, filters.mode_of_payment)
	if returns_only:
		query = query.where(invoice.is_return == 1)

	query = restrict_items(query, item, filters)
	rows = query.run(as_dict=True)
	if returns_only:
		for row in rows:
			row.qty = abs(flt(row.qty))
			row.amount = abs(flt(row.amount))
	return rows


def _where_mode_of_payment(query, invoice, parent, mode_of_payment):
	if parent == 'Sales Invoice':
		payment = DocType('Sales Invoice Payment')
		matching = (
			frappe.qb.from_(payment)
			.select(payment.parent)
			.where(payment.mode_of_payment == mode_of_payment)
			.where(payment.parenttype == 'Sales Invoice')
		)
		return query.where(invoice.name.isin(matching))
	return query.where(invoice.mode_of_payment == mode_of_payment)


def _stock_entry_rows(filters, warehouse_names, purpose, warehouse_field):
	from_date, to_date = date_range(filters)
	entry = DocType('Stock Entry')
	line = DocType('Stock Entry Detail')
	item = DocType('Item')
	warehouse_column = line.t_warehouse if warehouse_field == 't_warehouse' else line.s_warehouse

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
			warehouse_column.as_('warehouse'),
			Sum(Coalesce(line.transfer_qty, line.qty, 0)).as_('qty'),
		)
		.where(entry.docstatus == 1)
		.where(line.parenttype == 'Stock Entry')
		.where(entry.purpose == purpose)
		.where(entry.posting_date >= from_date)
		.where(entry.posting_date <= to_date)
		.where(warehouse_column.isin(warehouse_names))
		.groupby(item.name, item.item_name, item.item_group, warehouse_column)
	)
	if filters.get('company'):
		query = query.where(entry.company == filters.company)
	query = restrict_items(query, item, filters)
	return query.run(as_dict=True)


def _balance_rows(filters, warehouse_names, as_on):
	ledger = DocType('Stock Ledger Entry')
	item = DocType('Item')
	query = (
		frappe.qb.from_(ledger)
		.inner_join(item)
		.on(item.name == ledger.item_code)
		.select(
			item.name.as_('item_code'),
			item.item_name,
			item.item_group,
			ledger.warehouse,
			Sum(ledger.actual_qty).as_('qty'),
		)
		.where(ledger.is_cancelled == 0)
		.where(ledger.posting_date <= as_on)
		.where(ledger.warehouse.isin(warehouse_names))
		.groupby(item.name, item.item_name, item.item_group, ledger.warehouse)
	)
	if filters.get('company'):
		query = query.where(ledger.company == filters.company)
	query = restrict_items(query, item, filters)
	return query.run(as_dict=True)


def _apply_item_weight(rows):
	if not rows or not frappe.get_meta('Item').has_field(WEIGHT_FIELD):
		for row in rows:
			row['weight'] = 0.0
		return

	codes = list({row.item_code for row in rows if row.item_code})
	weights = {
		row.name: flt(row.get(WEIGHT_FIELD))
		for row in frappe.get_all('Item', filters={'name': ['in', codes]}, fields=['name', WEIGHT_FIELD])
	}
	for row in rows:
		row['weight'] = flt(row.qty) * weights.get(row.item_code, 0.0)


def _filtered_items(filters):
	item = DocType('Item')
	query = (
		frappe.qb.from_(item)
		.select(item.name.as_('item_code'), item.item_name, item.item_group)
		.where(item.disabled == 0)
		.where(item.has_variants == 0)
	)
	query = restrict_items(query, item, filters)
	return query.run(as_dict=True)
