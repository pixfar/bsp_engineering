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


def _get_user_permission_warehouses(user=None):
	user = user or frappe.session.user
	return frappe.get_all(
		'User Permission',
		filters={'user': user, 'allow': 'Warehouse'},
		fields=['for_value', 'is_default'],
		order_by='is_default desc, creation asc',
	)


def _resolve_warehouse_name(name, company=None):
	if not name:
		return None
	names = _query_warehouses([name], company=company)
	if names:
		return names[0]
	expanded = _query_warehouses(
		_expand_warehouse_permission_names([name]),
		company=company,
	)
	return expanded[0] if expanded else None


def get_user_default_warehouse(company=None, user=None):
	"""Return the user's default warehouse from User Permission."""
	user = user or frappe.session.user
	if user == 'Administrator':
		return None

	perms = _get_user_permission_warehouses(user=user)
	if not perms:
		return None

	for perm in perms:
		if not perm.is_default:
			continue
		resolved = _resolve_warehouse_name(perm.for_value, company=company)
		if resolved:
			return resolved

	for perm in perms:
		resolved = _resolve_warehouse_name(perm.for_value, company=company)
		if resolved:
			return resolved

	return None


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
		permitted = [
			p.for_value
			for p in _get_user_permission_warehouses()
			if p.for_value
		]

	expanded = _expand_warehouse_permission_names(permitted)
	if not expanded:
		return []

	if not include_groups:
		default_wh = get_user_default_warehouse(company=company)
		if default_wh:
			others = _query_warehouses(
				expanded, company=company, include_groups=False
			)
			ordered = [default_wh] + [n for n in others if n != default_wh]
			return ordered

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


def _user_has_warehouse_restrictions(user=None):
	user = user or frappe.session.user
	if user == 'Administrator':
		return False
	return bool(
		frappe.db.exists(
			'User Permission',
			{'user': user, 'allow': 'Warehouse'},
		)
	)


def resolve_pos_warehouse(warehouse=None, company=None, pos_profile=None):
	"""Pick warehouse: explicit > user default > POS profile > permitted."""
	restricted = not can_change_pos_warehouse()
	if restricted:
		warehouse = None

	if warehouse:
		validate_warehouse_permission(warehouse, company=company)
		return warehouse

	if restricted and _user_has_warehouse_restrictions():
		default_wh = get_user_default_warehouse(company=company)
		if default_wh:
			return default_wh

	permitted = get_permitted_warehouse_names(company=company)
	profile_wh = None
	if isinstance(pos_profile, dict):
		profile_wh = pos_profile.get('warehouse')

	if profile_wh:
		if restricted and profile_wh not in permitted:
			return permitted[0] if permitted else None
		validate_warehouse_permission(profile_wh, company=company)
		return profile_wh

	if not permitted:
		return None

	return permitted[0]
