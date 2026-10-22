# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

from bsp_engineering.utils.warehouse_row_reports import requisition_summary


def execute(filters=None):
	return requisition_summary(filters)
