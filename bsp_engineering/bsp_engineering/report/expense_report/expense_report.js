// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

// "Period" is a shortcut that fills From/To Date (this day / week / month /
// year up to today). Editing either date by hand switches Period back to
// blank, i.e. a custom range.
const PERIOD_START = {
	Daily: () => frappe.datetime.get_today(),
	Weekly: () => frappe.datetime.week_start(),
	Monthly: () => frappe.datetime.month_start(),
	Yearly: () => frappe.datetime.year_start(),
};

function apply_period(report) {
	const start = PERIOD_START[report.get_filter_value("period")];
	if (!start) {
		report.refresh();
		return;
	}
	const from_date = start();
	const to_date = frappe.datetime.get_today();
	if (report.get_filter_value("from_date") === from_date && report.get_filter_value("to_date") === to_date) {
		report.refresh();
		return;
	}
	// The two date changes below fire their own on_change; don't let them
	// treat this as a manual edit and clear Period again.
	report._applying_period = true;
	report.set_filter_value({ from_date, to_date });
	setTimeout(() => (report._applying_period = false), 500);
}

function on_date_change(report) {
	if (!report._applying_period && report.get_filter_value("period")) {
		const start = PERIOD_START[report.get_filter_value("period")];
		const matches =
			report.get_filter_value("from_date") === start() &&
			report.get_filter_value("to_date") === frappe.datetime.get_today();
		if (!matches) {
			report._applying_period = true;
			report.set_filter_value("period", "");
			setTimeout(() => (report._applying_period = false), 500);
		}
	}
	if (!report._no_refresh) report.refresh();
}

frappe.query_reports["Expense Report"] = {
	filters: [
		{
			fieldname: "period",
			label: __("Period"),
			fieldtype: "Select",
			options: [
				{ value: "", label: __("Custom Range") },
				{ value: "Daily", label: __("Daily (Today)") },
				{ value: "Weekly", label: __("Weekly (This Week)") },
				{ value: "Monthly", label: __("Monthly (This Month)") },
				{ value: "Yearly", label: __("Yearly (This Year)") },
			],
			default: "Monthly",
			on_change: (report) => {
				if (!report._applying_period) apply_period(report);
			},
		},
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: ["", "Expense Type", "Employee", "Warehouse", "Department", "Date"],
			description: __("Leave empty for line-by-line detail"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
			on_change: on_date_change,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
			on_change: on_date_change,
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "MultiSelectList",
			options: "Warehouse",
			get_data: (txt) => frappe.db.get_link_options("Warehouse", txt, { is_group: 0 }),
		},
		{
			fieldname: "expense_type",
			label: __("Expense Type"),
			fieldtype: "MultiSelectList",
			options: "Expense Claim Type",
			get_data: (txt) => frappe.db.get_link_options("Expense Claim Type", txt),
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Draft", "Paid", "Unpaid", "Rejected", "Submitted", "Cancelled"],
		},
		{
			fieldname: "approval_status",
			label: __("Approval Status"),
			fieldtype: "Select",
			options: ["", "Draft", "Approved", "Rejected"],
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (column.fieldname === "warehouse" && data.warehouse_name) {
			value = frappe.utils.escape_html(data.warehouse_name);
		}
		return value;
	},
};
