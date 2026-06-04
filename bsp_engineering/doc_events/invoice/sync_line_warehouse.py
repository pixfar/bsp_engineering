import frappe
from frappe.utils import cint

from bsp_engineering.utils.pos_warehouse import (
	can_change_pos_warehouse,
	resolve_pos_warehouse,
)


def sync_line_warehouse_from_source(doc, method=None):
	"""Align item/packed warehouse with Source Warehouse for stock posting."""
	if not can_change_pos_warehouse():
		profile_name = doc.get('pos_profile')
		profile = None
		if profile_name:
			profile = frappe.db.get_value(
				'POS Profile',
				profile_name,
				['warehouse', 'company'],
				as_dict=True,
			)
		source = resolve_pos_warehouse(
			company=doc.get('company') or (profile or {}).get('company'),
			pos_profile=profile,
		)
		if source:
			doc.set_warehouse = source
	else:
		source = doc.get('set_warehouse')

	if not source:
		return

	for row in doc.get('items') or []:
		if cint(row.get('is_stock_item')):
			row.warehouse = source

	for row in doc.get('packed_items') or []:
		row.warehouse = source
