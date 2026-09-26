// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

// New Items get the next automatic Item Code (see item_auto_code.js); the
// user can still overwrite it.
frappe.ui.form.on("Item", {
	onload(frm) {
		if (frm.is_new()) {
			bsp_engineering.item_code.fill(frm.doc, (code) => frm.set_value("item_code", code));
		}
	},
});
