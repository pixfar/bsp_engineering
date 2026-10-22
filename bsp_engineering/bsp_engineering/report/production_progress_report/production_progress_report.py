# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

from bsp_engineering.utils.warehouse_row_reports import production_progress


def execute(filters=None):
	return production_progress(filters)
