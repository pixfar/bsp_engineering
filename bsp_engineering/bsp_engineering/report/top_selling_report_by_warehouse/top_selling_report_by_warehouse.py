# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

from bsp_engineering.utils.warehouse_row_reports import top_selling_by_warehouse


def execute(filters=None):
	return top_selling_by_warehouse(filters)
