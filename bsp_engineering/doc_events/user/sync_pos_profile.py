# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Keep User.posa_pos_profile in sync with POS Profile Applicable for Users
and maintain a zero-balance open POS Opening Shift for that assignment.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate


def on_update(doc, method=None):
	_sync_if_profile_changed(doc)


def after_insert(doc, method=None):
	_sync_if_profile_changed(doc, force=True)


def _sync_if_profile_changed(doc, force=False):
	if frappe.flags.in_migrate or frappe.flags.in_install or frappe.flags.in_patch:
		return
	if frappe.flags.get("skip_user_pos_profile_sync"):
		return
	if not doc.meta.has_field("posa_pos_profile"):
		return

	if not force and not doc.has_value_changed("posa_pos_profile"):
		return

	sync_user_pos_profile(doc.name, doc.get("posa_pos_profile"))


def sync_user_pos_profile(user: str, pos_profile: str | None):
	"""Apply POS Profile membership + opening-shift lifecycle for ``user``.

	- Removes the user from every POS Profile Applicable for Users row
	- Adds them as the Default user on the selected profile (when set)
	- Cancels any Open POS Opening Shift for the user
	- Creates and submits a new zero-balance opening shift for the new profile
	"""
	frappe.flags.skip_user_pos_profile_sync = True
	try:
		_remove_user_from_all_profiles(user)

		if pos_profile:
			_add_user_to_profile(user, pos_profile)

		_cancel_open_shifts(user)

		if pos_profile:
			_create_zero_balance_opening_shift(user, pos_profile)
	finally:
		frappe.flags.skip_user_pos_profile_sync = False


def _remove_user_from_all_profiles(user: str):
	parents = frappe.get_all(
		"POS Profile User",
		filters={"user": user},
		pluck="parent",
	)
	for parent in set(parents):
		profile = frappe.get_doc("POS Profile", parent)
		before = len(profile.applicable_for_users or [])
		profile.applicable_for_users = [
			row for row in (profile.applicable_for_users or []) if row.user != user
		]
		if len(profile.applicable_for_users) != before:
			profile.flags.ignore_permissions = True
			profile.flags.ignore_mandatory = True
			profile.save()


def _add_user_to_profile(user: str, pos_profile: str):
	if not frappe.db.exists("POS Profile", pos_profile):
		frappe.throw(_("POS Profile {0} does not exist").format(pos_profile))

	profile = frappe.get_doc("POS Profile", pos_profile)
	# "Default" on POS Profile User means this profile is the user's default POS.
	existing = next(
		(row for row in (profile.applicable_for_users or []) if row.user == user),
		None,
	)
	if existing:
		existing.default = 1
	else:
		profile.append(
			"applicable_for_users",
			{"user": user, "default": 1},
		)

	profile.flags.ignore_permissions = True
	profile.flags.ignore_mandatory = True
	profile.save()


def _cancel_open_shifts(user: str):
	open_shifts = frappe.get_all(
		"POS Opening Shift",
		filters={
			"user": user,
			"docstatus": 1,
			"status": "Open",
		},
		pluck="name",
	)
	for name in open_shifts:
		shift = frappe.get_doc("POS Opening Shift", name)
		shift.flags.ignore_permissions = True
		shift.cancel()
		# POS Opening Shift has no on_cancel hook to refresh status.
		if shift.docstatus == 2 and shift.status != "Cancelled":
			frappe.db.set_value(
				"POS Opening Shift",
				name,
				"status",
				"Cancelled",
				update_modified=False,
			)


def _create_zero_balance_opening_shift(user: str, pos_profile: str):
	company = frappe.db.get_value("POS Profile", pos_profile, "company")
	if not company:
		frappe.throw(_("POS Profile {0} has no Company").format(pos_profile))

	balance_details = _payment_rows_for_profile(pos_profile)
	if not balance_details:
		frappe.throw(
			_("POS Profile {0} has no payment methods configured").format(pos_profile)
		)

	doc = frappe.get_doc(
		{
			"doctype": "POS Opening Shift",
			"period_start_date": get_datetime(),
			"posting_date": getdate(),
			"user": user,
			"pos_profile": pos_profile,
			"company": company,
			"docstatus": 1,
		}
	)
	doc.set("balance_details", balance_details)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc


def _payment_rows_for_profile(pos_profile: str) -> list[dict]:
	"""Build zero-amount opening balance rows from the profile payment methods."""
	rows = frappe.get_all(
		"POS Payment Method",
		filters={"parent": pos_profile, "parenttype": "POS Profile"},
		fields=["mode_of_payment"],
		order_by="idx asc",
	)
	if not rows:
		# Older ERPNext versions store payments as Sales Invoice Payment children.
		rows = frappe.get_all(
			"Sales Invoice Payment",
			filters={"parent": pos_profile, "parenttype": "POS Profile"},
			fields=["mode_of_payment"],
			order_by="idx asc",
		)
	return [
		{"mode_of_payment": row.mode_of_payment, "amount": 0}
		for row in rows
		if row.mode_of_payment
	]
