import json

import frappe
from frappe import _
from frappe.utils import cint

ALLOWED = ("Warehouse", "Territory", "Employee", "User")

_SPECS = (
	{
		"doctype": "Warehouse",
		"filters": {"disabled": 0, "is_group": 0},
		"title_field": "warehouse_name",
	},
	{
		"doctype": "Territory",
		"filters": {"is_group": 0},
		"title_field": None,
	},
	{
		"doctype": "Employee",
		"filters": {"status": "Active"},
		"title_field": "employee_name",
	},
	{
		"doctype": "User",
		"filters": {"enabled": 1, "name": ["!=", "Guest"]},
		"title_field": "full_name",
	},
)


def _only_manager():
	frappe.only_for("System Manager")


_SKIP_ROLES = {"All", "Guest", "Desk User", "Administrator"}
_PREFERRED_ROLES = (
	"POS User",
	"Sales User",
	"Purchase User",
	"Stock User",
	"Accounts User",
)


def _pick_role(roles, requested):
	if requested and requested in roles:
		return requested
	for name in _PREFERRED_ROLES:
		if name in roles:
			return name
	return roles[0] if roles else None


def _roles_for_user(user):
	"""Jobs for the Role Permissions tab: Role Profile roles when set."""
	profile = frappe.db.get_value("User", user, "role_profile_name")
	if profile and frappe.db.exists("Role Profile", profile):
		roles = [
			row.role
			for row in frappe.get_all(
				"Has Role",
				filters={
					"parent": profile,
					"parenttype": "Role Profile",
				},
				fields=["role"],
				order_by="idx asc",
			)
			if row.role and row.role not in _SKIP_ROLES
		]
		if roles:
			return roles, profile
	roles = [
		name
		for name in frappe.get_roles(user)
		if name not in _SKIP_ROLES
	]
	return roles, profile


@frappe.whitelist()
def get_manage_permissions(user, role=None):
	"""One screen: places for this person, document rights for one job."""
	_only_manager()
	if not user or not frappe.db.exists("User", user):
		frappe.throw(_("User {0} was not found").format(user))
	roles, role_profile = _roles_for_user(user)
	chosen = _pick_role(roles, role)
	documents = []
	if chosen:
		from bsp_engineering.api.role_permission import get_simple_documents

		documents = get_simple_documents(chosen)
	info = _matrix(user)
	return {
		"user": user,
		"full_name": info["full_name"],
		"role_profile": role_profile,
		"roles": roles,
		"role": chosen,
		"places": info["groups"],
		"documents": documents,
	}


@frappe.whitelist()
def get_permission_matrix(user):
	"""Checkbox rows for one user's document permissions."""
	_only_manager()
	if not user or not frappe.db.exists("User", user):
		frappe.throw(_("User {0} was not found").format(user))
	return _matrix(user)


@frappe.whitelist()
def set_user_permissions(user, changes):
	"""Create or delete User Permission rows from checkbox changes."""
	_only_manager()
	if isinstance(changes, str):
		changes = json.loads(changes)
	if not user or not frappe.db.exists("User", user):
		frappe.throw(_("User {0} was not found").format(user))
	if not isinstance(changes, list):
		frappe.throw(_("Changes must be a list"))

	ordered = sorted(changes, key=lambda row: cint(row.get("is_default")))
	touched = set()
	cleared_defaults = {}
	for change in ordered:
		_apply_change(user, change)
		allow = change.get("allow")
		touched.add(allow)
		if cint(change.get("allowed")) and not cint(change.get("is_default")):
			cleared_defaults.setdefault(allow, set()).add(change.get("for_value"))
	for allow in touched:
		_ensure_default(user, allow, cleared_defaults.get(allow, set()))
	return _matrix(user)


def _matrix(user):
	existing = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": ["in", list(ALLOWED)]},
		fields=["allow", "for_value", "is_default"],
		limit_page_length=0,
	)
	by_allow = {}
	for row in existing:
		by_allow.setdefault(row.allow, {})[row.for_value] = cint(row.is_default)

	groups = []
	for spec in _SPECS:
		selected = by_allow.get(spec["doctype"], {})
		groups.append(
			{
				"allow": spec["doctype"],
				"label": _(spec["doctype"]),
				"rows": _rows(spec, selected),
			}
		)
	return {
		"user": user,
		"full_name": frappe.db.get_value("User", user, "full_name") or user,
		"groups": groups,
	}


def _rows(spec, selected):
	title_field = spec["title_field"]
	fields = ["name"] + ([title_field] if title_field else [])
	docs = frappe.get_all(
		spec["doctype"],
		filters=spec["filters"],
		fields=fields,
		limit_page_length=0,
	)
	seen = {doc.name for doc in docs}
	for value in selected:
		if value not in seen and frappe.db.exists(spec["doctype"], value):
			extra = {"name": value}
			if title_field:
				extra[title_field] = frappe.db.get_value(
					spec["doctype"], value, title_field
				)
			docs.append(extra)

	rows = []
	for doc in docs:
		label = (title_field and doc.get(title_field)) or doc.name
		rows.append(
			{
				"value": doc.name,
				"label": label,
				"allowed": 1 if doc.name in selected else 0,
				"is_default": 1 if selected.get(doc.name) else 0,
			}
		)
	rows.sort(key=lambda row: (row["label"] or "").lower())
	return rows


def _apply_change(user, change):
	allow = change.get("allow")
	for_value = change.get("for_value")
	if allow not in ALLOWED or not for_value:
		frappe.throw(_("Invalid permission change"))
	if not frappe.db.exists(allow, for_value):
		frappe.throw(_("{0} {1} was not found").format(allow, for_value))

	allowed = cint(change.get("allowed"))
	is_default = cint(change.get("is_default")) if allowed else 0
	names = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": allow, "for_value": for_value},
		pluck="name",
	)
	if not allowed:
		for name in names:
			frappe.delete_doc("User Permission", name)
		return

	if is_default:
		_clear_other_defaults(user, allow, for_value)
	if not names:
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": user,
				"allow": allow,
				"for_value": for_value,
				"apply_to_all_doctypes": 1,
				"is_default": is_default,
			}
		).insert()
		return

	doc = frappe.get_doc("User Permission", names[0])
	if cint(doc.is_default) != is_default:
		doc.is_default = is_default
		doc.save()


def _clear_other_defaults(user, allow, for_value):
	others = frappe.get_all(
		"User Permission",
		filters={
			"user": user,
			"allow": allow,
			"is_default": 1,
			"for_value": ["!=", for_value],
		},
		pluck="name",
	)
	for name in others:
		doc = frappe.get_doc("User Permission", name)
		doc.is_default = 0
		doc.save()


def _ensure_default(user, allow, skip_values):
	if allow not in ALLOWED:
		return
	rows = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": allow},
		fields=["name", "for_value", "is_default"],
		order_by="creation asc",
	)
	if not rows or any(cint(row.is_default) for row in rows):
		return
	pick = next(
		(row for row in rows if row.for_value not in skip_values),
		rows[0],
	)
	doc = frappe.get_doc("User Permission", pick.name)
	doc.is_default = 1
	doc.save()
