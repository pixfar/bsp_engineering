# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

from bsp_engineering.utils.top_party_reports import top_suppliers


def execute(filters=None):
	return top_suppliers(filters)
