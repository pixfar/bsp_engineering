// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.query_reports["Production Requirement Report"] = {
	"filters": [
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
	// the three fixed warehouse columns shown) has fallen below its combined
	// low-stock threshold -- the same "needs a Dalai order" signal Low Stock
	// Alert Report raises per-row, surfaced here as a single at-a-glance
	// column instead of filtering rows out.
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "total_stock" && flt(data.total_stock) < flt(data.total_low_qty)) {
			value = `<span style="color: var(--red-500, #d1242f); font-weight: 700;">${value}</span>`;
		}
		return value;
	},
};
