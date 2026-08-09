"""Shared Additional Salary creation/reversal helpers for the Verti (piece-rate)
Salary System -- used by both Verti Daily Production (wage) and Verti Weekly
Wastage (penalty deduction), so the two doctypes' on_submit/on_cancel logic
stay in sync instead of drifting apart.
"""

import re

import frappe
from frappe import _
from frappe.utils import flt


def create_additional_salary(employee, salary_component, amount, payroll_date, ref_doctype, ref_docname):
	"""Create and submit one Additional Salary for `employee`. Raises on
	failure (e.g. no active Salary Structure Assignment for that employee) --
	callers are expected to let that propagate so the whole batch (and the
	submitting parent document) rolls back together; see each doctype's
	on_submit for why a partial batch must never be left half-applied.
	"""
	company = frappe.db.get_value("Employee", employee, "company")
	if not company:
		frappe.throw(_("Employee {0} has no Company set.").format(employee))

	component_type = frappe.db.get_value("Salary Component", salary_component, "type")

	additional_salary = frappe.new_doc("Additional Salary")
	additional_salary.employee = employee
	additional_salary.company = company
	additional_salary.salary_component = salary_component
	additional_salary.type = component_type
	additional_salary.payroll_date = payroll_date
	additional_salary.amount = flt(amount)
	additional_salary.overwrite_salary_structure_amount = 0
	additional_salary.ref_doctype = ref_doctype
	additional_salary.ref_docname = ref_docname
	additional_salary.flags.ignore_permissions = True
	additional_salary.insert(ignore_permissions=True)
	additional_salary.submit()
	return additional_salary


def create_additional_salaries_or_rollback(rows, source_doctype, source_name):
	"""rows: iterable of {"employee", "salary_component", "amount", "payroll_date"}.

	Creates one Additional Salary per row inside a savepoint. If any row
	fails, everything created in this batch (and, since this always runs
	from inside a submit(), the parent document's own docstatus change) is
	rolled back together -- a partially-distributed day's wage or week's
	penalty is worse than none at all, since it would silently under-pay
	some workers with no easy way to see who was skipped and why.

	Returns the list of created Additional Salary names on success. Raises
	(after rollback) on failure, with a message naming exactly which
	employee/row caused it.
	"""
	# Autonamed docnames (e.g. "VDP-2026-00001") contain hyphens, which MariaDB's
	# unquoted `SAVEPOINT <name>` syntax rejects -- sanitize to a safe identifier
	# instead of quoting, since quoting rules differ across DB backends.
	raw_savepoint = f"verti_salary_{source_doctype.lower().replace(' ', '_')}_{source_name}"
	savepoint = re.sub(r"[^0-9a-zA-Z_]", "_", raw_savepoint)
	frappe.db.savepoint(savepoint)
	created = []
	try:
		for row in rows:
			amount = flt(row.get("amount"))
			if amount <= 0:
				continue
			additional_salary = create_additional_salary(
				employee=row["employee"],
				salary_component=row["salary_component"],
				amount=amount,
				payroll_date=row["payroll_date"],
				ref_doctype=source_doctype,
				ref_docname=source_name,
			)
			created.append(additional_salary.name)
	except Exception as error:
		frappe.db.rollback(save_point=savepoint)
		frappe.log_error(
			title=f"Verti Salary: Additional Salary creation failed for {source_doctype} {source_name}",
			message=frappe.get_traceback(),
		)
		frappe.throw(
			_(
				"Could not create Additional Salary for employee {0}: {1}. "
				"No Additional Salary entries were created for this document -- "
				"fix the issue (e.g. assign a Salary Structure to that employee) and submit again."
			).format(row.get("employee"), str(error))
		)
	return created


def cancel_additional_salaries(source_doctype, source_name):
	"""Cancel every submitted Additional Salary this document created (via
	ref_doctype/ref_docname), mirroring the source document's own cancel --
	called from on_cancel so reversing a Verti Daily Production or Verti
	Weekly Wastage also reverses the payroll entries it produced, not just
	its own docstatus."""
	names = frappe.get_all(
		"Additional Salary",
		filters={"ref_doctype": source_doctype, "ref_docname": source_name, "docstatus": 1},
		pluck="name",
	)
	for name in names:
		doc = frappe.get_doc("Additional Salary", name)
		doc.flags.ignore_permissions = True
		doc.cancel()
	return names
