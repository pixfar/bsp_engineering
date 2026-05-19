// Build the item_code get_query function for a given item_group value
function item_code_query(item_group) {
	const filters = { is_purchase_item: 1, has_variants: 0, disabled: 0 };
	if (item_group) filters.item_group = item_group;
	return { filters };
}

// Push the query into every rendered grid-row field for item_code.
// frm.set_query only updates grid.fieldinfo (used for NEW rows);
// already-rendered fields cache get_query at make_control time and
// must be patched directly.
function sync_item_queries(frm) {
	const query_fn = function (doc, cdt, cdn) {
		return item_code_query((locals[cdt] && locals[cdt][cdn] && locals[cdt][cdn].item_group) || "");
	};

	// 1. Cover future/new rows
	frm.set_query("item_code", "items", query_fn);

	// 2. Patch already-rendered row fields via fields_dict
	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) return;
	(grid.grid_rows || []).forEach((grid_row) => {
		const field = grid_row.fields_dict && grid_row.fields_dict.item_code;
		if (field) {
			field.get_query = function () {
				return item_code_query((grid_row.doc && grid_row.doc.item_group) || "");
			};
		}
	});
}

frappe.ui.form.on("Purchase Invoice", {
	refresh: function (frm) {
		sync_item_queries(frm);
	},
});

frappe.ui.form.on("Purchase Invoice Item", {
	item_group: function (frm, cdt, cdn) {
		// Clear stale item selection
		frappe.model.set_value(cdt, cdn, "item_code", "");

		// Patch the query on the exact rendered field for this row
		const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
		if (!grid) return;
		const grid_row = grid.grid_rows_by_docname && grid.grid_rows_by_docname[cdn];
		if (!grid_row) return;
		const field = grid_row.fields_dict && grid_row.fields_dict.item_code;
		if (field) {
			field.get_query = function () {
				return item_code_query((grid_row.doc && grid_row.doc.item_group) || "");
			};
		}
	},
});
