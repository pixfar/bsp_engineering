// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.ui.form.on('Requisition', {
	refresh(frm) {
		toggle_transfer_status_visibility(frm);
		sync_item_code_query(frm);
		setup_transfer_stock_button(frm);
		setup_confirm_receipt_button(frm);
		set_transfer_status_indicator(frm);
		setup_print_button(frm);
	},
});

function setup_print_button(frm) {
	if (frm.is_new()) return;
	frm.add_custom_button(__('Print'), function () {
		const url = frappe.urllib.get_full_url(
			'/api/method/frappe.utils.print_format.download_pdf?' +
			$.param({
				doctype: frm.doctype,
				name: frm.docname,
				format: 'BSP Requisition',
				no_letterhead: 0,
			})
		);
		window.open(url);
	}).addClass('btn-default');
}

frappe.ui.form.on('Requisition Item', {
	item_group(frm, cdt, cdn) {
		handle_item_group_change(frm, cdt, cdn);
	},
	item_code(frm, cdt, cdn) {
		sync_item_group_from_item(frm, cdt, cdn);
	},
});

function requisition_item_code_query(item_group) {
	const filters = { has_variants: 0, disabled: 0 };
	if (item_group) {
		filters.item_group = item_group;
	}
	return { filters };
}

function sync_item_code_query(frm) {
	const query_fn = function (doc, cdt, cdn) {
		const row = locals[cdt] && locals[cdt][cdn];
		return requisition_item_code_query((row && row.item_group) || '');
	};

	frm.set_query('item_code', 'items', query_fn);

	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) {
		return;
	}
	(grid.grid_rows || []).forEach((grid_row) => {
		const field = grid_row.fields_dict && grid_row.fields_dict.item_code;
		if (field) {
			field.get_query = function () {
				return requisition_item_code_query(
					(grid_row.doc && grid_row.doc.item_group) || ''
				);
			};
		}
	});
}

function apply_item_code_query_to_row(frm, cdt, cdn) {
	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) {
		return;
	}
	const grid_row = grid.grid_rows_by_docname && grid.grid_rows_by_docname[cdn];
	if (!grid_row) {
		return;
	}
	const field = grid_row.fields_dict && grid_row.fields_dict.item_code;
	if (!field) {
		return;
	}
	const row = locals[cdt] && locals[cdt][cdn];
	field.get_query = function () {
		return requisition_item_code_query((row && row.item_group) || '');
	};
}

function handle_item_group_change(frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row) {
		return;
	}

	apply_item_code_query_to_row(frm, cdt, cdn);

	if (!row.item_code) {
		return;
	}

	frappe.db.get_value('Item', row.item_code, 'item_group', (r) => {
		if (r && r.item_group !== row.item_group) {
			frappe.model.set_value(cdt, cdn, 'item_code', '');
		}
	});
}

function sync_item_group_from_item(frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.item_code) {
		return;
	}
	frappe.db.get_value('Item', row.item_code, 'item_group', (r) => {
		if (r && r.item_group) {
			frappe.model.set_value(cdt, cdn, 'item_group', r.item_group);
		}
	});
	apply_item_code_query_to_row(frm, cdt, cdn);
}

function toggle_transfer_status_visibility(frm) {
	const hide = frm.is_new();
	frm.set_df_property('transfer_status', 'hidden', hide);
	if (hide) {
		frm.page.clear_indicator();
	}
}

function setup_transfer_stock_button(frm) {
	if (frm.is_new() || frm.doc.docstatus !== 1) return;
	if (frm.doc.transfer_status === 'Fully Transferred') return;

	frappe.call({
		method: 'bsp_engineering.bsp_engineering.doctype.requisition.requisition.can_create_stock_entry',
		args: { requisition: frm.doc.name },
		callback(r) {
			if (r.message && r.message.can_create) {
				frm.add_custom_button(
					__('Transfer Stock'),
					() => create_stock_entry_from_requisition(frm),
					__('Create')
				);
			}
		},
	});
}

function create_stock_entry_from_requisition(frm) {
	frappe.call({
		method:
			'bsp_engineering.bsp_engineering.doctype.requisition.requisition'
			+ '.make_stock_entry',
		args: { requisition: frm.doc.name },
		freeze: true,
		freeze_message: __('Creating Stock Entry...'),
		callback(r) {
			if (!r.exc && r.message) {
				frappe.model.sync(r.message);
				frappe.set_route('Form', 'Stock Entry', r.message.name);
			}
		},
	});
}

function setup_confirm_receipt_button(frm) {
	if (frm.is_new() || frm.doc.docstatus !== 1) return;
	if (frm.doc.transfer_status !== 'In Transit') return;
	if (frappe.session.user !== frm.doc.requested_by) return;

	frm.add_custom_button(__('Confirm Receipt'), () => {
		show_confirm_receipt_dialog(frm);
	}).addClass('btn-primary');
}

