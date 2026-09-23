console.log("BSP: bsp_column_picker.js loaded");
frappe.provide("frappe.views");

// -----------------------------------------------------------------------
// BSP: Pick Columns — global column visibility for Query Reports
// Stored per user+report in "Report Column Visibility" DocType.
// -----------------------------------------------------------------------

function bsp_open_pick_columns_dialog(report) {
    if (!report || !report.columns || !report.columns.length) {
        frappe.msgprint(__("Please run the report first."));
        return;
    }

    let d = new frappe.ui.Dialog({
        title: __("Pick Columns"),
        fields: [{
            label: __("Select columns to show"),
            fieldname: "columns",
            fieldtype: "MultiCheck",
            options: report.columns.map((col) => ({
                label: col.label || col.name || col.fieldname || col.id,
                value: col.fieldname || col.id,
                checked: !col.hidden
            }))
        }],
        primary_action_label: __("Apply"),
        primary_action: (values) => {
            let selected = values.columns || [];
            report.columns.forEach((col) => {
                let col_id = col.fieldname || col.id;
                col.hidden = !selected.includes(col_id);
            });
            report.render_datatable();

            // Save to DocType safely via Python API to prevent duplicates
            frappe.call({
                method: "bsp_engineering.api.report_prefs.save_column_visibility",
                args: {
                    report_name: report.report_name,
                    visible_columns: JSON.stringify(selected)
                },
                callback: function(r) {
                    if (r.message) {
                        report._bsp_col_prefs = { docname: r.message, visible_columns: selected };
                    }
                }
            });
            d.hide();
        }
    });

    d.set_secondary_action_label(__("Reset to Default"));
    d.set_secondary_action(() => {
        let prefs = report._bsp_col_prefs;
        if (prefs && prefs.docname) {
            frappe.db.delete_doc("Report Column Visibility", prefs.docname).then(() => {
                report._bsp_col_prefs = null;
                report.columns.forEach(col => {
                    col.hidden = col._bsp_original_hidden || false;
                });
                report.render_datatable();
                d.hide();
            });
        } else {
            report.columns.forEach(col => {
                col.hidden = col._bsp_original_hidden || false;
            });
            report.render_datatable();
            d.hide();
        }
    });

    d.show();
}

function bsp_apply_column_prefs(report, visible_columns) {
    if (!visible_columns || !report.columns) return;
    report.columns.forEach(col => {
        if (col._bsp_original_hidden === undefined) {
            col._bsp_original_hidden = col.hidden || false;
        }
        let col_id = col.fieldname || col.id;
        col.hidden = !visible_columns.includes(col_id);
    });
}

function bsp_add_pick_columns_button(report) {
    if (!report || !report.page) return;
    let page = report.page;

    // Don't add twice
    if (page.wrapper.find(".bsp-pick-columns-btn").length) return;

    page.add_button(__("Pick Columns"), () => {
        bsp_open_pick_columns_dialog(report);
    }).addClass("bsp-pick-columns-btn");
}

// -----------------------------------------------------------------------
// BSP: Query Reports open sorted by their date column, newest first, so the
// latest transactions are at the top. Only the view is sorted (the datatable
// row order), not report.data, so exports and the total row are unchanged.
// Skipped for tree reports, for data already in descending date order, and
// for reports that set `bsp_default_date_sort: false` in their JS settings
// (e.g. statements whose rows are grouped per party).
// -----------------------------------------------------------------------
const BSP_DATE_SORT_FIELDS = ["posting_date", "date", "transaction_date", "posting_datetime"];

function bsp_find_date_column(report) {
    const visible = (report.columns || []).filter((col) => !col.hidden);
    const is_date = (col) => ["Date", "Datetime"].includes(col.fieldtype);
    return (
        visible.find((col) => is_date(col) && BSP_DATE_SORT_FIELDS.includes(col.fieldname)) ||
        visible.find((col) => is_date(col) && ["Date", "Posting Date"].includes(col.label))
    );
}

function bsp_apply_default_date_sort(report) {
    const datatable = report.datatable;
    if (!datatable || !datatable.datamanager || report.tree_report) return;
    if (report.report_settings && report.report_settings.bsp_default_date_sort === false) return;

    const date_col = bsp_find_date_column(report);
    if (!date_col) return;

    const dt_col = datatable.datamanager
        .getColumns()
        .find((col) => col.id === date_col.fieldname || col.id === date_col.id);
    if (!dt_col || (dt_col.sortOrder && dt_col.sortOrder !== "none")) return;

    // Already newest-first -> leave the report's own order alone.
    const dates = (report.data || [])
        .map((row) => row && row[date_col.fieldname])
        .filter(Boolean)
        .map(String);
    if (dates.length < 2) return;
    const already_desc = dates.every((d, i) => i === 0 || dates[i - 1] >= d);
    if (already_desc) return;

    // Reverse first so rows sharing the same date also end up newest-first
    // (the datatable's sort keeps the existing order for equal values).
    datatable.datamanager.rowViewOrder.reverse();
    datatable.sortColumn(dt_col.colIndex, "desc");
}

