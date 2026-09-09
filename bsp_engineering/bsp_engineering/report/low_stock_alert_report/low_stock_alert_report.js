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
