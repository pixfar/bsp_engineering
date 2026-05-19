function mr_item_code_query(item_group) {
	const filters = { has_variants: 0, disabled: 0 };
	if (item_group) filters.item_group = item_group;
	return { filters };
}

function sync_mr_item_queries(frm) {
	const query_fn = function (doc, cdt, cdn) {
		return mr_item_code_query(
			(locals[cdt] && locals[cdt][cdn] && locals[cdt][cdn].item_group) || ""
		);
	};

	frm.set_query("item_code", "items", query_fn);

	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) return;
	(grid.grid_rows || []).forEach((grid_row) => {
		const field = grid_row.fields_dict && grid_row.fields_dict.item_code;
		if (field) {
			field.get_query = function () {
				return mr_item_code_query((grid_row.doc && grid_row.doc.item_group) || "");
			};
		}
	});
}

frappe.ui.form.on("Material Request", {
	refresh: function (frm) {
		sync_mr_item_queries(frm);
	},
});

frappe.ui.form.on("Material Request Item", {
	item_group: function (frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "item_code", "");

		const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
		if (!grid) return;
		const grid_row = grid.grid_rows_by_docname && grid.grid_rows_by_docname[cdn];
		if (!grid_row) return;

		const field = grid_row.fields_dict && grid_row.fields_dict.item_code;
		if (field) {
			field.get_query = function () {
				return mr_item_code_query((grid_row.doc && grid_row.doc.item_group) || "");
			};
		}
	},
});
