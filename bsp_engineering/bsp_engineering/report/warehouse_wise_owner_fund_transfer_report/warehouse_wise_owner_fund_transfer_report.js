// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.query_reports["Warehouse Wise Owner Fund Transfer Report"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1,
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"get_query": function () {
				var company = frappe.query_report.get_filter_value("company");
				return { filters: { company: company, is_group: 0 } };
			},
			"description": __("Leave blank to show every warehouse"),
		},
		{
			"fieldname": "cash_in_hand_account",
			"label": __("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"get_query": function () {
				var company = frappe.query_report.get_filter_value("company");
				return { filters: { company: company, account_type: ["in", ["Cash", "Bank"]], is_group: 0 } };
			},
			"description": __("Leave blank to show every configured Cash/Bank account"),
		},
	],
};
