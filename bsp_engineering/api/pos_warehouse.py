import frappe

from bsp_engineering.utils.pos_warehouse import (
	can_change_pos_warehouse,
	get_default_company,
	get_permitted_warehouse_names,
	resolve_pos_warehouse,
)


@frappe.whitelist()
def can_switch_pos_warehouse():
	return can_change_pos_warehouse()


@frappe.whitelist()
def get_pos_warehouses(company=None, pos_profile=None):
	"""Warehouses for POS, scoped to user permissions."""
	if pos_profile and isinstance(pos_profile, str):
		import json

		try:
			pos_profile = json.loads(pos_profile)
		except Exception:
			pos_profile = None

	if not company and isinstance(pos_profile, dict):
		company = pos_profile.get('company')

	if not company:
		company = get_default_company()

	names = get_permitted_warehouse_names(company=company)
	if not names:
		return []

	return frappe.get_all(
		'Warehouse',
		filters={'name': ['in', names]},
		fields=['name', 'warehouse_name'],
		order_by='warehouse_name asc',
	)


@frappe.whitelist()
def get_pos_default_warehouse(company=None, pos_profile=None):
	"""Default warehouse: POS Profile warehouse when permitted."""
	if pos_profile and isinstance(pos_profile, str):
		import json

		try:
			pos_profile = json.loads(pos_profile)
		except Exception:
			pos_profile = None

	if not company and isinstance(pos_profile, dict):
		company = pos_profile.get('company')

	return resolve_pos_warehouse(
		company=company,
		pos_profile=pos_profile if isinstance(pos_profile, dict) else None,
	)
