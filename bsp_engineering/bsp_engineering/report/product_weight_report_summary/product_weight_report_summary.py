# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import DocType
from pypika import Order


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			'label': _('Stock UOM'),
			'fieldname': 'stock_uom',
			'fieldtype': 'Link',
			'options': 'UOM',
			'width': 120,
		},
		{
			'label': _('Item Code'),
			'fieldname': 'item_code',
			'fieldtype': 'Link',
			'options': 'Item',
			'width': 180,
		},
		{
			'label': _('Warehouse'),
			'fieldname': 'warehouse',
			'fieldtype': 'Link',
			'options': 'Warehouse',
			'width': 180,
		},
		{
			'label': _('Actual Qty'),
			'fieldname': 'actual_qty',
			'fieldtype': 'Float',
			'width': 120,
		},
		{
			'label': _('Default Weight'),
			'fieldname': 'default_weight_of_measure',
			'fieldtype': 'Float',
			'width': 130,
		},
		{
			'label': _('Total Weight'),
			'fieldname': 'total_weight',
			'fieldtype': 'Float',
			'width': 130,
		},
		{
			'label': _('Valuation Rate'),
			'fieldname': 'valuation_rate',
			'fieldtype': 'Currency',
			'width': 130,
		},
		{
			'label': _('Stock Value'),
			'fieldname': 'stock_value',
			'fieldtype': 'Currency',
			'width': 140,
		},
	]


def get_data(filters):
	bin_doctype = DocType('Bin')
	item_doctype = DocType('Item')

	query = (
		frappe.qb.from_(bin_doctype)
		.inner_join(item_doctype)
		.on(item_doctype.name == bin_doctype.item_code)
		.select(
			bin_doctype.stock_uom,
			bin_doctype.item_code,
			bin_doctype.warehouse,
			bin_doctype.actual_qty,
			bin_doctype.valuation_rate,
			bin_doctype.stock_value,
			item_doctype.custom_default_weigt_of_measure.as_(
				'default_weight_of_measure'
			),
		)
		.where(bin_doctype.actual_qty != 0)
		.orderby(bin_doctype.stock_uom, order=Order.asc)
		.orderby(bin_doctype.item_code, order=Order.asc)
		.orderby(bin_doctype.warehouse, order=Order.asc)
	)

	if filters.get('item_code'):
		query = query.where(bin_doctype.item_code == filters.item_code)

	if filters.get('warehouse'):
		query = query.where(bin_doctype.warehouse == filters.warehouse)

	if filters.get('stock_uom'):
		query = query.where(bin_doctype.stock_uom == filters.stock_uom)

	result = query.run(as_dict=True)

	for row in result:
		default_weight = frappe.utils.flt(
			row.get('default_weight_of_measure')
		)
		actual_qty = frappe.utils.flt(row.get('actual_qty'))
		valuation_rate = frappe.utils.flt(row.get('valuation_rate'))
		stock_value = frappe.utils.flt(row.get('stock_value'))

		row['default_weight_of_measure'] = default_weight
		row['total_weight'] = default_weight * actual_qty
		row['valuation_rate'] = valuation_rate
		row['stock_value'] = stock_value or (actual_qty * valuation_rate)

	return result
