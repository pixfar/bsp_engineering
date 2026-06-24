frappe.ui.form.on('Delivery Note', {
	refresh(frm) {
		setup_dn_print_button(frm);
	},
});

function setup_dn_print_button(frm) {
	if (frm.is_new()) return;
	frm.add_custom_button(__('Print Challan'), function () {
		const url = frappe.urllib.get_full_url(
			'/api/method/frappe.utils.pdf.download_pdf?' +
			$.param({ doctype: frm.doctype, name: frm.docname, format: 'BSP Delivery Note', no_letterhead: 0 })
		);
		window.open(url);
	}).addClass('btn-default');
}
