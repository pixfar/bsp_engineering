# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

from bsp_engineering.utils.item_warehouse_matrix import stock_entry_summary


def execute(filters=None):
	return stock_entry_summary(filters, purpose="Material Transfer", warehouse_field="t_warehouse")
