# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Smoke checks for the warehouse-row / N.Poly / top-party report pack.

    bench --site bsp.localhost execute bsp_engineering.tests.test_additional_bsp_reports.run_checks
"""

import frappe
from frappe.utils import add_days, nowdate

from bsp_engineering.utils.item_warehouse_matrix import purchase_summary, sales_summary
from bsp_engineering.utils.npoly_rfl_reports import history_list, summary_report
from bsp_engineering.utils.top_party_reports import top_customers, top_suppliers
from bsp_engineering.utils.warehouse_row_reports import (
	management_summary,
	molding_production,
	production_progress,
	requisition_summary,
	sales_value_by_report_group,
	top_selling_by_warehouse,
	transfer_summary,
)

COMPANY = 'BSP Engineering Works'


def _filters(**extra):
	base = {
		'company': COMPANY,
		'from_date': add_days(nowdate(), -90),
		'to_date': nowdate(),
	}
	base.update(extra)
	return base


def run_checks():
	checks = [
		('sales_value_by_report_group', lambda: sales_value_by_report_group(_filters())),
		('requisition_summary', lambda: requisition_summary(_filters())),
		('transfer_summary', lambda: transfer_summary(_filters())),
		('management_summary', lambda: management_summary(_filters())),
		('history_list', lambda: history_list(_filters())),
		('summary_report', lambda: summary_report(_filters())),
		('molding_production', lambda: molding_production(_filters())),
		('production_progress', lambda: production_progress(_filters())),
		('top_customers', lambda: top_customers(_filters(limit=10))),
		('top_suppliers', lambda: top_suppliers(_filters(limit=10))),
		('top_selling_by_warehouse', lambda: top_selling_by_warehouse(_filters())),
		('customer_returns', lambda: sales_summary(_filters(), returns_only=True)),
		('supplier_returns', lambda: purchase_summary(_filters(), returns_only=True)),
	]
	for name, fn in checks:
		print('RUN', name)
		columns, data = fn()
		assert columns, f'{name} returned no columns'
		assert isinstance(data, list), f'{name} data is not a list'
		print('OK', name, 'cols', len(columns), 'rows', len(data))

	# Requisition columns that still have counts keep their statuses.
	columns, data = requisition_summary(_filters(from_date='2026-01-01', to_date='2026-10-22'))
	labels = [column['label'] for column in columns]
	assert labels[0] == 'Warehouse Name'
	assert 'Completed' in labels

	# Top selling by warehouse is ordered by value.
	_columns, rows = top_selling_by_warehouse(_filters(from_date='2026-01-01', to_date='2026-10-22'))
	values = [row['value'] for row in rows]
	assert values == sorted(values, reverse=True)

	print('ALL OK')
