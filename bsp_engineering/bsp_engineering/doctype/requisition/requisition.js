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
		frappe.confirm(
			__('Confirm receipt of all items for this requisition?'),
			() => {
				frappe.call({
					method: 'bsp_engineering.bsp_engineering.doctype.requisition.requisition.confirm_receipt_from_requisition',
					args: { requisition: frm.doc.name },
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
