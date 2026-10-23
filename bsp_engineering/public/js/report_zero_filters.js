// Optional Check filters for warehouse-matrix BSP reports. Default is off so
// every warehouse column / zero row stays visible; users tick these to trim.
frappe.provide("bsp_engineering");

bsp_engineering.report_zero_filters = [
	{
		fieldname: "hide_zero_columns",
		label: __("Hide Zero Columns"),
		fieldtype: "Check",
		default: 0,
	},
	{
		fieldname: "hide_zero_rows",
		label: __("Hide Zero Rows"),
		fieldtype: "Check",
		default: 0,
	},
];
