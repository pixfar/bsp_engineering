// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.ui.form.on("Requisition", {
	refresh: function (frm) {
		frm.fields_dict["items"].grid.get_field("item_code").get_query = function (
			doc,
			cdt,
			cdn
		) {
			let row = frappe.get_doc(cdt, cdn);
			if (row.item_group) {
				return { filters: { item_group: row.item_group } };
			}
			return {};
		};
	},
});

frappe.ui.form.on("Requisition Item", {
	item_group: function (frm, cdt, cdn) {
		// Clear item_code when group changes so stale value isn't kept
		frappe.model.set_value(cdt, cdn, "item_code", "");
	},
});
