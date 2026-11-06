# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
from frappe.modules.import_file import import_file_by_path

BANGLA = "BSP Sales Invoice Bangla"
LEGACY_FORMATS = ("", "Standard", "BSP Sales Invoice")


def execute():
	"""Install the Bangla and English sales invoice formats and make Bangla the default."""
	for scrub in ("bsp_sales_invoice_bangla", "bsp_sales_invoice_english"):
		path = frappe.get_module_path(
			"Bsp Engineering", "print_format", scrub, f"{scrub}.json"
		)
		import_file_by_path(path, force=True)

	if frappe.db.exists("DocType", "POS Profile"):
		_set_profile_format("print_format")
		if frappe.db.has_column("POS Profile", "print_format_for_online"):
			_set_profile_format("print_format_for_online")

	setter_name = "Sales Invoice-main-default_print_format"
	if frappe.db.exists("Property Setter", setter_name):
		frappe.db.set_value("Property Setter", setter_name, "value", BANGLA, update_modified=False)
	else:
		frappe.make_property_setter(
			"Sales Invoice",
			None,
			"default_print_format",
			BANGLA,
			"Data",
			for_doctype=True,
		)


def _set_profile_format(fieldname):
	placeholders = ", ".join(["%s"] * len(LEGACY_FORMATS))
	frappe.db.sql(
		f"""
		UPDATE `tabPOS Profile`
		SET `{fieldname}` = %s
		WHERE IFNULL(`{fieldname}`, '') IN ({placeholders})
		""",
		(BANGLA, *LEGACY_FORMATS),
	)
