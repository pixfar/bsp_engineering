import frappe


def execute():
	"""Prerequisite data for the Molding (piece-rate) Salary System:

	- Employee.custom_molding_point: each worker's share-point used to split a
	  day's production wage and a week's wastage penalty across everyone who
	  worked.
	- Two Salary Components Molding Daily Production / Molding Weekly Wastage
	  create Additional Salary entries against, on submit.

	Idempotent -- safe to run again (e.g. after a fixtures re-sync) since
	both parts check for the record before creating it. Also safe on a bench
	that already had the old "Verti"-named field/components renamed in place
	(bsp_engineering.patches.v1_0.setup_verti_salary_system, superseded by
	this patch) -- the exists() checks below just no-op in that case.
	"""
	_ensure_molding_point_field()
	_ensure_salary_component("Molding Daily Wage", "MDW", "Earning")
	_ensure_salary_component("Molding Wastage Deduction", "MWD", "Deduction")


def _ensure_molding_point_field():
	name = "Employee-custom_molding_point"
	if frappe.db.exists("Custom Field", name):
		return
	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "Employee",
			"fieldname": "custom_molding_point",
			"fieldtype": "Float",
			"label": "Molding Point",
			"insert_after": "designation",
			"description": "Share point used to split Molding piece-rate wages and wastage penalties across present workers.",
			"non_negative": 1,
		}
	).insert(ignore_permissions=True)


def _ensure_salary_component(component_name, abbr, component_type):
	if frappe.db.exists("Salary Component", component_name):
		return
	frappe.get_doc(
		{
			"doctype": "Salary Component",
			"salary_component": component_name,
			"salary_component_abbr": abbr,
			"type": component_type,
			"description": f"Auto-created by the Molding Salary System ({component_type}).",
		}
	).insert(ignore_permissions=True)
