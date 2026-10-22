# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""N. Poly & RFL pipe purchase/sale history and summary.

Limited to the three item groups the business tracks on DO purchases that
are later sold: N.Poly Suction Hose Pipe, N. Poly BS Class Pipe, RFL Pipe.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from bsp_engineering.utils.item_warehouse_matrix import date_range, parse_list
from bsp_engineering.utils.report_permissions import get_report_permitted_warehouses

NPOLY_RFL_ITEM_GROUPS = (
	'N.Poly Suction Hose Pipe',
	'N. Poly BS Class Pipe',
	'RFL Pipe',
)


def history_list(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{'label': _('Date'), 'fieldname': 'date', 'fieldtype': 'Date', 'width': 100},
		{'label': _('Do Number'), 'fieldname': 'do_number', 'fieldtype': 'Data', 'width': 140},
		{'label': _('Do Amount'), 'fieldname': 'do_amount', 'fieldtype': 'Currency', 'width': 120},
		{'label': _('Item Code'), 'fieldname': 'item_code', 'fieldtype': 'Link', 'options': 'Item', 'width': 120},
		{'label': _('Item Name'), 'fieldname': 'item_name', 'fieldtype': 'Data', 'width': 180},
		{'label': _('Item Quantity'), 'fieldname': 'quantity', 'fieldtype': 'Float', 'width': 110},
		{'label': _('MRP'), 'fieldname': 'mrp', 'fieldtype': 'Currency', 'width': 100},
		{'label': _('Discount'), 'fieldname': 'discount', 'fieldtype': 'Currency', 'width': 100},
		{'label': _('Dealer Price'), 'fieldname': 'dealer_price', 'fieldtype': 'Currency', 'width': 120},
		{'label': _('Sales Price'), 'fieldname': 'sales_price', 'fieldtype': 'Currency', 'width': 120},
	]
	sales = _sales_rows(filters)
	purchases = _purchase_rates(filters)
	do_amounts = _do_amounts(filters)

	data = []
	for row in sales:
		key = (row.do_number, row.item_code)
		purchase = purchases.get(key) or {}
		data.append(
			{
				'date': row.posting_date,
				'do_number': row.do_number,
				'do_amount': flt(do_amounts.get(row.do_number)),
				'item_code': row.item_code,
				'item_name': row.item_name,
				'quantity': flt(row.qty),
				'mrp': flt(row.price_list_rate),
				'discount': flt(row.discount_amount),
				'dealer_price': flt(purchase.get('rate')),
				'sales_price': flt(row.rate),
			}
		)
	data.sort(key=lambda entry: (entry['date'] or '', entry['do_number'] or '', entry['item_code'] or ''))
	return columns, data


def summary_report(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{'label': _('Do Amount'), 'fieldname': 'do_amount', 'fieldtype': 'Currency', 'width': 120},
		{'label': _('Item Code'), 'fieldname': 'item_code', 'fieldtype': 'Link', 'options': 'Item', 'width': 120},
		{'label': _('Item Name'), 'fieldname': 'item_name', 'fieldtype': 'Data', 'width': 180},
		{'label': _('Item Quantity'), 'fieldname': 'quantity', 'fieldtype': 'Float', 'width': 110},
		{'label': _('Dealer Price'), 'fieldname': 'dealer_price', 'fieldtype': 'Currency', 'width': 120},
		{'label': _('Sales Price'), 'fieldname': 'sales_price', 'fieldtype': 'Currency', 'width': 120},
		{'label': _('Loss/Profit'), 'fieldname': 'loss_profit', 'fieldtype': 'Currency', 'width': 120},
	]
	_columns, history = history_list(filters)
	by_item = {}
	do_by_item = defaultdict(set)
	for row in history:
		entry = by_item.setdefault(
			row['item_code'],
			{
				'item_code': row['item_code'],
				'item_name': row['item_name'],
				'quantity': 0.0,
				'dealer_amount': 0.0,
				'sales_amount': 0.0,
			},
		)
		qty = flt(row['quantity'])
		entry['quantity'] += qty
		entry['dealer_amount'] += flt(row['dealer_price']) * qty
		entry['sales_amount'] += flt(row['sales_price']) * qty
		if row.get('do_number'):
			do_by_item[row['item_code']].add((row['do_number'], flt(row['do_amount'])))

	data = []
	for entry in by_item.values():
		qty = flt(entry['quantity'])
		dealer_price = flt(entry['dealer_amount'] / qty) if qty else 0.0
		sales_price = flt(entry['sales_amount'] / qty) if qty else 0.0
		do_amount = sum(amount for do_number, amount in do_by_item.get(entry['item_code'], ()))
		data.append(
			{
				'do_amount': do_amount,
				'item_code': entry['item_code'],
				'item_name': entry['item_name'],
				'quantity': qty,
				'dealer_price': dealer_price,
				'sales_price': sales_price,
				'loss_profit': flt(entry['sales_amount']) - flt(entry['dealer_amount']),
			}
		)
	data.sort(key=lambda row: (-flt(row['loss_profit']), row['item_code'] or ''))
	return columns, data


