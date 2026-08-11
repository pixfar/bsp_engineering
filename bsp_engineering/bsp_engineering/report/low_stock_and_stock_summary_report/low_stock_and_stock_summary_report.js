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
			"fieldtype": "Link",
			"options": "Item Group",
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
		},
	],

	// Total Stock is flagged red whenever the item's combined stock (across
	// every warehouse column shown) has fallen below its combined low-stock
	// threshold -- the same "needs a Dalai order" signal Low Stock Alert
	// Report raises per-row, surfaced here as a single at-a-glance column
	// instead of filtering rows out.
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "total_stock" && flt(data.total_stock) < flt(data.total_low_qty)) {
			value = `<span style="color: var(--red-500, #d1242f); font-weight: 700;">${value}</span>`;
		}
		return value;
	},
};
