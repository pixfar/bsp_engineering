# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

from operator import itemgetter

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.stock.report.stock_ageing.stock_ageing import FIFOSlots, get_average_age


def execute(filters=None):
	filters = frappe._dict(filters or {})
	to_date = filters.to_date
	filters.show_warehouse_wise_stock = 1

	columns = get_columns()
	data = get_data(filters, to_date)
	return columns, data


def get_columns():
	return [
		{
			'label': _('Warehouse'),
			'fieldname': 'warehouse',
			'fieldtype': 'Link',
			'options': 'Warehouse',
			'width': 180,
		},
		{
			'label': _('Item Name'),
			'fieldname': 'item_name',
			'fieldtype': 'Data',
			'width': 200,
		},
		{
			'label': _('Item Code'),
			'fieldname': 'item_code',
			'fieldtype': 'Link',
			'options': 'Item',
			'width': 140,
		},
		{
			'label': _('Item Group'),
			'fieldname': 'item_group',
			'fieldtype': 'Link',
			'options': 'Item Group',
			'width': 140,
		},
		{
			'label': _('Total Days'),
			'fieldname': 'total_days',
			'fieldtype': 'Float',
			'width': 110,
		},
	]


def get_data(filters, to_date):
	item_details = FIFOSlots(filters).generate()
	_func = itemgetter(1)
	precision = cint(
		frappe.db.get_single_value('System Settings', 'float_precision', cache=True)
	)
	rows = []

	for _key, item_dict in item_details.items():
		if not flt(item_dict.get('total_qty'), precision):
			continue

		fifo_queue = sorted(filter(_func, item_dict['fifo_queue']), key=_func)
		if not fifo_queue:
			continue

		details = item_dict['details']
		rows.append({
			'warehouse': details.warehouse,
			'item_name': details.item_name,
			'item_code': details.name,
			'item_group': details.item_group,
			'total_days': get_average_age(fifo_queue, to_date),
		})

	rows.sort(key=lambda row: (row['warehouse'] or '', row['item_code'] or ''))
	return rows
