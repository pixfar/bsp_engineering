import json

import frappe

POS_WAREHOUSE_SWITCH_ROLE = 'System Manager'
# BSP Admin / BSP Viewer / System Manager may switch showrooms and see every
# warehouse by default (see posawesome warehouse_doc_permissions). Explicit
# Warehouse User Permissions always override that and narrow them to the
# permitted warehouses only -- see get_user_permission_warehouse_names /
# get_permitted_warehouse_names.
POS_WAREHOUSE_UNRESTRICTED_ROLES = {POS_WAREHOUSE_SWITCH_ROLE, 'BSP Admin', 'BSP Viewer'}


def get_default_company():
	return frappe.db.get_default('company') or frappe.defaults.get_global_default(
		'company'
	)


def can_change_pos_warehouse(user=None):
	"""Whether the POS warehouse switcher should be enabled.

	True for System Manager / BSP Admin / BSP Viewer (all showrooms, or only
	their Warehouse User Permissions when those rows exist), and for any user
	with two or more explicit Warehouse User Permissions so they can swap
	among those showrooms. Everyone else stays locked to their POS Profile
	warehouse (see should_use_pos_profile_warehouse_only).
	"""
	user = user or frappe.session.user
	if user == 'Administrator':
		return True
	if POS_WAREHOUSE_UNRESTRICTED_ROLES.intersection(frappe.get_roles(user)):
		return True
	up_names = get_user_permission_warehouse_names(user=user)
	return bool(up_names and len(up_names) > 1)


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


def get_user_permission_warehouse_names(
	user=None, company=None, include_groups=False
):
	"""Warehouses from explicit Warehouse User Permissions, expanded for
	group warehouses. Returns None when the user has no such rows (so role-
	based all-showroom access still applies for BSP Admin / System Manager /
	BSP Viewer). Empty list means they have permission rows that resolve to
	no usable warehouse."""
	user = user or frappe.session.user
	if user == 'Administrator':
		return None

	perms = _get_user_permission_warehouses(user=user)
	if not perms:
		return None

	try:
		from frappe.core.doctype.user_permission.user_permission import (
			get_permitted_documents,
		)

		# get_permitted_documents reads the current session user; when
		# resolving for another user fall back to the raw permission rows.
		if user == frappe.session.user:
			permitted = get_permitted_documents('Warehouse') or [
				p.for_value for p in perms if p.for_value
			]
		else:
			permitted = [p.for_value for p in perms if p.for_value]
	except Exception:
		permitted = [p.for_value for p in perms if p.for_value]

	expanded = _expand_warehouse_permission_names(permitted)
	if not expanded:
		return []

	if not include_groups:
		default_wh = get_user_default_warehouse(company=company, user=user)
		if default_wh and user == frappe.session.user:
			others = _query_warehouses(
				expanded, company=company, include_groups=False
			)
			return [default_wh] + [n for n in others if n != default_wh]

	names = _query_warehouses(
		expanded, company=company, include_groups=include_groups
	)
	if names or include_groups:
		return names
	return _query_warehouses(expanded, company=company, include_groups=True)


def _user_has_default_warehouse_permission(user=None):
	user = user or frappe.session.user
	if user == 'Administrator':
		return False
	return bool(
		frappe.db.exists(
			'User Permission',
			{
				'user': user,
				'allow': 'Warehouse',
				'is_default': 1,
			},
		)
	)


def should_use_pos_profile_warehouse_only(user=None):
	"""Lock sales to POS Profile warehouse when unrestricted or no default perm."""
	if can_change_pos_warehouse(user):
		return False
	if not _user_has_warehouse_restrictions(user):
		return True
	if not _user_has_default_warehouse_permission(user):
		return True
	return False


def get_pos_profile_warehouse(pos_profile=None, company=None):
	if isinstance(pos_profile, dict):
		wh = pos_profile.get('warehouse')
	elif isinstance(pos_profile, str) and pos_profile.strip():
		wh = frappe.db.get_value('POS Profile', pos_profile.strip(), 'warehouse')
	else:
		wh = None

	if not wh:
		try:
			from bsp_engineering.posawesome.profile import get_active_pos_profile

			profile = get_active_pos_profile() or {}
			wh = profile.get('warehouse')
		except Exception:
			wh = None

	if wh and company:
		return _resolve_warehouse_name(wh, company=company) or wh
	return wh


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

	return None


