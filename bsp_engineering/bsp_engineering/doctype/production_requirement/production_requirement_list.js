// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.listview_settings['Production Requirement'] = {
	add_fields: ['status', 'total_shortage_qty', 'total_plan_qty'],
	get_indicator(doc) {
		const colors = { Pending: 'gray', 'In Progress': 'orange', Completed: 'green', 'On Hold': 'yellow', Cancelled: 'red' };
		return [__(doc.status), colors[doc.status] || 'gray', `status,=,${doc.status}`];
	},
};
