# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

from bsp_engineering.utils.warehouse_row_reports import transfer_summary


def execute(filters=None):
	return transfer_summary(filters)
