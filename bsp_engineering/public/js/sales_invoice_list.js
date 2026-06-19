frappe.listview_settings['Sales Invoice'] = {
	add_fields: [
		'customer',
		'customer_name',
		'base_grand_total',
		'outstanding_amount',
		'due_date',
		'company',
		'currency',
		'is_return',
	],
	get_indicator(doc) {
		if (cint(doc.is_return)) {
			if (doc.docstatus === 2) {
				return [
					__('Credit Note Cancelled'),
					'red',
					'is_return,=,1',
				];
			}
			if (doc.docstatus === 0) {
				return [
					__('Credit Note (Draft)'),
					'orange',
					'is_return,=,1',
				];
			}
			return [__('Credit Note'), 'purple', 'is_return,=,1'];
		}

		const status_colors = {
			Draft: 'red',
			Unpaid: 'orange',
			Paid: 'green',
			Return: 'gray',
			'Credit Note Issued': 'blue',
			'Unpaid and Discounted': 'orange',
			'Partly Paid and Discounted': 'yellow',
			'Overdue and Discounted': 'red',
			Overdue: 'red',
			'Partly Paid': 'yellow',
			'Internal Transfer': 'darkgrey',
			Cancelled: 'red',
		};
		return [
			__(doc.status),
			status_colors[doc.status] || 'blue',
			'status,=,' + doc.status,
		];
	},
	right_column: 'grand_total',
	onload(listview) {
		if (frappe.model.can_create('Delivery Note')) {
			listview.page.add_action_item(__('Delivery Note'), () => {
				erpnext.bulk_transaction_processing.create(
					listview,
					'Sales Invoice',
					'Delivery Note'
				);
			});
		}

		if (frappe.model.can_create('Payment Entry')) {
			listview.page.add_action_item(__('Payment'), () => {
				erpnext.bulk_transaction_processing.create(
					listview,
					'Sales Invoice',
					'Payment Entry'
				);
			});
		}
	},
};
