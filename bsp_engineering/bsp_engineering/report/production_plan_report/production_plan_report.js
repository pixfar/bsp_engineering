// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.query_reports["Production Plan Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "MultiSelectList",
			options: "Warehouse",
			get_data: (txt) => frappe.db.get_link_options("Warehouse", txt, { is_group: 0 }),
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "MultiSelectList",
			options: "Item Group",
			get_data: (txt) => frappe.db.get_link_options("Item Group", txt),
		},
		{
			fieldname: "production_group",
			label: __("Production Group"),
			fieldtype: "MultiSelectList",
			options: "Production Group",
			get_data: (txt) => frappe.db.get_link_options("Production Group", txt),
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "MultiSelectList",
			options: "Item",
			get_data: (txt) => frappe.db.get_link_options("Item", txt),
		},
		{
			fieldname: "production_by",
			label: __("Production By"),
			fieldtype: "Link",
			options: "User",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && ["shortage_qty", "uncovered_qty"].includes(column.fieldname) && flt(data[column.fieldname]) > 0) {
			value = `<span style="color: var(--red-500, #d1242f); font-weight: 600;">${value}</span>`;
		}
		return value;
	},
};
