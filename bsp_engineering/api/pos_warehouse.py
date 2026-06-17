import frappe

from bsp_engineering.utils.pos_warehouse import (
	can_change_pos_warehouse,
	get_default_company,
	get_permitted_warehouse_names,
	get_user_default_warehouse,
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

	# System Managers see ALL POS-enabled warehouses, not limited by User Permission rows
	filters = {'disabled': 0, 'is_group': 0, 'custom_show_on_pos': 1}
	if company:
		filters['company'] = company

	warehouses = frappe.get_all(
		'Warehouse',
		filters=filters,
		fields=['name', 'warehouse_name'],
		order_by='warehouse_name asc, name asc',
	)

	# Default: User Permission default warehouse first, fall back to POS profile warehouse
	default_wh = get_user_default_warehouse(company=company)
	if not default_wh and profile:
		default_wh = profile.get('warehouse')

	return {
		'warehouses': warehouses,
		'default_warehouse': default_wh,
	}


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