def get_permitted_warehouse_names(
	company=None, include_groups=False, pos_profile=None
):
	"""Return warehouse names the current user may use in POS.

	Warehouse User Permissions always win — including for BSP Admin /
	System Manager / BSP Viewer who otherwise see every showroom.
	"""
	if should_use_pos_profile_warehouse_only():
		profile_wh = get_pos_profile_warehouse(
			pos_profile=pos_profile, company=company
		)
		return [profile_wh] if profile_wh else []

	up_names = get_user_permission_warehouse_names(
		company=company, include_groups=include_groups
	)
	if up_names is not None:
		return up_names

	base_filters = {'disabled': 0}
	if not include_groups:
		base_filters['is_group'] = 0
	if company:
		base_filters['company'] = company

	# No Warehouse User Permission: privileged roles (and anyone else who
	# reaches here) see the full company warehouse list.
	return frappe.get_all(
		'Warehouse',
		filters=base_filters,
		pluck='name',
		order_by='warehouse_name asc, name asc',
	)


def validate_warehouse_permission(warehouse, company=None, pos_profile=None):
	if not warehouse:
		return

	if should_use_pos_profile_warehouse_only():
		profile_wh = get_pos_profile_warehouse(
			pos_profile=pos_profile, company=company
		)
		if profile_wh and warehouse != profile_wh:
			frappe.throw(
				frappe._(
					'You may only sell from warehouse {0} assigned to your POS Profile'
				).format(profile_wh),
				frappe.PermissionError,
			)
		return

	if warehouse not in get_permitted_warehouse_names(
		company=company, pos_profile=pos_profile
	):
		frappe.throw(
			frappe._('You do not have permission to use warehouse {0}').format(
				warehouse
			),
			frappe.PermissionError,
		)


def inject_warehouse_into_pos_profile(pos_profile, warehouse):
	if isinstance(pos_profile, str):
		try:
			profile = json.loads(pos_profile)
		except Exception:
			profile = {}
		profile['warehouse'] = warehouse
		return json.dumps(profile)

	if isinstance(pos_profile, dict):
		profile = dict(pos_profile)
		profile['warehouse'] = warehouse
		return profile

	return pos_profile


def prepare_pos_profile_for_stock(pos_profile, company=None, warehouse=None):
	"""Resolve warehouse permissions and inject into POS profile payload."""
	profile = {}
	if isinstance(pos_profile, dict):
		profile = pos_profile
	elif isinstance(pos_profile, str) and pos_profile.strip():
		try:
			profile = json.loads(pos_profile)
		except Exception:
			profile = {}

	if not company:
		company = profile.get('company') or get_default_company()

	if can_change_pos_warehouse() and warehouse:
		target = warehouse
	else:
		if not can_change_pos_warehouse():
			warehouse = None
		target = warehouse or resolve_pos_warehouse(
			company=company,
			pos_profile=profile,
		)

	if not target:
		return pos_profile, None

	validate_warehouse_permission(
		target, company=company, pos_profile=profile
	)
	return inject_warehouse_into_pos_profile(pos_profile, target), target


def resolve_pos_warehouse(warehouse=None, company=None, pos_profile=None):
	"""Pick warehouse: explicit > user default perm > POS profile (locked users)."""
	restricted = not can_change_pos_warehouse()
	if restricted:
		warehouse = None

	if warehouse:
		validate_warehouse_permission(
			warehouse, company=company, pos_profile=pos_profile
		)
		return warehouse

	if restricted and should_use_pos_profile_warehouse_only():
		profile_wh = get_pos_profile_warehouse(
			pos_profile=pos_profile, company=company
		)
		if profile_wh:
			return profile_wh
		return None

	if restricted and _user_has_warehouse_restrictions():
		default_wh = get_user_default_warehouse(company=company)
		if default_wh:
			return default_wh

	permitted = get_permitted_warehouse_names(
		company=company, pos_profile=pos_profile
	)
	profile_wh = get_pos_profile_warehouse(
		pos_profile=pos_profile, company=company
	)

	if profile_wh:
		if restricted and profile_wh not in permitted:
			return permitted[0] if permitted else None
		validate_warehouse_permission(
			profile_wh, company=company, pos_profile=pos_profile
		)
		return profile_wh

	if not permitted:
		return None

	return permitted[0]
