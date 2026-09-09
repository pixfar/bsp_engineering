frappe.query_reports["Sales Return Register"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			width: "80",
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
			reqd: 1,
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
			fieldname: "territory",
			label: __("Territory"),
			fieldtype: "Link",
			options: "Territory",
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
	],

	// frappe.form.link_formatters["Item"] (registered globally by ERPNext)
	// rewrites any Item Link cell into "code: item_name" whenever the same
	// row also carries an item_name field - useful in e.g. a Sales Order
	// Item grid, but this report already has its own separate Item Name
	// column right next to it, so it just shows the code twice. Building
	// the link directly instead of calling default_formatter() for this
	// one column keeps that global formatter from ever running here.
	formatter: function (value, row, column, data, default_formatter) {
		if (column.fieldname === "item_code" && data && data.item_code) {
			const code = frappe.utils.escape_html(data.item_code);
			return `<a href="/app/item/${encodeURIComponent(data.item_code)}" data-doctype="Item" data-name="${code}">${code}</a>`;
		}
		return default_formatter(value, row, column, data);
	},
};
