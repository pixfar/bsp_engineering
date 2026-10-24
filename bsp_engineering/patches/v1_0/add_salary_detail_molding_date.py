import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Show which production day / wastage week each molding Additional Salary
	row on a Salary Slip belongs to (Component alone repeats the same label).
	"""
	create_custom_fields(
		{
			"Salary Detail": [
				{
					"fieldname": "custom_molding_date",
					"fieldtype": "Data",
					"label": "Date",
					"insert_after": "salary_component",
					"columns": 2,
					"in_list_view": 1,
					"read_only": 1,
					"allow_on_submit": 1,
					"description": "Production date (Molding Daily Wage) or wastage week "
					"(Molding Wastage Deduction), stamped from the linked Additional Salary.",
				}
			]
		},
		update=True,
	)

	# Prefer Date over Abbr in the earnings/deductions grid (Abbr is rarely useful on slips).
	_ensure_property_setter(
		doctype="Salary Detail",
		fieldname="abbr",
		property="in_list_view",
		value="0",
		property_type="Check",
	)


def _ensure_property_setter(doctype, fieldname, property, value, property_type):
	name = f"{doctype}-{fieldname}-{property}"
	if frappe.db.exists("Property Setter", name):
		frappe.db.set_value("Property Setter", name, "value", value, update_modified=False)
		return
	frappe.get_doc(
		{
			"doctype": "Property Setter",
			"doctype_or_field": "DocField",
			"doc_type": doctype,
			"field_name": fieldname,
			"property": property,
			"property_type": property_type,
			"value": value,
			"name": name,
		}
	).insert(ignore_permissions=True)
