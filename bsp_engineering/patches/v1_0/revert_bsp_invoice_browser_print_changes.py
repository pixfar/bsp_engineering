# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe

from bsp_engineering.utils.invoice_print_revert import (
	BSP_INVOICE_PRINT_FORMATS,
	ORIGINAL_PRINT_CSS,
	revert_bsp_invoice_html,
)


def execute():
	for name in BSP_INVOICE_PRINT_FORMATS:
		if not frappe.db.exists('Print Format', name):
			continue

		html = frappe.db.get_value('Print Format', name, 'html') or ''
		frappe.db.set_value(
			'Print Format',
			name,
			{
				'css': ORIGINAL_PRINT_CSS,
				'html': revert_bsp_invoice_html(html),
			},
			update_modified=False,
		)
