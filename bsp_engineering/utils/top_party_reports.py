# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Top Customer / Top Supplier by invoice amount."""

import frappe
from frappe import _
from frappe.utils import flt, strip_html

from bsp_engineering.utils.item_warehouse_matrix import date_range, get_matrix_warehouses


def top_customers(filters=None):
	return _top_parties(filters, party='customer')


def top_suppliers(filters=None):
	return _top_parties(filters, party='supplier')


def _top_parties(filters, party):
	filters = frappe._dict(filters or {})
	warehouses = get_matrix_warehouses(filters)
	warehouse_names = [warehouse.name for warehouse in warehouses]
	name_label = _('Customer Name') if party == 'customer' else _('Supplier Name')
	columns = [
		{'label': name_label, 'fieldname': 'party_name', 'fieldtype': 'Data', 'width': 200},
		{'label': _('Amount'), 'fieldname': 'amount', 'fieldtype': 'Currency', 'width': 140},
		{'label': _('Warehouse'), 'fieldname': 'warehouse_name', 'fieldtype': 'Data', 'width': 180},
		{'label': _('Mobile'), 'fieldname': 'mobile', 'fieldtype': 'Data', 'width': 120},
		{'label': _('Location'), 'fieldname': 'location', 'fieldtype': 'Data', 'width': 180},
	]
	if not warehouse_names:
		return columns, []

	from_date, to_date = date_range(filters)
	if party == 'customer':
		parent, child, party_table, name_field = (
			'Sales Invoice',
			'Sales Invoice Item',
			'Customer',
			'customer_name',
		)
		location_expr = 'party.territory'
	else:
		parent, child, party_table, name_field = (
			'Purchase Invoice',
			'Purchase Invoice Item',
			'Supplier',
			'supplier_name',
		)
		location_expr = 'party.primary_address'

	values = {
		'from_date': from_date,
		'to_date': to_date,
		'warehouses': tuple(warehouse_names),
	}
	conditions = [
		'invoice.docstatus = 1',
		'invoice.is_return = 0',
		'line.parenttype = %(parent)s',
		'invoice.posting_date BETWEEN %(from_date)s AND %(to_date)s',
		'line.warehouse IN %(warehouses)s',
	]
	values['parent'] = parent
	if filters.get('company'):
		conditions.append('invoice.company = %(company)s')
		values['company'] = filters.company
	if filters.get(party):
		conditions.append(f'invoice.{party} = %(party)s')
		values['party'] = filters.get(party)

	rows = frappe.db.sql(
		f"""
		SELECT invoice.{party} AS party,
		       party.{name_field} AS party_name,
		       line.warehouse AS warehouse,
		       warehouse.warehouse_name AS warehouse_name,
		       party.mobile_no AS mobile,
		       {location_expr} AS location,
		       SUM(IFNULL(line.base_net_amount, 0)) AS amount
		FROM `tab{child}` line
		INNER JOIN `tab{parent}` invoice ON invoice.name = line.parent
		INNER JOIN `tab{party_table}` party ON party.name = invoice.{party}
		LEFT JOIN `tabWarehouse` warehouse ON warehouse.name = line.warehouse
		WHERE {' AND '.join(conditions)}
		GROUP BY invoice.{party}, party.{name_field}, line.warehouse,
		         warehouse.warehouse_name, party.mobile_no, {location_expr}
		HAVING SUM(IFNULL(line.base_net_amount, 0)) != 0
		ORDER BY amount DESC, party_name ASC
		""",
		values,
		as_dict=True,
	)

	data = [
		{
			'party': row.party,
			'party_name': row.party_name or row.party,
			'amount': flt(row.amount),
			'warehouse': row.warehouse,
			'warehouse_name': row.warehouse_name or row.warehouse,
			'mobile': row.mobile or '',
			'location': strip_html(row.location or '').replace('\n', ', ').strip(),
		}
		for row in rows
	]
	limit = int(filters.get('limit') or 0)
	if limit > 0:
		data = data[:limit]
	return columns, data
