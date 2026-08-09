// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.ui.form.on('Verti Daily Production', {
	refresh(frm) {
		setup_fetch_attendance_button(frm);
	},
	date(frm) {
		recalculate(frm);
	},
	total_work_kg(frm) {
		recalculate(frm);
	},
	rate_per_kg(frm) {
		recalculate(frm);
	},
});

frappe.ui.form.on('Verti Daily Production Detail', {
	point(frm) {
		distribute_wage(frm);
	},
	present_employees_remove(frm) {
		distribute_wage(frm);
	},
});

function recalculate(frm) {
	calculate_total_wage(frm);
	distribute_wage(frm);
}

function calculate_total_wage(frm) {
	frm.set_value('total_wage', flt(frm.doc.total_work_kg) * flt(frm.doc.rate_per_kg));
}

function distribute_wage(frm) {
	// Per Point Rate = Total Wage / Sum of Points; daily_salary = point *
	// Per Point Rate. Mirrors the server's own distribute_wage() (validate())
	// exactly, purely so the grid updates live without a save round trip --
	// the server recalculates from scratch on save regardless, so this
	// can never be the actual source of truth for the saved amount.
	const rows = frm.doc.present_employees || [];
	if (!rows.length) return;

	const total_points = rows.reduce((sum, row) => sum + flt(row.point), 0);
	if (total_points <= 0) {
		rows.forEach((row) => {
			frappe.model.set_value(row.doctype, row.name, 'daily_salary', 0);
		});
		frm.refresh_field('present_employees');
		return;
	}

	const per_point_rate = flt(frm.doc.total_wage) / total_points;
	rows.forEach((row) => {
		frappe.model.set_value(row.doctype, row.name, 'daily_salary', flt(row.point) * per_point_rate);
	});
	frm.refresh_field('present_employees');
}

function setup_fetch_attendance_button(frm) {
	if (frm.doc.docstatus !== 0) return;

	frm.add_custom_button(__('Fetch Attendance'), () => {
		if (!frm.doc.date) {
			frappe.msgprint(__('Please set the Date first.'));
			return;
		}

		frappe.call({
			method:
				'bsp_engineering.bsp_engineering.doctype.verti_daily_production'
				+ '.verti_daily_production.fetch_attendance',
			args: { date: frm.doc.date },
			freeze: true,
			freeze_message: __('Fetching attendance...'),
			callback(r) {
				if (!r.message) return;

				frm.clear_table('present_employees');
				r.message.forEach((emp) => {
					const row = frm.add_child('present_employees');
					row.employee = emp.employee;
					row.employee_name = emp.employee_name;
					row.point = emp.point;
				});
				frm.refresh_field('present_employees');
				recalculate(frm);

				frappe.show_alert({
					message: __('{0} present employee(s) fetched.', [r.message.length]),
					indicator: 'green',
				});
			},
		});
	}).addClass('btn-primary');
}
