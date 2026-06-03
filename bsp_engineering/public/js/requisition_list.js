frappe.listview_settings['Requisition'] = {
	add_fields: ['transfer_status', 'source_warehouse', 'target_warehouse'],
	get_indicator(doc) {
		const colors = {
			'Not Transferred': 'orange',
			'Partially Transferred': 'yellow',
			'Fully Transferred': 'green',
			'Over Transferred': 'red',
		};
		const color = colors[doc.transfer_status] || 'gray';
		return [__(doc.transfer_status || 'Not Transferred'), color, 'transfer_status,=,' + doc.transfer_status];
	},
};
