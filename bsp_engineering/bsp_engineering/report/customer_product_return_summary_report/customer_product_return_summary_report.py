# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

from bsp_engineering.utils.item_warehouse_matrix import sales_summary


def execute(filters=None):
	return sales_summary(filters, returns_only=True)
