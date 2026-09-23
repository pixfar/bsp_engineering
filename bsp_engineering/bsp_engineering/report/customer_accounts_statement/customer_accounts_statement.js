frappe.query_reports["Customer Accounts Statement"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
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
			fieldname: "party",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "party_group",
			label: __("Customer Group"),
			fieldtype: "Link",
			options: "Customer Group",
		},
	],

	// Rows are grouped per party and already newest-first; keep the global
	// date sort (bsp_column_picker.js) from mixing the groups together.
	bsp_default_date_sort: false,

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.bold) {
			value = `<b>${value}</b>`;
		}
		return value;
	},
};
