import frappe

POS_WAREHOUSE_SWITCH_ROLE = 'System Manager'


def get_default_company():
	return frappe.db.get_default('company') or frappe.defaults.get_global_default(
		'company'
	)


def can_change_pos_warehouse(user=None):
	"""System Manager may switch among all company warehouses."""
	user = user or frappe.session.user
	return POS_WAREHOUSE_SWITCH_ROLE in frappe.get_roles(user)


def _expand_warehouse_permission_names(names):
	"""Include nested-set child warehouses (same as Frappe User Permission)."""
	expanded = set()
	for name in names or []:
		if not name:
			continue
		expanded.add(name)
		if frappe.db.get_value('Warehouse', name, 'is_group'):
			expanded.update(frappe.db.get_descendants('Warehouse', name) or [])
	return list(expanded)


def _query_warehouses(names, company=None, include_groups=False):
	filters = {'disabled': 0, 'name': ['in', names]}
	if not include_groups:
		filters['is_group'] = 0
	if company:
		with_company = frappe.get_all(
			'Warehouse',
			filters={**filters, 'company': company},
			pluck='name',
			order_by='warehouse_name asc, name asc',
		)
		if with_company:
			return with_company
	return frappe.get_all(
		'Warehouse',
		filters=filters,
		pluck='name',
		order_by='warehouse_name asc, name asc',
	)


def get_permitted_warehouse_names(company=None, include_groups=False):
	"""Return warehouse names the current user may use in POS."""
	base_filters = {'disabled': 0}
	if not include_groups:
		base_filters['is_group'] = 0
	if company:
		base_filters['company'] = company

	if frappe.session.user == 'Administrator':
		return frappe.get_all(
			'Warehouse',
			filters=base_filters,
			pluck='name',
			order_by='warehouse_name asc, name asc',
		)

	has_user_perm_rows = frappe.db.exists(
		'User Permission',
		{'user': frappe.session.user, 'allow': 'Warehouse'},
	)

	if not has_user_perm_rows:
		return frappe.get_all(
			'Warehouse',
			filters=base_filters,
			pluck='name',
			order_by='warehouse_name asc, name asc',
		)

	try:
		from frappe.core.doctype.user_permission.user_permission import (
			get_permitted_documents,
		)

		permitted = get_permitted_documents('Warehouse') or []
	except Exception:
		permitted = frappe.get_all(
			'User Permission',
			filters={'user': frappe.session.user, 'allow': 'Warehouse'},
			pluck='for_value',
		)

	expanded = _expand_warehouse_permission_names(permitted)
	if not expanded:
		return []

	names = _query_warehouses(
		expanded, company=company, include_groups=include_groups
	)
	if names or include_groups:
		return names

	return _query_warehouses(expanded, company=company, include_groups=True)


def validate_warehouse_permission(warehouse, company=None):
	if not warehouse:
		return
	if warehouse not in get_permitted_warehouse_names(company=company):
		frappe.throw(
			frappe._('You do not have permission to use warehouse {0}').format(
				warehouse
			),
			frappe.PermissionError,
		)


def resolve_pos_warehouse(warehouse=None, company=None, pos_profile=None):
	"""Pick warehouse: explicit > POS profile > permitted default."""
	if warehouse:
		validate_warehouse_permission(warehouse, company=company)
		return warehouse

	if isinstance(pos_profile, dict) and pos_profile.get('warehouse'):
		wh = pos_profile.get('warehouse')
		validate_warehouse_permission(wh, company=company)
		return wh

	permitted = get_permitted_warehouse_names(company=company)
	if not permitted:
		return None

	if pos_profile and isinstance(pos_profile, dict):
		profile_wh = pos_profile.get('warehouse')
		if profile_wh and profile_wh in permitted:
			return profile_wh

	return permitted[0]
