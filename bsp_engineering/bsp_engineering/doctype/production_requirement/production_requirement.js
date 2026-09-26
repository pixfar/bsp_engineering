// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

// Shortage Qty is set server-side (production_requirement.py); this only
// keeps the totals live while editing.
frappe.ui.form.on('Production Requirement', {
	onload(frm) {
		if (frm.is_new() && !frm.doc.warehouse) {
			frappe.call({
				method: 'bsp_engineering.api.pos_warehouse.get_pos_active_warehouse',
				callback: (r) => {
					if (r.message?.name && !frm.doc.warehouse) {
						frm.set_value('warehouse', r.message.name);
					}
				},
			});
		}
	},
	refresh(frm) {
		frm.set_query('item_code', 'items', () => ({ filters: { disabled: 0 } }));
	},
});

frappe.ui.form.on('Production Requirement Item', {
	plan_qty: calculate_totals,
	items_remove: calculate_totals,
});

function calculate_totals(frm) {
	frm.doc.total_plan_qty = (frm.doc.items || []).reduce((sum, row) => sum + flt(row.plan_qty), 0);
	frm.doc.total_shortage_qty = (frm.doc.items || []).reduce((sum, row) => sum + flt(row.shortage_qty), 0);
	frm.refresh_fields(['total_plan_qty', 'total_shortage_qty']);
}