function show_confirm_receipt_dialog(frm) {
	frappe.call({
		method:
			'bsp_engineering.bsp_engineering.doctype.requisition.requisition'
			+ '.get_in_transit_se_items',
		args: { requisition: frm.doc.name },
		freeze: true,
		freeze_message: __('Loading items...'),
		callback(r) {
			if (r.exc || !r.message) {
				return;
			}

			const { items } = r.message;
			if (!items || !items.length) {
				frappe.msgprint(__('No items found to confirm.'));
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: __('Confirm Receipt'),
				size: 'large',
				fields: [
					{
						fieldtype: 'HTML',
						fieldname: 'receipt_items_html',
					},
				],
				primary_action_label: __('Confirm Receipt'),
				primary_action() {
					submit_confirm_receipt(frm, dialog, items);
				},
			});

			const rows_html = items
				.map(
					(item) => `
					<tr data-se-item="${frappe.utils.escape_html(item.name)}">
						<td>${frappe.utils.escape_html(item.item_code || '')}</td>
						<td>${frappe.utils.escape_html(item.item_name || '')}</td>
						<td class="text-right sent-qty">
							${flt(item.qty)}
							<span class="text-muted">${frappe.utils.escape_html(item.uom || '')}</span>
						</td>
						<td>
							<input
								type="number"
								class="form-control input-sm received-qty-input"
								data-se-item="${frappe.utils.escape_html(item.name)}"
								value="${flt(item.qty)}"
								min="0"
								max="${flt(item.qty)}"
								step="any"
							/>
						</td>
					</tr>`
				)
				.join('');

			dialog.fields_dict.receipt_items_html.$wrapper.html(`
				<p class="text-muted small mb-3">
					${__(
						'Confirm the quantity actually received for each item. '
						+ 'Adjust if some units were damaged or missing.'
					)}
				</p>
				<div class="table-responsive">
					<table class="table table-bordered table-sm receipt-qty-table">
						<thead>
							<tr>
								<th>${__('Item Code')}</th>
								<th>${__('Item Name')}</th>
								<th class="text-right">${__('Sent Qty')}</th>
								<th>${__('Received Qty')}</th>
							</tr>
						</thead>
						<tbody>${rows_html}</tbody>
					</table>
				</div>
			`);

			dialog.show();
		},
	});
}

function submit_confirm_receipt(frm, dialog, items) {
	const received_quantities = {};
	let has_positive_qty = false;

	for (const item of items) {
		const input = dialog.$wrapper.find(
			`.received-qty-input[data-se-item="${item.name}"]`
		);
		const received_qty = flt(input.val());
		const sent_qty = flt(item.qty);

		if (received_qty < 0) {
			frappe.msgprint({
				title: __('Invalid Quantity'),
				message: __('Received quantity cannot be negative for {0}.', [
					item.item_code,
				]),
				indicator: 'red',
			});
			return;
		}

		if (received_qty > sent_qty) {
			frappe.msgprint({
				title: __('Invalid Quantity'),
				message: __(
					'Received quantity ({0}) cannot exceed sent quantity ({1}) for {2}.',
					[received_qty, sent_qty, item.item_code]
				),
				indicator: 'red',
			});
			return;
		}

		received_quantities[item.name] = received_qty;
		if (received_qty > 0) {
			has_positive_qty = true;
		}
	}

	if (!has_positive_qty) {
		frappe.msgprint({
			title: __('Nothing to Confirm'),
			message: __('Enter at least one positive received quantity.'),
			indicator: 'orange',
		});
		return;
	}

	dialog.hide();

	frappe.call({
		method:
			'bsp_engineering.bsp_engineering.doctype.requisition.requisition'
			+ '.confirm_receipt_from_requisition',
		args: {
			requisition: frm.doc.name,
			received_quantities: JSON.stringify(received_quantities),
		},
		freeze: true,
		freeze_message: __('Confirming receipt...'),
		callback(r) {
			if (!r.exc) {
				frappe.show_alert({
					message: __('Receipt confirmed'),
					indicator: 'green',
				});
				frm.reload_doc();
			}
		},
	});
}

function set_transfer_status_indicator(frm) {
	if (frm.is_new()) return;

	if (frm.doc.docstatus === 2) {
		frm.page.set_indicator(__('Cancelled'), 'red');
		return;
	}

	if (!frm.doc.transfer_status) return;

	const colors = {
		'Not Transferred': 'orange',
		'In Transit': 'blue',
		'Partially Transferred': 'yellow',
		'Fully Transferred': 'green',
		'Over Transferred': 'red',
	};
	frm.page.set_indicator(
		__(frm.doc.transfer_status),
		colors[frm.doc.transfer_status] || 'blue'
	);
}
