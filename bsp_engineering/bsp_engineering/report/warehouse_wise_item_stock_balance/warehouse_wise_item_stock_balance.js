// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.query_reports["Warehouse Wise Item Stock Balance"] = {
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
			"description": __("Limits the report to items with stock movement on or after this date")
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
	],

	// frappe.form.link_formatters["Item"] (registered globally by ERPNext)
	// rewrites any Item Link cell into "code: item_name" whenever the same
	// row also carries an item_name field - useful in e.g. a Sales Order
	// Item grid, but this report already has its own separate Item Name
	// column right next to it, so it just shows the code twice. Building
	// the link directly instead of calling default_formatter() for this
	// one column keeps that global formatter from ever running here.
	"formatter": function (value, row, column, data, default_formatter) {
		if (column.fieldname === "item_code" && data && data.item_code) {
			const code = frappe.utils.escape_html(data.item_code);
			return `<a href="/app/item/${encodeURIComponent(data.item_code)}" data-doctype="Item" data-name="${code}">${code}</a>`;
		}
		return default_formatter(value, row, column, data);
	},
};
