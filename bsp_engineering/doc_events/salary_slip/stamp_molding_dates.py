"""Stamp a readable Date / Period on Salary Slip earning & deduction rows
that come from the Molding (piece-rate) Salary System.

Additional Salary already keeps `ref_doctype` / `ref_docname` pointing at
Molding Daily Production or Molding Weekly Wastage. Without this stamp the
slip only shows repeated "Molding Daily Wage" lines with no day, so workers
can't tell which production date each amount belongs to.
"""

from __future__ import annotations

import frappe
from frappe.utils import formatdate

MOLDING_COMPONENTS = frozenset({"Molding Daily Wage", "Molding Wastage Deduction"})
DATE_FIELD = "custom_molding_date"


def stamp_molding_dates(doc, method=None):
	if not _child_has_date_field():
		return

	for row in list(doc.get("earnings") or []) + list(doc.get("deductions") or []):
		if row.salary_component not in MOLDING_COMPONENTS or not row.additional_salary:
			# Clear stale value if the row is no longer a molding Additional Salary.
			if row.get(DATE_FIELD):
				row.set(DATE_FIELD, None)
			continue
		row.set(DATE_FIELD, _resolve_molding_date_label(row.additional_salary))


def _child_has_date_field() -> bool:
	return bool(frappe.get_meta("Salary Detail").has_field(DATE_FIELD))


def _resolve_molding_date_label(additional_salary_name: str) -> str | None:
	ads = frappe.db.get_value(
		"Additional Salary",
		additional_salary_name,
		["ref_doctype", "ref_docname", "payroll_date"],
		as_dict=True,
	)
	if not ads:
		return None

	if ads.ref_doctype == "Molding Daily Production" and ads.ref_docname:
		production_date = frappe.db.get_value(
			"Molding Daily Production", ads.ref_docname, "date"
		)
		return formatdate(production_date) if production_date else _format_optional(ads.payroll_date)

	if ads.ref_doctype == "Molding Weekly Wastage" and ads.ref_docname:
		start_date, end_date = frappe.db.get_value(
			"Molding Weekly Wastage",
			ads.ref_docname,
			["start_date", "end_date"],
		) or (None, None)
		if start_date and end_date:
			if start_date == end_date:
				return formatdate(start_date)
			return f"{formatdate(start_date)} – {formatdate(end_date)}"
		return _format_optional(ads.payroll_date)

	return _format_optional(ads.payroll_date)


def _format_optional(value) -> str | None:
	return formatdate(value) if value else None
