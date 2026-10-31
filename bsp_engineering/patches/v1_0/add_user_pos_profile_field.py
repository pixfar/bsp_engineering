# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Add User.posa_pos_profile and backfill from POS Profile Applicable for Users.

Does not create or cancel POS Opening Shifts — existing open shifts stay as-is.
Shift lifecycle runs only when the User field changes after this migration.
"""

import frappe


FIELDNAME = "posa_pos_profile"
CUSTOM_FIELD_NAME = f"User-{FIELDNAME}"


def execute():
	_ensure_custom_field()
	_migrate_from_pos_profile_users()


def _ensure_custom_field():
	if frappe.db.exists("Custom Field", CUSTOM_FIELD_NAME):
		return

	insert_after = "posa_pos_pin"
	if not frappe.db.exists("Custom Field", "User-posa_pos_pin"):
		insert_after = "roles"

	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "User",
			"fieldname": FIELDNAME,
			"fieldtype": "Link",
			"label": "POS Profile",
			"options": "POS Profile",
			"insert_after": insert_after,
			"description": "Assigning a POS Profile adds this user under Applicable for Users (Default) and opens a zero-balance POS Opening Shift.",
		}
	).insert(ignore_permissions=True)


def _migrate_from_pos_profile_users():
	"""Set User.posa_pos_profile from existing POS Profile User rows.

	Prefer the row marked Default; otherwise the most recently modified assignment.
	"""
	if not frappe.db.has_column("User", FIELDNAME):
		# Custom Field insert above adds the column on next reload; force it.
		frappe.clear_cache(doctype="User")
		from frappe.model.meta import get_meta

		get_meta("User", cached=False)
		frappe.reload_doctype("User")

	if not frappe.db.has_column("User", FIELDNAME):
		frappe.db.add_column("User", FIELDNAME, "varchar(140)")

	rows = frappe.db.sql(
		"""
		SELECT user, parent, `default`, modified
		FROM `tabPOS Profile User`
		WHERE user IS NOT NULL AND user != ''
		ORDER BY user, `default` DESC, modified DESC
		""",
		as_dict=True,
	)

	seen = set()
	for row in rows:
		user = row.user
		if user in seen:
			continue
		if not frappe.db.exists("User", user):
			continue
		seen.add(user)
		frappe.db.set_value(
			"User",
			user,
			FIELDNAME,
			row.parent,
			update_modified=False,
		)
