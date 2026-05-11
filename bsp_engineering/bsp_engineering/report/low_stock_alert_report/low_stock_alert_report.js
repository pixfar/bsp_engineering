// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.query_reports["Low Stock Alert Report"] = {
	"filters": [
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse"
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"options": "Item Group"
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item"
		}
	]
};
