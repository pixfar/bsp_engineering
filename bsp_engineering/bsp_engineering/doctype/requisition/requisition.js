// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.ui.form.on('Requisition', {
	refresh(frm) {
		toggle_transfer_status_visibility(frm);
		sync_item_code_query(frm);
		setup_transfer_stock_button(frm);
		setup_confirm_receipt_button(frm);
		set_transfer_status_indicator(frm);
	},
});

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
		frappe.call({
			method: 'bsp_engineering.bsp_engineering.doctype.requisition.requisition.get_in_transit_se_items',
			args: { requisition: frm.doc.name },
			callback(r) {
				if (r.exc || !r.message) return;
				show_receipt_dialog(frm, r.message);
			},
		});
	}).addClass('btn-primary');
}

function show_receipt_dialog(frm, se_data) {
	const { items } = se_data;

	const rows_html = items.map(item => `
		<tr>
			<td style="vertical-align:middle; padding:6px 8px;">${item.item_code}</td>
			<td style="vertical-align:middle; padding:6px 8px;">${item.item_name || ''}</td>
			<td style="vertical-align:middle; text-align:right; padding:6px 8px; white-space:nowrap;">
				${item.qty} ${item.uom || ''}
			</td>
			<td style="padding:4px 8px;">
				<input
					type="number"
					class="form-control received-qty-input"
					data-item-name="${item.name}"
					data-max-qty="${item.qty}"
					value="${item.qty}"
					min="0"
					max="${item.qty}"
					step="any"
					style="text-align:right; min-width:80px;"
				>
			</td>
		</tr>
	`).join('');

	const dialog = new frappe.ui.Dialog({
		title: __('Confirm Receipt'),
		fields: [{
			fieldtype: 'HTML',
			fieldname: 'items_table',
			options: `
				<p style="font-size:12px; color:#6b7280; margin-bottom:10px;">
					${__('Reduce the Received Qty if any items were damaged or missing. Items set to 0 will be excluded.')}
				</p>
				<table class="table table-bordered table-sm" style="margin:0; font-size:13px;">
					<thead style="background:#f3f4f6;">
						<tr>
							<th style="padding:6px 8px;">${__('Item Code')}</th>
							<th style="padding:6px 8px;">${__('Item Name')}</th>
							<th style="padding:6px 8px; text-align:right;">${__('Sent Qty')}</th>
							<th style="padding:6px 8px;">${__('Received Qty')}</th>
						</tr>
					</thead>
					<tbody>${rows_html}</tbody>
				</table>
			`,
		}],
		primary_action_label: __('Confirm Receipt'),
		primary_action() {
			const received_quantities = {};
			let valid = true;

			dialog.$wrapper.find('.received-qty-input').each(function () {
				const $inp = $(this);
				const item_name = $inp.data('item-name');
				const max_qty = parseFloat($inp.data('max-qty'));
				const qty = parseFloat($inp.val());

				if (isNaN(qty) || qty < 0) {
					frappe.msgprint(__('Received quantity cannot be negative.'));
					valid = false;
					return false;
				}
				if (qty > max_qty) {
					frappe.msgprint(
						__('Received quantity cannot exceed sent quantity ({0}).').replace('{0}', max_qty)
					);
					valid = false;
					return false;
				}
				received_quantities[item_name] = qty;
			});

			if (!valid) return;

			frappe.call({
				method: 'bsp_engineering.bsp_engineering.doctype.requisition.requisition.confirm_receipt_from_requisition',
				args: {
					requisition: frm.doc.name,
					received_quantities: JSON.stringify(received_quantities),
				},
				freeze: true,
				freeze_message: __('Confirming receipt...'),
				callback(r) {
					if (!r.exc) {
						dialog.hide();
						frm.reload_doc();
					}
				},
			});
		},
	});

	dialog.show();
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
