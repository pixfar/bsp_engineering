// BSP report look for report PDFs and prints: a navy banner with the company
// and report name, the applied filters in a strip below it, column headers
// centred white-on-navy, compact banded rows and a tinted total row -- the
// same as on screen (public/css/bsp_report.bundle.css) and in Excel exports
// (overrides/query_report.py).
//
// Every report PDF/print is rendered client-side through Frappe's
// "print_template" page (Query Report "PDF"/"Print", Report Builder print),
// with the grid itself from "print_grid" unless the report ships its own
// print format. The styles are added to print_template so they reach the
// PDF too (wkhtmltopdf renders the posted HTML), and are scoped to
// .bsp-report-print so document print formats are untouched.
//
// wkhtmltopdf has no Bangla font on the server, so Bangla text and the Taka
// sign came out as boxes; the report uses the bundled Hind Siliguri (Latin +
// Bangla) instead. {{ base_url }} is filled in by print_template.

frappe.provide("bsp_engineering.report_print");

const BSP_REPORT_FONT_URL = "{{ base_url }}/assets/bsp_engineering/fonts/hind_siliguri";
const BSP_FILTERS_PER_ROW = 4;

const BSP_REPORT_PRINT_CSS = `
	@font-face {
		font-family: "Hind Siliguri";
		font-weight: normal;
		src: url("${BSP_REPORT_FONT_URL}/HindSiliguri-Regular.ttf") format("truetype");
	}
	@font-face {
		font-family: "Hind Siliguri";
		font-weight: bold;
		src: url("${BSP_REPORT_FONT_URL}/HindSiliguri-Bold.ttf") format("truetype");
	}
	.bsp-report-print,
	.bsp-report-print .print-format,
	.bsp-report-print table {
		font-family: "Hind Siliguri", sans-serif !important;
		-webkit-print-color-adjust: exact;
		print-color-adjust: exact;
	}
	.bsp-report-head {
		background-color: #1f3a5f;
		color: #ffffff;
		text-align: center;
		padding: 10px 12px 8px;
		margin: 0 0 10px 0;
		text-transform: uppercase;
	}
	/* Set on the lines themselves: the site's print style colours text
	   directly, which beats colour inherited from the banner. */
	.bsp-report-print .bsp-report-head,
	.bsp-report-print .bsp-report-head .bsp-report-company,
	.bsp-report-print .bsp-report-head .bsp-report-title {
		color: #ffffff !important;
	}
	.bsp-report-company {
		font-size: 18pt;
		font-weight: bold;
		line-height: 1.2;
	}
	.bsp-report-title {
		font-size: 12pt;
		font-weight: bold;
		line-height: 1.3;
		margin-top: 2px;
	}
	.bsp-report-print table.bsp-report-filters {
		margin: 0 auto 12px auto;
		border-collapse: collapse;
		width: auto;
	}
	.bsp-report-filters td {
		border: 1px solid #c8d2de;
		padding: 4px 10px !important;
		font-size: 8pt;
		white-space: nowrap;
	}
	.bsp-report-filters td.bsp-filter-label {
		background-color: #e6ecf3;
		color: #4a5b70;
		font-weight: bold;
		text-transform: none;
	}
	.bsp-report-filters td.bsp-filter-value {
		color: #1b2733;
		font-weight: bold;
	}
	.bsp-report-print table.table-bordered > thead > tr > th {
		background-color: #1f3a5f !important;
		color: #ffffff !important;
		text-align: center !important;
		vertical-align: middle !important;
		font-weight: bold;
		padding: 5px 4px !important;
		line-height: 1.2;
		border: 1px solid #34537a !important;
	}
	.bsp-report-print table.table-bordered > tbody > tr {
		height: auto !important;
	}
	.bsp-report-print table.table-bordered > tbody > tr > td {
		padding: 3px 5px !important;
		line-height: 1.25;
		vertical-align: middle;
		border-color: #c8d2de !important;
	}
	/* Dates on one line in every report PDF/print (see the print_grid patch). */
	.bsp-report-print table.table-bordered > tbody > tr > td[data-bsp-fieldtype="Date"],
	.bsp-report-print table.table-bordered > tbody > tr > td[data-bsp-fieldtype="Datetime"],
	.bsp-report-print table.table-bordered > tbody > tr > td[data-bsp-field$="date"],
	.bsp-report-print table.table-bordered > tbody > tr > td[data-bsp-field="date"] {
		white-space: nowrap;
	}
	.bsp-report-print table.table-bordered > tbody > tr:nth-child(even) > td {
		background-color: #f4f7fb;
	}
	.bsp-report-print table.table-bordered > tbody > tr.bsp-total-row > td {
		background-color: #dce6f2;
		font-weight: bold;
	}
`;

