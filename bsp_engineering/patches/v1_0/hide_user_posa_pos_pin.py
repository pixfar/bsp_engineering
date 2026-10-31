# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Hide POS PIN on User — assignment is driven by POS Profile instead."""
	name = "User-posa_pos_pin"
	if not frappe.db.exists("Custom Field", name):
		return
	frappe.db.set_value("Custom Field", name, "hidden", 1, update_modified=False)
