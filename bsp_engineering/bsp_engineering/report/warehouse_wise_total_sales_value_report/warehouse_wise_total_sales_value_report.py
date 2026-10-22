# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

from bsp_engineering.utils.warehouse_row_reports import sales_value_by_report_group


def execute(filters=None):
	return sales_value_by_report_group(filters)
