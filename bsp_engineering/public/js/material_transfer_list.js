frappe.listview_settings['Material Transfer'] = {
	add_fields: ['transfer_status', 'from_warehouse', 'to_warehouse'],
	get_indicator(doc) {
		const colors = {
			'In Transit': 'blue',
			'Partially Received': 'yellow',
			'Fully Received': 'green',
			Pending: 'orange',
			Received: 'green',
		};
		const color = colors[doc.transfer_status] || 'gray';
		return [
			__(doc.transfer_status || 'In Transit'),
			color,
			'transfer_status,=,' + doc.transfer_status,
		];
	},
};
