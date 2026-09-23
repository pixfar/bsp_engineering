// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.query_reports["Production Requirement Report"] = {
	"filters": [
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
			"options": [
				{ "value": "", "label": __("All") },
				{ "value": "Low Stock", "label": __("Low Stock (Red)") },
				{ "value": "Sufficient Stock", "label": __("Sufficient Stock") },
			],
		},
	],

	"onload": function (report) {
		// 1. Handle Column Persistence Logic
		frappe.call({
			method: "bsp_engineering.bsp_engineering.api.report_settings.get_user_report_settings",
			args: { report_name: report.report_name },
			callback: function (r) {
				if (r.message) {
					const { hidden_columns = [], column_order = [] } = r.message;

					const filter_and_sort = () => {
						if (!report.columns) return;

						// Filter out hidden columns
						report.columns = report.columns.filter(col => !hidden_columns.includes(col.id));

						// Reorder columns based on saved order
						if (column_order.length) {
							const ordered = [];
							const remaining = [];

							report.columns.forEach(col => {
								const idx = column_order.indexOf(col.id);
								if (idx !== -1) {
									ordered.push({ ...col, sort_idx: idx });
								} else {
									remaining.push(col);
								}
							});

							ordered.sort((a, b) => a.sort_idx - b.sort_idx);
							report.columns = [...ordered.map(c => { delete c.sort_idx; return c; }), ...remaining];
						}
					};

					filter_and_sort();

					const original_refresh = report.refresh;
					if (original_refresh) {
						report.refresh = function (...args) {
							filter_and_sort();
							return original_refresh.apply(this, args);
						};
					}
				}
			}
		});

		// 2. Define the Pick Columns action to be reused
		report.open_pick_columns_dialog = function () {
			frappe.call({
				method: "bsp_engineering.bsp_engineering.api.report_settings.get_user_report_settings",
				args: { report_name: report.report_name },
				callback: function (r) {
					const current_settings = r.message || {};
					const hidden_columns = current_settings.hidden_columns || [];

					const d = new frappe.ui.Dialog({
						title: __("Pick Columns"),
						fields: [
							{
								label: __("Select Columns"),
								fieldname: "columns",
								fieldtype: "MultiCheck",
								options: report.columns.map(col => ({
									label: col.label,
									value: col.id,
									checked: !hidden_columns.includes(col.id)
								}))
							}
						],
						primary_action: (values) => {
							const selected = values.columns || [];
							const new_hidden = report.columns
								.filter(col => !selected.includes(col.id))
								.map(col => col.id);

							const still_hidden = hidden_columns.filter(id => !report.columns.find(c => c.id === id));

							frappe.call({
								method: "bsp_engineering.bsp_engineering.api.report_settings.save_user_report_settings",
								args: {
									report_name: report.report_name,
									hidden_columns: [...new_hidden, ...still_hidden],
									column_order: []
								},
								callback: () => {
									report.refresh();
									d.hide();
								}
							});
						}
					});
					d.show();
				}
			});
		};

		// 3. Add to Report Menu (The "..." menu)
		if (report.get_menu_items) {
			const original_get_menu = report.get_menu_items;
			report.get_menu_items = function () {
				const items = original_get_menu ? original_get_menu.call(this) : [];
				items.push({
					label: __("Pick Columns"),
					action: () => report.open_pick_columns_dialog()
				});
				return items;
			};
		}

		// 4. Direct DOM Injection using MutationObserver (The most robust way for the toolbar)
		const observer = new MutationObserver(() => {
			const toolbar = $(".page-head-actions");
			if (toolbar.length && !$("#btn-pick-columns").length) {
				const btn = $(`<button class="btn btn-xs btn-default btn-pick-columns" style="margin-right: 10px; background-color: #fff; color: #000; border: 1px solid #d1d88d;">${__("Pick Columns")}</button>`);

				btn.on("click", () => {
					report.open_pick_columns_dialog();
				});
				toolbar.prepend(btn);
			}
		});

		observer.observe(document.body, {
			childList: true,
			subtree: true
		});
	},

	"formatter": function (value, row, column, data, default_formatter) {
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

	"after_datatable_render": function (report) {
		const datatable = report.datatable;
		if (!datatable) return;

		const original_remove = datatable.events.onRemoveColumn;
		datatable.events.onRemoveColumn = function (column) {
			if (original_remove) original_remove.call(this, column);

			frappe.call({
				method: "bsp_engineering.bsp_engineering.api.report_settings.get_user_report_settings",
				args: { report_name: report.report_name },
				callback: function (r) {
					const settings = r.message || {};
					const hidden = settings.hidden_columns || [];
					if (!hidden.includes(column.id)) {
						hidden.push(column.id);
					}

					frappe.call({
						method: "bsp_engineering.bsp_engineering.api.report_settings.save_user_report_settings",
						args: {
							report_name: report.report_name,
							hidden_columns: hidden,
							column_order: datatable.datamanager.getColumns(true).map(col => col.id)
						}
					});
				}
			});
		};

		const original_switch = datatable.events.onSwitchColumn;
		datatable.events.onSwitchColumn = function (col1, col2) {
			if (original_switch) original_switch.call(this, col1, col2);

			frappe.call({
				method: "bsp_engineering.bsp_engineering.api.report_settings.get_user_report_settings",
				args: { report_name: report.report_name },
				callback: function (r) {
					const settings = r.message || {};
					const current_order = datatable.datamanager.getColumns(true).map(col => col.id);

					frappe.call({
						method: "bsp_engineering.bsp_engineering.api.report_settings.save_user_report_settings",
						args: {
							report_name: report.report_name,
							hidden_columns: settings.hidden_columns || [],
							column_order: current_order
						}
					});
				}
			});
		};
	},
};
