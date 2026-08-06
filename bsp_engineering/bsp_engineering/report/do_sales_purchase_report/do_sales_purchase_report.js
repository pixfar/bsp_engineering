// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.query_reports["DO Sales Purchase Report"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "do_number",
			"label": __("DO Number"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
		},
		{
			"fieldname": "received_status",
			"label": __("Received Status"),
			"fieldtype": "Select",
			"options": ["", "Not Received", "Partly Received", "Received"],
		},
	]
};
