# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

from bsp_engineering.utils.warehouse_row_reports import molding_production


def execute(filters=None):
	return molding_production(filters)
