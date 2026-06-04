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
	"""Warehouses for POS switcher (System Manager only)."""
	if not can_change_pos_warehouse():
		return []
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

	profile = pos_profile if isinstance(pos_profile, dict) else None

	names = get_permitted_warehouse_names(company=company, pos_profile=profile)
	if not names:
		return []

	rows = frappe.get_all(
		'Warehouse',
		filters={'name': ['in', names]},
		fields=['name', 'warehouse_name'],
	)
	by_name = {row.name: row for row in rows}
	return [by_name[name] for name in names if name in by_name]


@frappe.whitelist()
def get_pos_active_warehouse(company=None, pos_profile=None):
	"""Transaction warehouse with display label (read-only for non-SM)."""
	if pos_profile and isinstance(pos_profile, str):
		import json

		try:
			pos_profile = json.loads(pos_profile)
		except Exception:
			pos_profile = None

	if not company and isinstance(pos_profile, dict):
		company = pos_profile.get('company')

	name = resolve_pos_warehouse(
		company=company,
		pos_profile=pos_profile if isinstance(pos_profile, dict) else None,
	)
	if not name:
		return {}

	row = frappe.db.get_value(
		'Warehouse', name, ['name', 'warehouse_name'], as_dict=True
	)
	return row or {'name': name, 'warehouse_name': name}


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
