import frappe
from frappe.utils import cint


def sync_line_warehouse_from_source(doc, method=None):
	"""Align item/packed warehouse with Source Warehouse for stock posting."""
	source = doc.get('set_warehouse')
	if not source:
		return

	for row in doc.get('items') or []:
		if cint(row.get('is_stock_item')):
			row.warehouse = source

	for row in doc.get('packed_items') or []:
		row.warehouse = source