def _item_group_filter(filters):
	groups = parse_list(filters.get('item_group')) or list(NPOLY_RFL_ITEM_GROUPS)
	return [group for group in groups if group in NPOLY_RFL_ITEM_GROUPS] or list(NPOLY_RFL_ITEM_GROUPS)


def _common_values(filters):
	from_date, to_date = date_range(filters)
	values = {
		'from_date': from_date,
		'to_date': to_date,
		'item_groups': tuple(_item_group_filter(filters)),
	}
	if filters.get('company'):
		values['company'] = filters.company
	if filters.get('do_number'):
		values['do_number'] = f"%{filters.do_number}%"
	item_codes = parse_list(filters.get('item_code'))
	if item_codes:
		values['item_codes'] = tuple(item_codes)
	permitted = get_report_permitted_warehouses()
	if permitted is not None:
		values['warehouses'] = tuple(permitted) or ('',)
	return values


def _sales_rows(filters):
	values = _common_values(filters)
	conditions = [
		'si.docstatus = 1',
		'si.is_return = 0',
		"IFNULL(si.custom_do_number, '') != ''",
		'si.posting_date BETWEEN %(from_date)s AND %(to_date)s',
		'sii.item_group IN %(item_groups)s',
	]
	if values.get('company'):
		conditions.append('si.company = %(company)s')
	if values.get('do_number'):
		conditions.append('si.custom_do_number LIKE %(do_number)s')
	if values.get('item_codes'):
		conditions.append('sii.item_code IN %(item_codes)s')
	if values.get('warehouses'):
		conditions.append('sii.warehouse IN %(warehouses)s')

	return frappe.db.sql(
		f"""
		SELECT si.posting_date, si.custom_do_number AS do_number,
		       sii.item_code, sii.item_name, sii.stock_qty AS qty,
		       sii.price_list_rate, sii.discount_amount, sii.rate
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE {' AND '.join(conditions)}
		ORDER BY si.posting_date, si.custom_do_number, sii.item_code
		""",
		values,
		as_dict=True,
	)


def _purchase_rates(filters):
	values = _common_values(filters)
	conditions = [
		'pi.docstatus = 1',
		'pi.is_return = 0',
		"IFNULL(pi.custom_do_number, '') != ''",
		'pi.posting_date BETWEEN %(from_date)s AND %(to_date)s',
		'pii.item_group IN %(item_groups)s',
	]
	if values.get('company'):
		conditions.append('pi.company = %(company)s')
	if values.get('do_number'):
		conditions.append('pi.custom_do_number LIKE %(do_number)s')
	if values.get('item_codes'):
		conditions.append('pii.item_code IN %(item_codes)s')
	if values.get('warehouses'):
		conditions.append('pii.warehouse IN %(warehouses)s')

	rows = frappe.db.sql(
		f"""
		SELECT pi.custom_do_number AS do_number, pii.item_code,
		       SUM(pii.amount) AS amount, SUM(IFNULL(pii.stock_qty, pii.qty)) AS qty
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
		WHERE {' AND '.join(conditions)}
		GROUP BY pi.custom_do_number, pii.item_code
		""",
		values,
		as_dict=True,
	)
	rates = {}
	for row in rows:
		qty = flt(row.qty)
		rates[(row.do_number, row.item_code)] = {'rate': flt(row.amount) / qty if qty else 0.0}
	return rates


def _do_amounts(filters):
	values = _common_values(filters)
	conditions = [
		'pi.docstatus = 1',
		'pi.is_return = 0',
		"IFNULL(pi.custom_do_number, '') != ''",
		'pi.posting_date BETWEEN %(from_date)s AND %(to_date)s',
	]
	if values.get('company'):
		conditions.append('pi.company = %(company)s')
	if values.get('do_number'):
		conditions.append('pi.custom_do_number LIKE %(do_number)s')

	rows = frappe.db.sql(
		f"""
		SELECT custom_do_number AS do_number, SUM(grand_total) AS amount
		FROM `tabPurchase Invoice` pi
		WHERE {' AND '.join(conditions)}
		GROUP BY custom_do_number
		""",
		values,
		as_dict=True,
	)
	return {row.do_number: flt(row.amount) for row in rows}
