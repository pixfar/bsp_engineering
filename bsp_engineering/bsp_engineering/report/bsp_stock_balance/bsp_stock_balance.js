// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.query_reports["BSP Stock Balance"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": "2020-01-01",
			"description": __("Opening balance is calculated using entries posted before this date")
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"description": __("Shows the stock balance as on this date")
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "MultiSelectList",
			"options": "Item Group",
			"get_data": function (txt) {
				return frappe.db.get_link_options("Item Group", txt);
			}
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "MultiSelectList",
			"options": "Item",
			"get_data": function (txt) {
				return frappe.db.get_link_options("Item", txt);
			}
		},
		{
			"fieldname": "include_zero_stock_items",
			"label": __("Include Zero Stock Items"),
			"fieldtype": "Check",
			"default": 0
		}
	]
};