// -----------------------------------------------------------------------
// BSP: every Query Report (custom and ERPNext's own) fits its columns to
// the window instead of using each column's fixed width. A report can opt
// out with `bsp_fit_columns: false` in its JS settings.
//  - Each column gets at least the width its data needs (measured from the
//    first rows), capped so one long text column (e.g. Item Name) can't take
//    over -- longer text is cut with "...".
//  - Header labels wrap onto more lines instead of widening the column.
//  - Space left over is shared out equally, so the table always fills the
//    window; re-fitted when the window is resized.
// Only when the needed widths add up to more than the window (e.g. a report
// with 20+ warehouse columns) does the table scroll sideways.
// -----------------------------------------------------------------------
const BSP_FIT_MIN_WIDTH = 60;
const BSP_FIT_MAX_WIDTH = 240;
// Free-text columns (names, descriptions, remarks) are capped tighter.
const BSP_FIT_MAX_TEXT_WIDTH = 200;
const BSP_FIT_TEXT_FIELDTYPES = ["Data", "Small Text", "Text", "Long Text", "Text Editor", "Dynamic Link"];
const BSP_FIT_PADDING = 22;
const BSP_FIT_SAMPLE_ROWS = 100;
let bsp_fit_canvas = null;

function bsp_should_fit(report) {
    if (!report || report.tree_report) return false;
    return !(report.report_settings && report.report_settings.bsp_fit_columns === false);
}

function bsp_text_width(text, font) {
    bsp_fit_canvas = bsp_fit_canvas || document.createElement("canvas");
    const ctx = bsp_fit_canvas.getContext("2d");
    ctx.font = font;
    return ctx.measureText(text).width;
}

function bsp_cell_text(value, col, row) {
    if (value === null || value === undefined || value === "") return "";
    let text = value;
    try {
        text = frappe.format(value, col, { only_value: true }, row);
    } catch (e) {
        text = value;
    }
    return String(text).replace(/<[^>]*>/g, "").replace(/&nbsp;/g, " ").trim();
}

function bsp_inject_fit_styles() {
    if (document.getElementById("bsp-fit-report-style")) return;
    const style = document.createElement("style");
    style.id = "bsp-fit-report-style";
    // Wrap header labels instead of cutting them off with "...". Frappe pins
    // every datatable row at 35px, so the header row must be let grow too or
    // the wrapped label spills over the filter row below it.
    style.textContent = `
        .bsp-fit-report .dt-header .dt-row-header {
            height: auto !important;
        }
        .bsp-fit-report .dt-row-header .dt-cell--header,
        .bsp-fit-report .dt-row-header .dt-cell--header .dt-cell__content {
            height: auto !important;
            white-space: normal !important;
            text-overflow: clip !important;
            line-height: 1.25;
        }
        .bsp-fit-report .dt-row-header .dt-cell--header .dt-cell__content {
            word-break: normal;
            overflow-wrap: break-word;
            padding-right: 18px;
        }
    `;
    document.head.appendChild(style);
}

function bsp_available_width(report) {
    const $candidates = [report.$report, report.$report && report.$report.parent(), $(report.page && report.page.main)];
    for (const $el of $candidates) {
        const width = $el && $el.length ? $el.width() : 0;
        if (width) return width;
    }
    return 0;
}

function bsp_fit_columns_to_window(report) {
    if (!bsp_should_fit(report)) return;
    const columns = (report.columns || []).filter((col) => !col.hidden);
    if (!columns.length) return;

    const available = bsp_available_width(report);
    if (!available) return;

    bsp_inject_fit_styles();
    report.$report.addClass("bsp-fit-report");
    bsp_bind_fit_resize(report);

    const body_font = getComputedStyle(document.body);
    const font = `13px ${body_font.fontFamily}`;
    const header_font = `600 13px ${body_font.fontFamily}`;
    const rows = (report.data || []).slice(0, BSP_FIT_SAMPLE_ROWS);

    const needed = columns.map((col) => {
        // Header can wrap, so it only needs room for its longest word.
        const label_words = String(col.name || col.label || "").split(/\s+/);
        let need = Math.max(...label_words.map((w) => bsp_text_width(w, header_font)));
        for (const row of rows) {
            if (!row) continue;
            const text = bsp_cell_text(row[col.fieldname], col, row);
            if (text) need = Math.max(need, bsp_text_width(text, font));
        }
        const is_text =
            BSP_FIT_TEXT_FIELDTYPES.includes(col.fieldtype) || /(^|_)(name|description|remarks)$/.test(col.fieldname || "");
        const max = is_text ? BSP_FIT_MAX_TEXT_WIDTH : BSP_FIT_MAX_WIDTH;
        return Math.min(max, Math.max(BSP_FIT_MIN_WIDTH, Math.ceil(need + BSP_FIT_PADDING)));
    });

    // Row-number column + vertical scrollbar + borders.
    const row_index_width = String((report.data || []).length).length * 9 + 30;
    const usable = available - row_index_width - 20;
    const total_needed = needed.reduce((a, b) => a + b, 0);
    const extra = Math.max(0, usable - total_needed);

    // Equal share of the leftover space, so wide text columns don't grow
    // further at the expense of the narrow numeric ones.
    const share = extra / columns.length;
    columns.forEach((col, idx) => {
        col.width = Math.floor(needed[idx] + share);
    });
}

