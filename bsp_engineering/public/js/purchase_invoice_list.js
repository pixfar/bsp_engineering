frappe.listview_settings["Purchase Invoice"] =
	frappe.listview_settings["Purchase Invoice"] || {};

(function () {
	const settings = frappe.listview_settings["Purchase Invoice"];

	// Define columns explicitly so the header renders correctly.
	// This runs before ListView.setup_columns(), bypassing any saved user preferences.
	settings.columns = [
		"status",
		"grand_total",
		"posting_date",
		"name",
		"custom_delivery_status",
	];

	const color_map = {
		"Not Received": "red",
		"Partially Received": "orange",
		"Fully Received": "green",
	};

	settings.formatters = settings.formatters || {};
	settings.formatters["custom_delivery_status"] = function (value) {
		if (!value) return "";
		const color = color_map[value] || "grey";
		return `<span class="indicator-pill ${color}">${__(value)}</span>`;
	};
})();
