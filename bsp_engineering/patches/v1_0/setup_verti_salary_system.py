import frappe


def execute():
	"""Prerequisite data for the Verti (piece-rate) Salary System:

	- Employee.custom_verti_point: each worker's share-point used to split a
	  day's production wage and a week's wastage penalty across everyone who
	  worked.
	- Two Salary Components Verti Daily Production / Verti Weekly Wastage
	  create Additional Salary entries against, on submit.

	Idempotent -- safe to run again (e.g. after a fixtures re-sync) since
	both parts check for the record before creating it.
	"""
	_ensure_verti_point_field()
	_ensure_salary_component("Verti Daily Wage", "VDW", "Earning")
	_ensure_salary_component("Verti Wastage Deduction", "VWD", "Deduction")


def _ensure_verti_point_field():
	name = "Employee-custom_verti_point"
	if frappe.db.exists("Custom Field", name):
		return
	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "Employee",
			"fieldname": "custom_verti_point",
			"fieldtype": "Float",
			"label": "Verti Point",
			"insert_after": "designation",
			"description": "Share point used to split Verti piece-rate wages and wastage penalties across present workers.",
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
			"description": f"Auto-created by the Verti Salary System ({component_type}).",
		}
	).insert(ignore_permissions=True)
