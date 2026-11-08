import json

import frappe
from frappe import _
from frappe.core.page.permission_manager.permission_manager import (
	not_allowed_in_permission_manager,
)
from frappe.permissions import (
	AUTOMATIC_ROLES,
	add_permission,
	get_all_perms,
	setup_custom_perms,
)
from frappe.utils import cint

RIGHTS = ("read", "write", "create", "delete", "submit")
BASIC = ("select", "read", "write", "create", "submit", "cancel")
SIMPLE_RIGHTS = ("read", "write", "create", "delete")

# Short list the shop staff actually use. Labels stay plain.
SIMPLE_GROUPS = (
	(
		"Sales",
		(
			("Sales Invoice", "Sales Bill"),
			("Customer", "Customer"),
			("Payment Entry", "Payment"),
			("Delivery Note", "Delivery"),
		),
	),
	(
		"Purchase",
		(
			("Purchase Invoice", "Purchase Bill"),
			("Supplier", "Supplier"),
			("Purchase Order", "Purchase Order"),
			("Purchase Receipt", "Purchase Receipt"),
		),
	),
	(
		"Stock",
		(
			("Item", "Item"),
			("Warehouse", "Warehouse"),
			("Stock Entry", "Stock Move"),
			("Material Request", "Material Request"),
			("Material Transfer", "Material Transfer"),
			("Requisition", "Requisition"),
			("Production Requirement", "Production"),
		),
	),
	(
		"Accounts",
		(
			("Journal Entry", "Journal"),
			("BSP Daily Deposit", "Daily Deposit"),
			("Expense Claim", "Expense"),
		),
	),
	(
		"People",
		(
			("Employee", "Employee"),
			("User", "User"),
		),
	),
)


def _only_manager():
	frappe.only_for("System Manager")


@frappe.whitelist()
def get_role_permission_matrix(role):
	"""Read, write, create, delete, and submit for every DocType."""
	_only_manager()
	_validate_role(role)
	return _matrix(role)


@frappe.whitelist()
def set_role_permissions(role, changes):
	"""Save checkbox changes for one role."""
	_only_manager()
	_validate_role(role)
	if isinstance(changes, str):
		changes = json.loads(changes)
	if not isinstance(changes, list):
		frappe.throw(_("Changes must be a list"))
	for change in changes:
		_apply_change(role, change)
	return _matrix(role)


def _validate_role(role):
	if not role or not frappe.db.exists("Role", role):
		frappe.throw(_("Role {0} was not found").format(role))
	if role in AUTOMATIC_ROLES or role == "Administrator":
		frappe.throw(_("Role {0} cannot be edited here").format(role))


def _matrix(role):
	perms = _role_perms(role)
	groups = {}
	for doc in _doctypes():
		module = doc.module or _("Other")
		group = groups.setdefault(
			module, {"module": module, "label": _(module), "rows": []}
		)
		current = perms.get(doc.name, {})
		group["rows"].append(
			{
				"doctype": doc.name,
				"label": _(doc.name),
				"is_submittable": cint(doc.is_submittable),
				"perms": {right: cint(current.get(right)) for right in RIGHTS},
			}
		)
	ordered = sorted(groups.values(), key=lambda group: group["label"].casefold())
	for group in ordered:
		group["rows"].sort(key=lambda row: row["label"].casefold())
	return {"role": role, "groups": ordered}


def role_right_score(role):
	"""How many plain document rights this job already has."""
	perms = _role_perms(role)
	score = 0
	for _label, rows in SIMPLE_GROUPS:
		for doctype, _title in rows:
			current = perms.get(doctype) or {}
			score += sum(cint(current.get(right)) for right in SIMPLE_RIGHTS)
	return score


def get_simple_documents(role):
	"""Plain document list for the one Manage Permissions screen.

	Already-permitted doctypes (any View/Create/Update/Delete tick) sort to
	the top of each group so staff see what the Role Profile / job already
	allows without hunting.
	"""
	_only_manager()
	_validate_role(role)
	perms = _role_perms(role)
	groups = []
	for label, rows in SIMPLE_GROUPS:
		built = []
		for doctype, title in rows:
			if not frappe.db.exists("DocType", doctype):
				continue
			current = perms.get(doctype, {})
			row_perms = {
				right: cint(current.get(right)) for right in SIMPLE_RIGHTS
			}
			built.append(
				{
					"doctype": doctype,
					"label": _(title),
					"is_submittable": cint(
						frappe.db.get_value("DocType", doctype, "is_submittable")
					),
					"perms": row_perms,
					"has_perm": 1 if any(row_perms.values()) else 0,
				}
			)
		built.sort(
			key=lambda row: (
				0 if row["has_perm"] else 1,
				(row["label"] or "").casefold(),
			)
		)
		if built:
			groups.append({"label": _(label), "rows": built})
	return groups


def _role_perms(role):
	found = {}
	for perm in get_all_perms(role):
		if cint(perm.permlevel) or cint(perm.if_owner):
			continue
		found[perm.parent] = {right: cint(perm.get(right)) for right in RIGHTS}
	return found


def _doctypes():
	active_domains = frappe.get_active_domains()
	return frappe.get_all(
		"DocType",
		filters={
			"istable": 0,
			"name": ["not in", not_allowed_in_permission_manager],
		},
		or_filters={
			"ifnull(restrict_to_domain, '')": "",
			"restrict_to_domain": ["in", active_domains],
		},
		fields=["name", "module", "is_submittable"],
		limit_page_length=0,
	)


def _apply_change(role, change):
	doctype = change.get("doctype")
	if not doctype or not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} was not found").format(doctype))
	meta = frappe.get_meta(doctype)
	wanted = _normalize(change.get("perms") or {}, cint(meta.is_submittable))
	setup_custom_perms(doctype)
	name = frappe.db.get_value(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
	)
	if not any(wanted.values()):
		_clear_rights(doctype, name)
		return
	if not name:
		add_permission(doctype, role, 0, "read")
		name = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
		)
	doc = frappe.get_doc("Custom DocPerm", name)
	for right in RIGHTS:
		doc.set(right, wanted[right])
	if not wanted["submit"]:
		doc.cancel = 0
		doc.amend = 0
	doc.save()
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype

	validate_permissions_for_doctype(doctype)
	frappe.clear_cache(doctype=doctype)


def _normalize(perms, is_submittable):
	out = {right: cint(perms.get(right)) for right in RIGHTS}
	if not is_submittable:
		out["submit"] = 0
	if out["submit"]:
		out["write"] = 1
	if out["write"] or out["create"] or out["delete"] or out["submit"]:
		out["read"] = 1
	if not out["read"]:
		return {right: 0 for right in RIGHTS}
	return out


def _clear_rights(doctype, name):
	if not name:
		return
	doc = frappe.get_doc("Custom DocPerm", name)
	for right in RIGHTS:
		doc.set(right, 0)
	doc.cancel = 0
	doc.amend = 0
	if any(cint(doc.get(right)) for right in BASIC):
		doc.save()
	else:
		others = frappe.db.count(
			"Custom DocPerm", {"parent": doctype, "name": ["!=", name]}
		)
		if not others:
			doc.read = 1
			doc.save()
			frappe.throw(
				_("At least one permission rule must remain for {0}").format(doctype)
			)
		frappe.delete_doc("Custom DocPerm", name)
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype

	validate_permissions_for_doctype(doctype, for_remove=True)
	frappe.clear_cache(doctype=doctype)