function bsp_bind_fit_resize(report) {
    if (report._bsp_fit_resize_bound) return;
    report._bsp_fit_resize_bound = true;
    let timer = null;
    $(window).on("resize", () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
            if (frappe.query_report !== report || !report.datatable) return;
            if (!frappe.get_route || frappe.get_route()[0] !== "query-report") return;
            report.render_datatable();
        }, 300);
    });
}

// Patch the QueryReport prototype once it's available
let bsp_patch_interval = setInterval(() => {
    if (!frappe.views || !frappe.views.QueryReport) return;
    if (frappe.views.QueryReport.prototype._bsp_patched) return;
    
    clearInterval(bsp_patch_interval);
    frappe.views.QueryReport.prototype._bsp_patched = true;

    // Hook into render_datatable to apply saved prefs
    const _orig_render_datatable = frappe.views.QueryReport.prototype.render_datatable;
    frappe.views.QueryReport.prototype.render_datatable = function() {
        // If we have prefs, apply them before rendering
        if (this._bsp_col_prefs && this._bsp_col_prefs.visible_columns) {
            bsp_apply_column_prefs(this, this._bsp_col_prefs.visible_columns);
        }
        bsp_fit_columns_to_window(this);
        const result = _orig_render_datatable.call(this);
        bsp_apply_default_date_sort(this);
        return result;
    };

    // Hook into setup_page_head to inject the button
    const _orig_setup_page_head = frappe.views.QueryReport.prototype.setup_page_head;
    frappe.views.QueryReport.prototype.setup_page_head = function() {
        _orig_setup_page_head.call(this);
        bsp_add_pick_columns_button(this);
    };

    // Hook into refresh to load prefs EARLY but after report_name is set
    const _orig_refresh = frappe.views.QueryReport.prototype.refresh;
    frappe.views.QueryReport.prototype.refresh = function() {
        let res = _orig_refresh.apply(this, arguments);
        this._bsp_load_and_apply_prefs();
        return res;
    };

    frappe.views.QueryReport.prototype._bsp_load_and_apply_prefs = function() {
        let report = this;
        if (!report.report_name) return; // Wait until report_name is set
        if (report._bsp_prefs_loaded_for === report.report_name) return;
        report._bsp_prefs_loaded_for = report.report_name;

        frappe.db.get_list("Report Column Visibility", {
            filters: { user: frappe.session.user, report_name: report.report_name },
            fields: ["name", "visible_columns"],
            order_by: "creation desc",
            limit: 1
        }).then(records => {
            if (records && records.length) {
                let visible = JSON.parse(records[0].visible_columns);
                report._bsp_col_prefs = { docname: records[0].name, visible_columns: visible };
                if (report.columns && report.columns.length) {
                    bsp_apply_column_prefs(report, visible);
                    if (report.datatable) {
                        report.render_datatable();
                    }
                }
            } else {
                report._bsp_col_prefs = null;
            }
        });
    };

    // If a report is already active (e.g. hard refresh race condition), trigger load immediately
    if (frappe.query_report && frappe.query_report.report_name) {
        frappe.query_report._bsp_load_and_apply_prefs();
        // Since setup_page_head might have already run, inject button if missing
        bsp_add_pick_columns_button(frappe.query_report);
    }

}, 100);

// Secondary safety net: poll for the active report view and inject button
setInterval(() => {
    if (frappe.get_route && frappe.get_route()[0] === "query-report" && frappe.query_report) {
        bsp_add_pick_columns_button(frappe.query_report);
    }
}, 1000);

// -----------------------------------------------------------------------
// BSP: Item link cells in Query Reports show the item code only.
// ERPNext registers frappe.form.link_formatters["Item"], which renders an
// Item Link as "code: item_name" whenever the row also has item_name.
// Query reports already carry a separate Item Name column, so the name
// shows twice. Wrap the formatter (whenever ERPNext assigns it - this file
// may load before erpnext's bundle) and skip it on query-report pages.
// Forms, child tables and list views keep the ERPNext behaviour.
// -----------------------------------------------------------------------
(function bsp_patch_item_link_formatter() {
    const formatters = frappe.provide("frappe.form.link_formatters");
    let _item_formatter = formatters["Item"];

    const is_query_report = () =>
        frappe.get_route && (frappe.get_route() || [])[0] === "query-report";

    Object.defineProperty(formatters, "Item", {
        configurable: true,
        enumerable: true,
        get() {
            if (!_item_formatter) return undefined;
            return function (value, doc, docfield) {
                if (is_query_report()) return value;
                return _item_formatter.call(this, value, doc, docfield);
            };
        },
        set(fn) {
            _item_formatter = fn;
        },
    });
})();