function bsp_plain_text(html) {
	return $("<div>").html(String(html)).text().trim();
}

function bsp_filter_display(value, df) {
	if (value === null || value === undefined || value === "") return "";
	if (Array.isArray(value)) {
		const is_range = df && df.fieldtype === "DateRange";
		const item_df = { fieldtype: is_range ? "Date" : "Data" };
		return value
			.map((v) => bsp_filter_display(v, item_df))
			.filter(Boolean)
			.join(is_range ? " - " : ", ");
	}
	if (df && df.fieldtype === "Check") return cint(value) ? __("Yes") : "";
	if (!df) return bsp_plain_text(value);
	return bsp_plain_text(frappe.format(value, df, { only_value: true, inline: true }));
}

// [{label, value}] for the filters that have a value, Company left out (it
// heads the banner).
function bsp_filter_items(ctx) {
	const controls = ((ctx.report && ctx.report.filters) || []).filter((c) => c && c.df);
	if (controls.length) {
		return controls
			.filter((c) => !c.df.hidden && c.df.fieldname !== "company")
			.map((c) => ({ label: __(c.df.label || c.df.fieldname), value: bsp_filter_display(c.get_value(), c.df) }))
			.filter((item) => item.value);
	}
	return Object.entries(ctx.filters || {})
		.filter(([key]) => key !== "company")
		.map(([key, value]) => ({ label: __(frappe.unscrub(key)), value: bsp_filter_display(value) }))
		.filter((item) => item.value);
}

function bsp_company(ctx) {
	return (
		(ctx.filters && ctx.filters.company) ||
		frappe.defaults.get_user_default("Company") ||
		(frappe.boot.sysdefaults && frappe.boot.sysdefaults.company) ||
		""
	);
}

// Banner + filter strip, used in place of print_grid's plain title/filters.
bsp_engineering.report_print.header = function (ctx) {
	ctx = ctx || {};
	const esc = frappe.utils.escape_html;
	const company = bsp_company(ctx);
	let html = `<div class="bsp-report-head">
		${company ? `<div class="bsp-report-company">${esc(company)}</div>` : ""}
		${ctx.title ? `<div class="bsp-report-title">${esc(__(ctx.title))}</div>` : ""}
	</div>`;

	const items = bsp_filter_items(ctx);
	if (items.length) {
		let rows = "";
		for (let i = 0; i < items.length; i += BSP_FILTERS_PER_ROW) {
			const cells = items
				.slice(i, i + BSP_FILTERS_PER_ROW)
				.map(
					(item) =>
						`<td class="bsp-filter-label">${esc(item.label)}</td><td class="bsp-filter-value">${esc(item.value)}</td>`
				)
				.join("");
			rows += `<tr>${cells}</tr>`;
		}
		html += `<table class="bsp-report-filters">${rows}</table>`;
	}
	return html;
};

(function bsp_style_report_prints() {
	const templates = frappe.templates || {};

	// Each replacement is skipped if a Frappe update changes the markup.
	if (templates.print_template && !templates.print_template.includes("bsp-report-print")) {
		templates.print_template = templates.print_template
			.replace("</head>", `<style>${BSP_REPORT_PRINT_CSS}</style></head>`)
			.replace('class="print-format-gutter"', 'class="print-format-gutter bsp-report-print"');
	}

	const grid = templates.print_grid;
	if (grid && !grid.includes("bsp_engineering.report_print")) {
		// print_grid opens with its title and (optional) filters block, then
		// the table. `obj` is the template's context object (see
		// frappe.template.compile), which may lack title/subtitle/filters.
		const table_start = grid.indexOf("<table");
		let patched =
			grid.indexOf("<!-- title -->") !== -1 && table_start !== -1
				? "{{ bsp_engineering.report_print.header(obj) }}\n" + grid.slice(table_start)
				: grid;
		// Mark the total row so it can be tinted like on screen.
		patched = patched.replace(
			'<tr style="height: 30px">',
			'<tr style="height: 30px" {% if (row.is_total_row) { %} class="bsp-total-row" {% } %}>'
		);
		// Tag each body cell with its column's fieldtype / fieldname so the CSS
		// below can keep dates on one line ("28-08-2026", not "28-08-" / "2026").
		patched = patched.replace(
			'<td {% if row.bold == 1 %} style="font-weight: bold" {% endif %} {% if longest_word',
			'<td data-bsp-fieldtype="{{ col.fieldtype || \'\' }}" data-bsp-field="{{ (col.fieldname || \'\').toLowerCase() }}" {% if row.bold == 1 %} style="font-weight: bold" {% endif %} {% if longest_word'
		);
		templates.print_grid = patched;
	}

	// Templates are compiled once and cached by name.
	delete frappe.template.compiled.print_template;
	delete frappe.template.compiled.print_grid;
})();
