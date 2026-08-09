# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""DO Number lookups (posawesome.posawesome.api.purchase_invoices
	.get_items_by_do_number, called every time a DO Number is typed on the
	Sales or Material Transfer screen) filter Purchase Invoice by an exact
	``custom_do_number`` match -- without an index that's a full table scan
	on every keystroke's lookup. Add one for each doctype that carries the
	field; also flip each Custom Field's own "search_index" checkbox so
	Customize Form and a future `bench export-fixtures` both reflect it.

	frappe.db.add_index is idempotent (checks information_schema before
	creating), so this is safe to run again.
	"""
	for doctype in ("Sales Invoice", "Purchase Invoice"):
		if not frappe.db.has_column(doctype, "custom_do_number"):
			continue
		frappe.db.add_index(doctype, ["custom_do_number"])
		frappe.db.set_value(
			"Custom Field", f"{doctype}-custom_do_number", "search_index", 1, update_modified=False
		)
