// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.query_reports["Low Stock and Stock Summary Report"] = {
	"filters": [
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "MultiSelectList",
			"options": "Warehouse",
			"get_data": function (txt) {
				return frappe.db.get_link_options("Warehouse", txt);
			},
			"description": __("Leave blank to show every warehouse that has a Low Stock Qty configured"),
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "MultiSelectList",
			"options": "Item Group",
			"get_data": function (txt) {
				return frappe.db.get_link_options("Item Group", txt);
			},
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "MultiSelectList",
			"options": "Item",
			"get_data": function (txt) {
				return frappe.db.get_link_options("Item", txt);
			},
		},
		{
			"fieldname": "production_group",
			"label": __("Production Group"),
			"fieldtype": "MultiSelectList",
			"options": "Production Group",
			"get_data": function (txt) {
				return frappe.db.get_link_options("Production Group", txt);
			},
		},
		{
			"fieldname": "stock_status",
			"label": __("Stock Status"),
			"fieldtype": "Select",
			// Matches the same red/not-red split the formatter below flags --
			// "Low Stock" is exactly the rows the formatter would render red.
			"options": [
				{ "value": "", "label": __("All") },
				{ "value": "Low Stock", "label": __("Low Stock (Red)") },
				{ "value": "Sufficient Stock", "label": __("Sufficient Stock") },
			],
		},
	],

	// Total Stock is flagged red whenever the item's combined stock (across
	// every warehouse column shown) has fallen below its combined low-stock
	// threshold -- the same "needs a Dalai order" signal Low Stock Alert
	// Report raises per-row, surfaced here as a single at-a-glance column
	// instead of filtering rows out.
	"formatter": function (value, row, column, data, default_formatter) {
		// frappe.form.link_formatters["Item"] (registered globally by
		// ERPNext) rewrites any Item Link cell into "code: item_name"
		// whenever the same row also carries an item_name field - useful in
		// e.g. a Sales Order Item grid, but this report already has its own
		// separate Item Name column right next to it, so it just shows the
		// code twice. Building the link directly instead of calling
		// default_formatter() for this one column keeps that global
		// formatter from ever running here.
		if (column.fieldname === "item_code" && data && data.item_code) {
			const code = frappe.utils.escape_html(data.item_code);
			return `<a href="/app/item/${encodeURIComponent(data.item_code)}" data-doctype="Item" data-name="${code}">${code}</a>`;
		}
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "total_stock" && flt(data.total_stock) < flt(data.total_low_qty)) {
			value = `<span style="color: var(--red-500, #d1242f); font-weight: 700;">${value}</span>`;
		}
		return value;
	},
};
