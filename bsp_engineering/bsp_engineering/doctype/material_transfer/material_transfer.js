// Copyright (c) 2026, Pixfar and contributors
// For license information, please see license.txt

frappe.ui.form.on('Material Transfer', {
	refresh(frm) {
		toggle_status_visibility(frm);
		sync_item_code_query(frm);
		set_status_indicator(frm);
		setup_action_buttons(frm);
	},
});

frappe.ui.form.on('Material Transfer Item', {
	item_group(frm, cdt, cdn) {
		handle_item_group_change(frm, cdt, cdn);
	},
	item_code(frm, cdt, cdn) {
		sync_item_group_from_item(frm, cdt, cdn);
	},
});

// ── Item query helpers (mirrors Requisition) ──────────────────────────────────

function material_transfer_item_code_query(item_group) {
	const filters = { has_variants: 0, disabled: 0 };
	if (item_group) filters.item_group = item_group;
	return { filters };
}

function sync_item_code_query(frm) {
	const query_fn = function (doc, cdt, cdn) {
		const row = locals[cdt] && locals[cdt][cdn];
		return material_transfer_item_code_query((row && row.item_group) || '');
	};
	frm.set_query('item_code', 'items', query_fn);

	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) return;
	(grid.grid_rows || []).forEach((grid_row) => {
		const field = grid_row.fields_dict && grid_row.fields_dict.item_code;
		if (field) {
			field.get_query = function () {
				return material_transfer_item_code_query(
					(grid_row.doc && grid_row.doc.item_group) || ''
				);
			};
		}
	});
}

function apply_item_code_query_to_row(frm, cdt, cdn) {
	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) return;
	const grid_row = grid.grid_rows_by_docname && grid.grid_rows_by_docname[cdn];
	if (!grid_row) return;
	const field = grid_row.fields_dict && grid_row.fields_dict.item_code;
	if (!field) return;
	const row = locals[cdt] && locals[cdt][cdn];
	field.get_query = function () {
		return material_transfer_item_code_query((row && row.item_group) || '');
	};
}

function handle_item_group_change(frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row) return;
	apply_item_code_query_to_row(frm, cdt, cdn);
	if (!row.item_code) return;
	frappe.db.get_value('Item', row.item_code, 'item_group', (r) => {
		if (r && r.item_group !== row.item_group) {
			frappe.model.set_value(cdt, cdn, 'item_code', '');
		}
	});
}

function sync_item_group_from_item(frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.item_code) return;
	frappe.db.get_value('Item', row.item_code, 'item_group', (r) => {
		if (r && r.item_group) {
			frappe.model.set_value(cdt, cdn, 'item_group', r.item_group);
		}
	});
	apply_item_code_query_to_row(frm, cdt, cdn);
}

// ── Status indicator ──────────────────────────────────────────────────────────

function toggle_status_visibility(frm) {
	frm.set_df_property('transfer_status', 'hidden', frm.is_new() ? 1 : 0);
	if (frm.is_new()) frm.page.clear_indicator();
}

function set_status_indicator(frm) {
	if (frm.is_new()) return;
	if (frm.doc.docstatus === 2) {
		frm.page.set_indicator(__('Cancelled'), 'red');
		return;
	}
	const colors = {
		'Pending':    'orange',
		'In Transit': 'blue',
		'Received':   'green',
	};
	const status = frm.doc.transfer_status;
	if (status) frm.page.set_indicator(__(status), colors[status] || 'blue');
}

// ── Action buttons ────────────────────────────────────────────────────────────

function setup_action_buttons(frm) {
	if (frm.is_new() || frm.doc.docstatus !== 1) return;
	if (frm.doc.transfer_status === 'Received') return;

	frappe.call({
		method: 'bsp_engineering.bsp_engineering.doctype.material_transfer.material_transfer.can_action',
		args: { transfer: frm.doc.name },
		callback(r) {
			if (!r.message || !r.message.can_action) return;

			// Accept Transfer: only while goods haven't been dispatched yet
			if (frm.doc.transfer_status === 'Pending') {
				frm.add_custom_button(__('Accept Transfer'), () => {
					frappe.confirm(
						__('Accept and dispatch this transfer from {0} to {1}?', [
							frm.doc.from_warehouse,
							frm.doc.to_warehouse,
						]),
						() => call_accept(frm)
					);
				}).addClass('btn-warning');
			}

			// Confirm Receipt: only once goods are In Transit (SE submitted)
			if (frm.doc.transfer_status === 'In Transit') {
				frm.add_custom_button(__('Confirm Receipt'), () => {
					frappe.confirm(
						__('Confirm receipt of all items for this transfer?'),
						() => {
							frappe.call({
								method: 'bsp_engineering.bsp_engineering.doctype.material_transfer.material_transfer.confirm_receipt',
								args: { transfer: frm.doc.name },
								freeze: true,
								freeze_message: __('Confirming receipt...'),
								callback(r) {
									if (!r.exc) frm.reload_doc();
								},
							});
						}
					);
				}).addClass('btn-primary');
			}
		},
	});
}

function call_accept(frm) {
	frappe.call({
		method: 'bsp_engineering.bsp_engineering.doctype.material_transfer.material_transfer.accept_transfer',
		args: { transfer: frm.doc.name },
		freeze: true,
		freeze_message: __('Accepting transfer...'),
		callback(r) {
			if (!r.exc) frm.reload_doc();
		},
	});
}


