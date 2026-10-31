import frappe

from bsp_engineering.utils.pos_warehouse import (
	can_change_pos_warehouse,
	get_default_company,
	get_permitted_warehouse_names,
	get_user_default_warehouse,
	resolve_pos_warehouse,
)


def _parse_pos_profile(pos_profile):
	if pos_profile and isinstance(pos_profile, str):
		import json

		try:
			return json.loads(pos_profile)
		except Exception:
			return None
	return pos_profile if isinstance(pos_profile, dict) else None


@frappe.whitelist()
def can_switch_pos_warehouse():
	return can_change_pos_warehouse()


@frappe.whitelist()
def get_pos_warehouses(company=None, pos_profile=None):
	"""Warehouses for the POS warehouse switcher.

	Respects Warehouse User Permissions for every role (including BSP Admin /
	System Manager / BSP Viewer). Returns an empty list when the user may not
	switch warehouses.
	"""
	if not can_change_pos_warehouse():
		return {
			'warehouses': [],
			'default_warehouse': None,
			'can_switch': False,
		}

	profile = _parse_pos_profile(pos_profile)
	if not company and profile:
		company = profile.get('company')
	if not company:
		company = get_default_company()

	permitted = get_permitted_warehouse_names(
		company=company, pos_profile=profile
	)
	if not permitted:
		return {
			'warehouses': [],
			'default_warehouse': None,
			'can_switch': False,
		}

	base_filters = {
		'disabled': 0,
		'is_group': 0,
		'name': ['in', permitted],
	}
	if company:
		base_filters['company'] = company

	# Prefer POS-visible warehouses; fall back to all permitted leaves when
	# none of the user's warehouses carry custom_show_on_pos.
	show_filters = dict(base_filters)
	if frappe.get_meta('Warehouse').has_field('custom_show_on_pos'):
		show_filters['custom_show_on_pos'] = 1

	warehouses = frappe.get_all(
		'Warehouse',
		filters=show_filters,
		fields=['name', 'warehouse_name'],
		order_by='warehouse_name asc, name asc',
	)
	if not warehouses:
		warehouses = frappe.get_all(
			'Warehouse',
			filters=base_filters,
			fields=['name', 'warehouse_name'],
			order_by='warehouse_name asc, name asc',
		)

	# Keep the User Permission / get_permitted order (default first).
	by_name = {row.name: row for row in warehouses}
	ordered = [by_name[name] for name in permitted if name in by_name]

	default_wh = get_user_default_warehouse(company=company)
	if not default_wh and profile:
		default_wh = profile.get('warehouse')
	if default_wh and default_wh not in by_name:
		default_wh = ordered[0].name if ordered else None
	if not default_wh and ordered:
		default_wh = ordered[0].name

	return {
		'warehouses': ordered,
		'default_warehouse': default_wh,
		'can_switch': len(ordered) > 1,
	}


@frappe.whitelist()
def get_pos_active_warehouse(company=None, pos_profile=None):
	"""Transaction warehouse with display label (read-only for non-switchers)."""
	profile = _parse_pos_profile(pos_profile)
	if not company and profile:
		company = profile.get('company')

	name = resolve_pos_warehouse(
		company=company,
		pos_profile=profile,
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
	profile = _parse_pos_profile(pos_profile)
	if not company and profile:
		company = profile.get('company')

	return resolve_pos_warehouse(
		company=company,
		pos_profile=profile,
	)
