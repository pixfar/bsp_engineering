console.log("BSP: query_report_columns.js LOADED ✓");
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
        return _orig_render_datatable.call(this);
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
