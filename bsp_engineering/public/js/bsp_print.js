/* Copyright (c) 2026, Pixfar and contributors */
/* For license information, please see license.txt */

frappe.provide('bsp_engineering.print');

const BSP_PDF_PRINT_FORMATS = [
	'BSP Sales Invoice',
	'BSP Purchase Invoice',
];

const _original_printit = frappe.ui.form.PrintView.prototype.printit;

frappe.ui.form.PrintView.prototype.printit = function () {
	const format_name = this.selected_format();
	const use_pdf_print = BSP_PDF_PRINT_FORMATS.includes(format_name);
	const has_print_server = cint(this.print_settings.enable_print_server);
	const has_mapped_printer = this.get_mapped_printer().length === 1;
	const is_raw = this.is_raw_printing();

	if (use_pdf_print && !has_print_server && !has_mapped_printer && !is_raw) {
		this.print_via_pdf();
		return;
	}

	_original_printit.call(this);
};

frappe.ui.form.PrintView.prototype.print_via_pdf = function () {
	const me = this;
	const print_format = me.get_print_format();
	let method = '/api/method/frappe.utils.print_format.download_pdf?';

	if (print_format.print_format_builder_beta) {
		method = '/api/method/frappe.utils.weasyprint.download_pdf?';
	}

	const query =
		'doctype=' +
		encodeURIComponent(me.frm.doc.doctype) +
		'&name=' +
		encodeURIComponent(me.frm.doc.name) +
		'&format=' +
		encodeURIComponent(me.selected_format()) +
		'&no_letterhead=' +
		(me.with_letterhead() ? '0' : '1') +
		'&letterhead=' +
		encodeURIComponent(me.get_letterhead()) +
		'&settings=' +
		encodeURIComponent(JSON.stringify(me.additional_settings || {})) +
		(me.lang_code ? '&_lang=' + encodeURIComponent(me.lang_code) : '');

	const url = frappe.urllib.get_full_url(method + query);

	frappe.dom.freeze(__('Preparing PDF for print...'));

	fetch(url, {
		credentials: 'include',
		headers: {
			'X-Frappe-CSRF-Token': frappe.csrf_token,
		},
	})
		.then((response) => {
			if (!response.ok) {
				throw new Error(__('PDF generation failed'));
			}
			return response.blob();
		})
		.then((blob) => {
			frappe.dom.unfreeze();
			me._open_pdf_and_print(blob);
		})
		.catch((error) => {
			frappe.dom.unfreeze();
			frappe.msgprint({
				title: __('Print failed'),
				message: error.message || __('Could not generate PDF for printing.'),
				indicator: 'red',
			});
		});
};

frappe.ui.form.PrintView.prototype._open_pdf_and_print = function (blob) {
	const blob_url = URL.createObjectURL(blob);
	const iframe = document.createElement('iframe');
	iframe.style.cssText =
		'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden;';
	iframe.src = blob_url;
	document.body.appendChild(iframe);

	const cleanup = () => {
		if (iframe.parentNode) {
			iframe.parentNode.removeChild(iframe);
		}
		URL.revokeObjectURL(blob_url);
	};

	iframe.onload = () => {
		setTimeout(() => {
			try {
				iframe.contentWindow.focus();
				iframe.contentWindow.print();
			} catch (error) {
				window.open(blob_url);
				frappe.show_alert({
					message: __('PDF opened in a new tab. Print from the browser PDF viewer.'),
					indicator: 'blue',
				});
				setTimeout(cleanup, 60000);
				return;
			}
			setTimeout(cleanup, 60000);
		}, 600);
	};
};
