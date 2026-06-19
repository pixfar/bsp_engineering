# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Restore BSP invoice print formats before browser-print CSS experiments."""

ORIGINAL_PRINT_CSS = """/* Browser print fixes for BSP Sales/Purchase Invoice (PDF uses wkhtmltopdf). */
@media print {
	@page {
		size: A4 portrait;
		margin: 10mm;
	}

	html,
	body {
		height: auto !important;
		overflow: visible !important;
	}

	.print-format-gutter {
		padding: 0 !important;
		background: #fff !important;
	}

	.print-format {
		padding: 0 !important;
		margin: 0 !important;
		min-height: 0 !important;
		max-width: none !important;
		width: 100% !important;
		border-radius: 0 !important;
		box-shadow: none !important;
	}

	#header-html,
	#footer-html,
	footer,
	.bsp-print-footer {
		display: block !important;
	}

	.visible-pdf.bsp-print-footer,
	#footer-html.bsp-print-footer,
	#footer-html {
		display: block !important;
	}

	.page-number,
	.visible-pdf.page-number {
		display: none !important;
	}

	#footer-html,
	.bsp-print-footer {
		page-break-inside: avoid;
		margin-top: 12px !important;
	}

	.letter-head-footer {
		page-break-inside: avoid;
		margin-top: 16px !important;
	}

	.bsp-print-spacer {
		padding-bottom: 12px !important;
		min-height: 0 !important;
	}

	table.table-bordered {
		page-break-inside: auto;
	}

	table.table-bordered tr {
		page-break-inside: avoid;
	}
}
"""

ORIGINAL_INLINE_PRINT_STYLE = (
	'<style class="bsp-invoice-print-style">'
	'@media print{'
	'.print-format-gutter{padding:0!important}'
	'.print-format{padding:0!important;min-height:0!important}'
	'#footer-html,#header-html{display:block!important}'
	'}'
	'</style>'
)

SIGNATURE_BLOCK = """        <div class="letter-head-footer" style="margin-top: 16px; padding-bottom: 5px;">
            <div style="float: left; width: 35%;">
                <div style="border-top: 1px solid #000; padding-top: 5px; text-align: center;">
                    <b>Received in good condition by</b>
                </div>
            </div>
            
            <div style="float: right; width: 35%;">
                <div style="border-top: 1px solid #000; padding-top: 5px; text-align: center;">
                    <b>For BSP Engineering Works</b>
                </div>
            </div>
            <div style="clear: both;"></div>
        </div>

"""

SPACER_BLOCK = (
	'<div class="row section-break bsp-print-spacer" '
	'style="margin: 0px !important; padding-bottom: 12px !important;">\n'
	'</div>\n\n\n'
)

BSP_INVOICE_PRINT_FORMATS = (
	'BSP Sales Invoice',
	'BSP Purchase Invoice',
)

_MODIFIED_INLINE_STYLES = (
	'@media print{'
	'.print-format-gutter{padding:0!important}'
	'.print-format{padding:0!important;min-height:0!important;'
	'box-sizing:border-box!important}'
	'.print-format .row{margin-left:0!important;margin-right:0!important}'
	'.print-format [class*="col-"]{float:left!important}'
	'footer,.bsp-invoice-page-footer{position:fixed!important;'
	'left:0!important;right:0!important;bottom:0!important}'
	'.letter-head-footer,.bsp-print-spacer{display:none!important}'
	'#footer-html,#header-html{display:block!important}'
	'}',
	'@media print{'
	'.print-format-gutter{padding:0!important}'
	'.print-format{padding:0!important;min-height:0!important;'
	'box-sizing:border-box!important}'
	'.print-format .row{margin-left:0!important;margin-right:0!important}'
	'.print-format [class*="col-"]{float:left!important}'
	'#footer-html,#header-html{display:block!important}'
	'}',
	'@media print{'
	'.print-format-gutter{padding:0!important}'
	'.print-format{padding:0!important;min-height:0!important;'
	'box-sizing:border-box!important}'
	'.print-format .row{margin-left:0!important;margin-right:0!important}'
	'#footer-html,#header-html{display:block!important}'
	'}',
)


def _strip_pdf_handler_script(html):
	marker = '<script class="bsp-printview-pdf-handler">'
	while marker in html:
		start = html.index(marker)
		end = html.index('</script>', start) + len('</script>')
		html = html[:start] + html[end:]
	return html


def revert_bsp_invoice_html(html):
	if not html:
		return html

	html = _strip_pdf_handler_script(html)
	html = html.replace("<script>document.title='';</script>\n", '')
	html = html.replace("<script>document.title='';</script>", '')

	for style_block in _MODIFIED_INLINE_STYLES:
		html = html.replace(
			f'<style class="bsp-invoice-print-style">{style_block}</style>',
			ORIGINAL_INLINE_PRINT_STYLE,
		)

	if ORIGINAL_INLINE_PRINT_STYLE not in html:
		if '<style class="bsp-invoice-print-style">' in html:
			start = html.index('<style class="bsp-invoice-print-style">')
			end = html.index('</style>', start) + len('</style>')
			html = ORIGINAL_INLINE_PRINT_STYLE + html[end:]
		else:
			html = ORIGINAL_INLINE_PRINT_STYLE + html

	html = html.replace(
		'<div id="footer-html" class="bsp-print-footer bsp-invoice-page-footer">',
		'<div id="footer-html" class="bsp-print-footer">',
	)

	html = html.replace(
		'<div class="text-center bsp-footer-content" '
		'style="border-top: 1px solid #ddd; padding-top: 10px; margin-top: 0;">',
		'<div class="text-center" style="border-top: 1px solid #ddd; '
		'padding-top: 10px; margin-top: 10px;">',
	)

	if 'Received in good condition by' not in html:
		html = html.replace(
			'<div id="footer-html" class="bsp-print-footer">\n        \n        '
			'<div class="text-center"',
			'<div id="footer-html" class="bsp-print-footer">\n        \n'
			+ SIGNATURE_BLOCK
			+ '        <div class="text-center"',
		)

	if 'bsp-print-spacer' not in html:
		html = html.replace(
			'</div>\n\n<footer>',
			'</div>\n\n' + SPACER_BLOCK + '<footer>',
			1,
		)

	return html
