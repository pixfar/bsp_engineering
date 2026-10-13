import frappe
from frappe.utils import cint

from bsp_engineering.utils.pos_warehouse import (
	can_change_pos_warehouse,
	resolve_pos_warehouse,
)

POS_SALE_DOCTYPES = ('Sales Invoice', 'POS Invoice')


def _resolve_locked_source(doc):
	profile_name = doc.get('pos_profile')
	profile = None
	if profile_name:
		profile = frappe.db.get_value(
			'POS Profile',
			profile_name,
			['warehouse', 'company'],
			as_dict=True,
		)
	return resolve_pos_warehouse(
		company=doc.get('company') or (profile or {}).get('company'),
		pos_profile=profile,
	)


def sync_line_warehouse_from_source(doc, method=None):
	"""Align item/packed warehouse with Source Warehouse for stock posting."""
	if doc.doctype in POS_SALE_DOCTYPES and doc.get('pos_profile'):
		_sync_pos_sale(doc)
		return

	if not can_change_pos_warehouse():
		source = _resolve_locked_source(doc)
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


def _sync_pos_sale(doc):
	"""POS sale: stock lines follow the sale warehouse, non-stock lines get none,
	and the payment account is one of that warehouse's Cash / Bank Accounts.

	Stock/non-stock comes from the Item master (row.is_stock_item is not a
	Sales Invoice Item field and is missing on every row loaded from the
	database). The selected warehouse is read from the flag captured in
	before_validate, because ERPNext's own validate blanks set_warehouse when
	the lines' warehouses differ -- which a non-stock line always causes.
	"""
	from posawesome.posawesome.utils.invoice_warehouse import (
		SALE_WAREHOUSE_FLAG,
		apply_sale_cash_account,
		apply_sale_warehouse,
	)

	if not can_change_pos_warehouse():
		source = _resolve_locked_source(doc)
	else:
		source = doc.flags.get(SALE_WAREHOUSE_FLAG) or doc.get('set_warehouse')

	if source:
		doc.flags[SALE_WAREHOUSE_FLAG] = source
	apply_sale_warehouse(doc, source)
	apply_sale_cash_account(doc, source)
