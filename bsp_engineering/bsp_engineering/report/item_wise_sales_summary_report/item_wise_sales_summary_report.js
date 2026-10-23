// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.query_reports["Item Wise Sales Summary Report"] = {
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
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "customer_group",
			label: __("Customer Group"),
			fieldtype: "Link",
			options: "Customer Group",
		},
		{
			fieldname: "mode_of_payment",
			label: __("Mode of Payment"),
			fieldtype: "Link",
			options: "Mode of Payment",
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "MultiSelectList",
			options: "Warehouse",
			get_data: function (txt) {
				const company = frappe.query_report.get_filter_value("company");
				const filters = { is_group: 0 };
				if (company) filters.company = company;
				return frappe.db.get_link_options("Warehouse", txt, filters);
			},
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			options: "Brand",
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "MultiSelectList",
			options: "Item Group",
			get_data: (txt) => frappe.db.get_link_options("Item Group", txt),
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "MultiSelectList",
			options: "Item",
			get_data: (txt) => frappe.db.get_link_options("Item", txt),
		},
		{
			fieldname: "production_group",
			label: __("Production Group"),
			fieldtype: "MultiSelectList",
			options: "Production Group",
			get_data: (txt) => frappe.db.get_link_options("Production Group", txt),
		},
	].concat(bsp_engineering.report_zero_filters || []),

	formatter: function (value, row, column, data, default_formatter) {
		// Item link formatter would print "code: name" beside the Item Name column.
		if (column.fieldname === "item_code" && data && data.item_code) {
			const code = frappe.utils.escape_html(data.item_code);
			return `<a href="/app/item/${encodeURIComponent(data.item_code)}" data-doctype="Item" data-name="${code}">${code}</a>`;
		}
		return default_formatter(value, row, column, data);
	},
};
