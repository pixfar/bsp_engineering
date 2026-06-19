const STANDARD_NAMING_SERIES = 'ACC-SINV-.YYYY.-';
const RETURN_NAMING_SERIES = 'ACC-SIN-RET.YYYY.-';
const LEGACY_RETURN_NAMING_SERIES = 'ACC-SINV-RET-.YYYY.-';

function apply_return_naming_series(frm) {
	if (frm.doc.docstatus) {
		return;
	}

	if (frm.doc.is_return) {
		if (frm.doc.naming_series !== RETURN_NAMING_SERIES) {
			frm.set_value('naming_series', RETURN_NAMING_SERIES);
		}
		return;
	}

	if (
		frm.doc.naming_series === RETURN_NAMING_SERIES
		|| frm.doc.naming_series === LEGACY_RETURN_NAMING_SERIES
	) {
		frm.set_value('naming_series', STANDARD_NAMING_SERIES);
	}
}

function handle_return_against(frm) {
	if (frm.doc.return_against || frm.doc.is_return) {
		frm.set_df_property('custom_is_paid', 'hidden', 1);
		frm.refresh_field('custom_is_paid');

		if (!frm.doc.docstatus && frm.doc.custom_is_paid) {
			frm.set_value('custom_is_paid', 0);
		}
		return;
	}

	frm.set_df_property('custom_is_paid', 'hidden', 0);
}

function set_return_invoice_indicator(frm) {
	if (frm.doc.is_return) {
		if (frm.doc.docstatus === 2) {
			frm.page.set_indicator(__('Credit Note Cancelled'), 'red');
			return;
		}

		if (frm.doc.docstatus === 1) {
			frm.page.set_indicator(__('Credit Note'), 'purple');
			return;
		}

		frm.page.set_indicator(__('Credit Note (Draft)'), 'orange');
		return;
	}

	if (frm.doc.status === 'Credit Note Issued' && frm.doc.docstatus === 1) {
		frm.page.set_indicator(__('Credit Note Issued'), 'blue');
	}
}

function show_return_invoice_links(frm) {
	if (frm.doc.is_return && frm.doc.return_against && frm.doc.docstatus) {
		const original = frappe.utils.escape_html(frm.doc.return_against);
		frm.dashboard.set_headline_alert(
			__(
				'This credit note is linked to the original invoice {0}. That invoice was not created again.',
				[`<a class="text-muted" href="/app/sales-invoice/${original}">${original}</a>`]
			),
			'blue'
		);
		return;
	}

	if (!frm.doc.is_return && frm.doc.docstatus === 1) {
		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'Sales Invoice',
				filters: {
					return_against: frm.doc.name,
					is_return: 1,
					docstatus: 1,
				},
				fields: ['name'],
			},
			callback(r) {
				const notes = (r.message || []).map((row) => row.name);
				if (!notes.length) {
					return;
				}

				const links = notes
					.map(
						(name) =>
							`<a class="text-muted" href="/app/sales-invoice/${frappe.utils.escape_html(name)}">${frappe.utils.escape_html(name)}</a>`
					)
					.join(', ');

				frm.dashboard.set_headline_alert(
					__('Linked credit note(s): {0}', [links]),
					'blue'
				);
			},
		});
	}
}

frappe.ui.form.on('Sales Invoice', {
	refresh(frm) {
		apply_return_naming_series(frm);
		handle_return_against(frm);
		set_return_invoice_indicator(frm);
		show_return_invoice_links(frm);
	},
	is_return(frm) {
		apply_return_naming_series(frm);
		handle_return_against(frm);
		set_return_invoice_indicator(frm);
	},
});
