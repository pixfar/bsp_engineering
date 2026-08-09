// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

const ALLOWED_WASTAGE_RATE = 0.01; // 1%
const PENALTY_PER_KG = 20; // BDT per excess KG

frappe.ui.form.on('Verti Weekly Wastage', {
	refresh(frm) {
		setup_fetch_weekly_data_button(frm);
	},
	start_date(frm) {
		default_end_date(frm);
	},
	total_weekly_work_kg(frm) {
		calculate_wastage_figures(frm);
	},
	actual_wastage_kg(frm) {
		calculate_wastage_figures(frm);
	},
});

function default_end_date(frm) {
	// Week runs Thursday -> Wednesday; suggest the end date once a start
	// date is picked, the user can still change it before saving.
	if (!frm.doc.start_date || frm.doc.end_date) return;
	const end_date = frappe.datetime.add_days(frm.doc.start_date, 6);
	frm.set_value('end_date', end_date);
}

function calculate_wastage_figures(frm) {
	// Mirrors the server's own calculate_wastage_figures() (validate())
	// exactly -- see verti_daily_production.js's identical note on why this
	// duplication is fine: it's a live-preview convenience only, the server
	// always recalculates from scratch on save.
	const allowed = flt(frm.doc.total_weekly_work_kg) * ALLOWED_WASTAGE_RATE;
	frm.set_value('allowed_wastage_kg', allowed);

	let excess = flt(frm.doc.actual_wastage_kg) - allowed;
	if (excess < 0) excess = 0;
	frm.set_value('excess_wastage_kg', excess);
	frm.set_value('penalty_amount', excess * PENALTY_PER_KG);
}

function setup_fetch_weekly_data_button(frm) {
	if (frm.doc.docstatus !== 0) return;

	frm.add_custom_button(__('Fetch Weekly Data'), () => {
		if (!frm.doc.start_date || !frm.doc.end_date) {
			frappe.msgprint(__('Please set both Start Date and End Date first.'));
			return;
		}

		frappe.call({
			method:
				'bsp_engineering.bsp_engineering.doctype.verti_weekly_wastage'
				+ '.verti_weekly_wastage.fetch_weekly_data',
			args: {
				start_date: frm.doc.start_date,
				end_date: frm.doc.end_date,
			},
			freeze: true,
			freeze_message: __('Fetching weekly production...'),
			callback(r) {
				if (!r.message) return;
				frm.set_value('total_weekly_work_kg', r.message.total_weekly_work_kg);
				calculate_wastage_figures(frm);

				frappe.show_alert({
					message: __('Total weekly work: {0} KG', [r.message.total_weekly_work_kg]),
					indicator: 'green',
				});
			},
		});
	}).addClass('btn-primary');
}
