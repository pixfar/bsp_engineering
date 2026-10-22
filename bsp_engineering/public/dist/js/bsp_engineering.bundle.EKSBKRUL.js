(() => {
  var __defProp = Object.defineProperty;
  var __defProps = Object.defineProperties;
  var __getOwnPropDescs = Object.getOwnPropertyDescriptors;
  var __getOwnPropSymbols = Object.getOwnPropertySymbols;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __propIsEnum = Object.prototype.propertyIsEnumerable;
  var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
  var __spreadValues = (a, b) => {
    for (var prop in b || (b = {}))
      if (__hasOwnProp.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    if (__getOwnPropSymbols)
      for (var prop of __getOwnPropSymbols(b)) {
        if (__propIsEnum.call(b, prop))
          __defNormalProp(a, prop, b[prop]);
      }
    return a;
  };
  var __spreadProps = (a, b) => __defProps(a, __getOwnPropDescs(b));

  // ../bsp_engineering/bsp_engineering/public/js/native_string_trim.js
  (function restore_native_string_trim() {
    const is_native = (fn) => typeof fn === "function" && /\[native code\]/.test(Function.prototype.toString.call(fn));
    const names = ["trim", "trimStart", "trimEnd", "trimLeft", "trimRight"];
    if (names.every((name) => !String.prototype[name] || is_native(String.prototype[name])))
      return;
    if (typeof document === "undefined" || !document.documentElement)
      return;
    let frame;
    try {
      frame = document.createElement("iframe");
      frame.style.display = "none";
      document.documentElement.appendChild(frame);
      const clean = frame.contentWindow && frame.contentWindow.String && frame.contentWindow.String.prototype;
      if (!clean)
        return;
      for (const name of names) {
        const native = clean[name];
        if (is_native(native) && !is_native(String.prototype[name])) {
          Object.defineProperty(String.prototype, name, {
            value: native,
            writable: true,
            configurable: true,
            enumerable: false
          });
        }
      }
    } catch (e) {
    } finally {
      if (frame)
        frame.remove();
    }
  })();

  // ../bsp_engineering/bsp_engineering/public/js/bsp_column_picker.js
  console.log("BSP: bsp_column_picker.js loaded");
  frappe.provide("frappe.views");
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
        report._bsp_col_prefs = {
          docname: report._bsp_col_prefs && report._bsp_col_prefs.docname,
          visible_columns: selected
        };
        report.render_datatable();
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
          report.columns.forEach((col) => {
            col.hidden = col._bsp_original_hidden || false;
          });
          report.render_datatable();
          d.hide();
        });
      } else {
        report.columns.forEach((col) => {
          col.hidden = col._bsp_original_hidden || false;
        });
        report.render_datatable();
        d.hide();
      }
    });
    d.show();
  }
  function bsp_apply_column_prefs(report, visible_columns) {
    if (!visible_columns || !report.columns)
      return;
    report.columns.forEach((col) => {
      if (col._bsp_original_hidden === void 0) {
        col._bsp_original_hidden = col.hidden || false;
      }
      let col_id = col.fieldname || col.id;
      col.hidden = !visible_columns.includes(col_id);
    });
  }
  function bsp_add_pick_columns_button(report) {
    if (!report || !report.page)
      return;
    let page = report.page;
    if (page.wrapper.find(".bsp-pick-columns-btn").length)
      return;
    page.add_button(__("Pick Columns"), () => {
      bsp_open_pick_columns_dialog(report);
    }).addClass("bsp-pick-columns-btn");
  }
  var BSP_DATE_SORT_FIELDS = ["posting_date", "date", "transaction_date", "posting_datetime"];
  function bsp_find_date_column(report) {
    const visible = (report.columns || []).filter((col) => !col.hidden);
    const is_date = (col) => ["Date", "Datetime"].includes(col.fieldtype);
    return visible.find((col) => is_date(col) && BSP_DATE_SORT_FIELDS.includes(col.fieldname)) || visible.find((col) => is_date(col) && ["Date", "Posting Date"].includes(col.label));
  }
  function bsp_apply_default_date_sort(report) {
    const datatable = report.datatable;
    if (!datatable || !datatable.datamanager || report.tree_report)
      return;
    if (report.report_settings && report.report_settings.bsp_default_date_sort === false)
      return;
    const date_col = bsp_find_date_column(report);
    if (!date_col)
      return;
    const dt_col = datatable.datamanager.getColumns().find((col) => col.id === date_col.fieldname || col.id === date_col.id);
    if (!dt_col || dt_col.sortOrder && dt_col.sortOrder !== "none")
      return;
    const dates = (report.data || []).map((row) => row && row[date_col.fieldname]).filter(Boolean).map(String);
    if (dates.length < 2)
      return;
    const already_desc = dates.every((d, i) => i === 0 || dates[i - 1] >= d);
    if (already_desc)
      return;
    datatable.datamanager.rowViewOrder.reverse();
    datatable.sortColumn(dt_col.colIndex, "desc");
  }
  var BSP_FIT_MIN_WIDTH = 60;
  var BSP_FIT_MAX_WIDTH = 240;
  var BSP_FIT_MAX_TEXT_WIDTH = 200;
  var BSP_FIT_TEXT_FIELDTYPES = ["Data", "Small Text", "Text", "Long Text", "Text Editor", "Dynamic Link"];
  var BSP_FIT_PADDING = 22;
  var BSP_FIT_HEADER_PADDING = 24;
  var BSP_FIT_SAMPLE_ROWS = 100;
  var bsp_fit_canvas = null;
  function bsp_should_fit(report) {
    if (!report || report.tree_report)
      return false;
    return !(report.report_settings && report.report_settings.bsp_fit_columns === false);
  }
  function bsp_text_width(text, font) {
    bsp_fit_canvas = bsp_fit_canvas || document.createElement("canvas");
    const ctx = bsp_fit_canvas.getContext("2d");
    ctx.font = font;
    return ctx.measureText(text).width;
  }
  function bsp_cell_text(value, col, row) {
    if (value === null || value === void 0 || value === "")
      return "";
    let text = value;
    try {
      text = frappe.format(value, col, { only_value: true }, row);
    } catch (e) {
      text = value;
    }
    return String(text).replace(/<[^>]*>/g, "").replace(/&nbsp;/g, " ").trim();
  }
  function bsp_inject_fit_styles() {
    if (document.getElementById("bsp-fit-report-style"))
      return;
    const style = document.createElement("style");
    style.id = "bsp-fit-report-style";
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
            overflow-wrap: normal;
            padding-left: 6px;
            padding-right: 6px;
        }
    `;
    document.head.appendChild(style);
  }
  function bsp_available_width(report) {
    const $candidates = [report.$report, report.$report && report.$report.parent(), $(report.page && report.page.main)];
    for (const $el of $candidates) {
      const width = $el && $el.length ? $el.width() : 0;
      if (width)
        return width;
    }
    return 0;
  }
  function bsp_fit_columns_to_window(report) {
    if (!bsp_should_fit(report))
      return;
    const columns = (report.columns || []).filter((col) => !col.hidden);
    if (!columns.length)
      return;
    const available = bsp_available_width(report);
    if (!available)
      return;
    bsp_inject_fit_styles();
    report.$report.addClass("bsp-fit-report");
    bsp_bind_fit_resize(report);
    const body_font = getComputedStyle(document.body);
    const font = `13px ${body_font.fontFamily}`;
    const header_font = `600 13px ${body_font.fontFamily}`;
    const rows = (report.data || []).slice(0, BSP_FIT_SAMPLE_ROWS);
    const needed = columns.map((col) => {
      const label_words = String(col.name || col.label || "").split(/\s+/);
      const header_need = Math.max(...label_words.map((w) => bsp_text_width(w, header_font)));
      let need = header_need + BSP_FIT_HEADER_PADDING - BSP_FIT_PADDING;
      for (const row of rows) {
        if (!row)
          continue;
        const text = bsp_cell_text(row[col.fieldname], col, row);
        if (text)
          need = Math.max(need, bsp_text_width(text, font));
      }
      const is_text = BSP_FIT_TEXT_FIELDTYPES.includes(col.fieldtype) || /(^|_)(name|description|remarks)$/.test(col.fieldname || "");
      const max = is_text ? BSP_FIT_MAX_TEXT_WIDTH : BSP_FIT_MAX_WIDTH;
      return Math.min(max, Math.max(BSP_FIT_MIN_WIDTH, Math.ceil(need + BSP_FIT_PADDING)));
    });
    const row_index_width = String((report.data || []).length).length * 9 + 30;
    const usable = available - row_index_width - 20;
    const total_needed = needed.reduce((a, b) => a + b, 0);
    const extra = Math.max(0, usable - total_needed);
    const share = extra / columns.length;
    columns.forEach((col, idx) => {
      col.width = Math.floor(needed[idx] + share);
    });
  }
  function bsp_bind_fit_resize(report) {
    if (report._bsp_fit_resize_bound)
      return;
    report._bsp_fit_resize_bound = true;
    let timer = null;
    $(window).on("resize", () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (frappe.query_report !== report || !report.datatable)
          return;
        if (!frappe.get_route || frappe.get_route()[0] !== "query-report")
          return;
        report.render_datatable();
      }, 300);
    });
  }
  var bsp_patch_interval = setInterval(() => {
    if (!frappe.views || !frappe.views.QueryReport)
      return;
    if (frappe.views.QueryReport.prototype._bsp_patched)
      return;
    clearInterval(bsp_patch_interval);
    frappe.views.QueryReport.prototype._bsp_patched = true;
    const _orig_render_datatable = frappe.views.QueryReport.prototype.render_datatable;
    frappe.views.QueryReport.prototype.render_datatable = function() {
      if (this._bsp_col_prefs && this._bsp_col_prefs.visible_columns) {
        bsp_apply_column_prefs(this, this._bsp_col_prefs.visible_columns);
      }
      bsp_fit_columns_to_window(this);
      const result = _orig_render_datatable.call(this);
      bsp_apply_default_date_sort(this);
      return result;
    };
    const _orig_setup_page_head = frappe.views.QueryReport.prototype.setup_page_head;
    frappe.views.QueryReport.prototype.setup_page_head = function() {
      _orig_setup_page_head.call(this);
      bsp_add_pick_columns_button(this);
    };
    const _orig_refresh = frappe.views.QueryReport.prototype.refresh;
    frappe.views.QueryReport.prototype.refresh = function() {
      let res = _orig_refresh.apply(this, arguments);
      this._bsp_load_and_apply_prefs();
      return res;
    };
    frappe.views.QueryReport.prototype._bsp_load_and_apply_prefs = function() {
      let report = this;
      if (!report.report_name)
        return;
      if (report._bsp_prefs_loaded_for === report.report_name)
        return;
      report._bsp_prefs_loaded_for = report.report_name;
      frappe.db.get_list("Report Column Visibility", {
        filters: { user: frappe.session.user, report_name: report.report_name },
        fields: ["name", "visible_columns"],
        order_by: "creation desc",
        limit: 1
      }).then((records) => {
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
    if (frappe.query_report && frappe.query_report.report_name) {
      frappe.query_report._bsp_load_and_apply_prefs();
      bsp_add_pick_columns_button(frappe.query_report);
    }
  }, 100);
  setInterval(() => {
    if (frappe.get_route && frappe.get_route()[0] === "query-report" && frappe.query_report) {
      bsp_add_pick_columns_button(frappe.query_report);
    }
  }, 1e3);
  (function bsp_patch_item_link_formatter() {
    const formatters = frappe.provide("frappe.form.link_formatters");
    let _item_formatter = formatters["Item"];
    Object.defineProperty(formatters, "Item", {
      configurable: true,
      enumerable: true,
      get() {
        if (!_item_formatter)
          return void 0;
        return function(value, doc, docfield) {
          if (value)
            return value;
          return _item_formatter.call(this, value, doc, docfield);
        };
      },
      set(fn) {
        _item_formatter = fn;
      }
    });
  })();

  // ../bsp_engineering/bsp_engineering/public/js/item_auto_code.js
  frappe.provide("bsp_engineering.item_code");
  bsp_engineering.item_code.fill = async function(doc, set_value) {
    if (!doc || doc.item_code || doc.variant_of)
      return;
    try {
      const { message: code } = await frappe.call({
        method: "bsp_engineering.doc_events.item.auto_item_code.get_next_item_code"
      });
      if (!code || doc.item_code)
        return;
      doc.__bsp_auto_code = code;
      await set_value(code);
    } catch (e) {
      console.error("Could not fetch next Item Code", e);
    }
  };
  var _a, _b;
  if (((_b = (_a = frappe.ui) == null ? void 0 : _a.form) == null ? void 0 : _b.QuickEntryForm) && !frappe.ui.form.ItemQuickEntryForm) {
    frappe.ui.form.ItemQuickEntryForm = class ItemQuickEntryForm extends frappe.ui.form.QuickEntryForm {
      render_dialog() {
        super.render_dialog();
        if (this.dialog.fields_dict.item_code) {
          bsp_engineering.item_code.fill(
            this.dialog.doc,
            (code) => this.dialog.set_value("item_code", code)
          );
        }
      }
    };
  }

  // ../bsp_engineering/bsp_engineering/public/js/bsp_item_search.js
  var ITEM = "Item";
  var PAGE_LENGTH = 20;
  var SCROLL_THRESHOLD = 40;
  var BANGLA_DIGITS = "\u09E6\u09E7\u09E8\u09E9\u09EA\u09EB\u09EC\u09ED\u09EE\u09EF";
  var normalize = (value) => String(value != null ? value : "").replace(/[০-৯]/g, (digit) => BANGLA_DIGITS.indexOf(digit)).toLowerCase();
  function matches_all_words(txt, values) {
    const words = normalize(txt).split(/\s+/).filter(Boolean);
    if (!words.length)
      return true;
    const haystack = values.map(normalize);
    return words.every((word) => haystack.some((value) => value.includes(word)));
  }
  var near_bottom = (el) => el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_THRESHOLD;
  var PAGED_METHODS = {
    "frappe.desk.search.search_link": (args, page) => __spreadProps(__spreadValues({}, args), {
      start: page.start,
      page_length: page.page_length
    }),
    "erpnext.controllers.queries.item_query": (args, page) => __spreadProps(__spreadValues({}, args), {
      start: page.start,
      page_len: page.page_length
    })
  };
  var pending_page = null;
  var original_call = frappe.call;
  frappe.call = function(opts, ...rest) {
    const add_page = pending_page && opts && typeof opts === "object" && PAGED_METHODS[opts.method];
    if (add_page) {
      opts = __spreadProps(__spreadValues({}, opts), { args: add_page(opts.args || {}, pending_page) });
    }
    return original_call.call(this, opts, ...rest);
  };
  function call_with_page(page, fn) {
    pending_page = page;
    try {
      return fn();
    } finally {
      pending_page = null;
    }
  }
  var link_proto = frappe.ui.form.ControlLink.prototype;
  var original_setup_awesomeplete = link_proto.setup_awesomeplete;
  link_proto.setup_awesomeplete = function() {
    original_setup_awesomeplete.call(this);
    this._bsp_exhausted = {};
    $(this.awesomplete.ul).on("scroll", () => this.bsp_load_more_items());
  };
  link_proto.bsp_load_more_items = function() {
    var _a2, _b2;
    const doctype = this.get_options();
    const ul = this.awesomplete.ul;
    if (doctype !== ITEM || this._bsp_loading || !near_bottom(ul))
      return;
    const term = this.$input.val();
    const cache = this.$input.cache[doctype];
    const list = cache && cache[term];
    if (!list || this._bsp_exhausted[term])
      return;
    const results = list.filter((d) => !d.action);
    const actions = list.filter((d) => d.action);
    const first_page = cint((_a2 = frappe.boot.sysdefaults) == null ? void 0 : _a2.link_field_results_limit) || 10;
    if (results.length < first_page)
      return;
    const args = {
      txt: term,
      doctype,
      ignore_user_permissions: (_b2 = this.df) == null ? void 0 : _b2.ignore_user_permissions,
      reference_doctype: this.get_reference_doctype() || "",
      page_length: PAGE_LENGTH,
      start: results.length
    };
    this.set_custom_query(args);
    this._bsp_loading = true;
    frappe.call({
      type: "POST",
      method: "frappe.desk.search.search_link",
      no_spinner: true,
      args
    }).then((r) => {
      const page = r.message || [];
      if (page.length < PAGE_LENGTH)
        this._bsp_exhausted[term] = true;
      const seen = new Set(results.map((d) => d.value));
      const more = page.filter((d) => !seen.has(d.value));
      if (!more.length)
        return;
      more.forEach((d) => frappe.utils.add_link_title(doctype, d.value, d.label));
      cache[term] = results.concat(more, actions);
      if (this.$input.val() !== term)
        return;
      const top = ul.scrollTop;
      this.awesomplete.maxItems = Math.max(this.awesomplete.maxItems, cache[term].length);
      this.awesomplete.list = cache[term];
      ul.scrollTop = top;
    }).always(() => {
      this._bsp_loading = false;
    });
  };
  var msl_proto = frappe.ui.form.ControlMultiSelectList.prototype;
  var original_msl_make_input = msl_proto.make_input;
  var to_options = (options) => (options || []).map((option) => {
    if (typeof option === "string")
      return { label: option, value: option };
    if (!option.label)
      option.label = option.value;
    return option;
  });
  msl_proto.make_input = function() {
    original_msl_make_input.call(this);
    this.$list_wrapper.off("input", "input");
    this.$list_wrapper.on(
      "input",
      "input",
      frappe.utils.debounce(() => {
        this._bsp_exhausted = false;
        this.set_options().then(() => this.bsp_render_options());
      }, 300)
    );
    this.$list_wrapper.on("show.bs.dropdown", () => {
      this._bsp_exhausted = false;
    });
    this.$list_wrapper.find(".selectable-items").on("scroll", (e) => this.bsp_load_more_options(e.currentTarget));
  };
  msl_proto.bsp_render_options = function() {
    const txt = this.$filter_input.val();
    const filtered = this._options.filter(
      (opt) => this.values.includes(opt.value) || matches_all_words(txt, [opt.label, opt.value, opt.description])
    );
    this.set_selectable_items(this._selected_values.concat(filtered).uniqBy((opt) => opt.value));
  };
  msl_proto.bsp_load_more_options = function(el) {
    if (this.df.options !== ITEM || !this.df.get_data)
      return;
    if (this._bsp_loading || this._bsp_exhausted || !near_bottom(el))
      return;
    const txt = this.$filter_input.val();
    this._bsp_loading = true;
    Promise.resolve(
      call_with_page(
        { start: this._options.length, page_length: PAGE_LENGTH },
        () => this.df.get_data(txt)
      )
    ).then((options) => {
      options = to_options(options);
      const seen = new Set(this._options.map((opt) => opt.value));
      const more = options.filter((opt) => !seen.has(opt.value));
      if (options.length < PAGE_LENGTH || !more.length)
        this._bsp_exhausted = true;
      if (!more.length || this.$filter_input.val() !== txt)
        return;
      this._options = this._options.concat(more);
      const top = el.scrollTop;
      this.bsp_render_options();
      el.scrollTop = top;
    }).finally(() => {
      this._bsp_loading = false;
    });
  };

  // ../bsp_engineering/bsp_engineering/public/js/report_styling.js
  frappe.provide("bsp_engineering.report_print");
  var BSP_REPORT_FONT_URL = "{{ base_url }}/assets/bsp_engineering/fonts/hind_siliguri";
  var BSP_FILTERS_PER_ROW = 4;
  var BSP_REPORT_PRINT_CSS = `
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
    if (value === null || value === void 0 || value === "")
      return "";
    if (Array.isArray(value)) {
      const is_range = df && df.fieldtype === "DateRange";
      const item_df = { fieldtype: is_range ? "Date" : "Data" };
      return value.map((v) => bsp_filter_display(v, item_df)).filter(Boolean).join(is_range ? " - " : ", ");
    }
    if (df && df.fieldtype === "Check")
      return cint(value) ? __("Yes") : "";
    if (!df)
      return bsp_plain_text(value);
    return bsp_plain_text(frappe.format(value, df, { only_value: true, inline: true }));
  }
  function bsp_filter_items(ctx) {
    const controls = (ctx.report && ctx.report.filters || []).filter((c) => c && c.df);
    if (controls.length) {
      return controls.filter((c) => !c.df.hidden && c.df.fieldname !== "company").map((c) => ({ label: __(c.df.label || c.df.fieldname), value: bsp_filter_display(c.get_value(), c.df) })).filter((item) => item.value);
    }
    return Object.entries(ctx.filters || {}).filter(([key]) => key !== "company").map(([key, value]) => ({ label: __(frappe.unscrub(key)), value: bsp_filter_display(value) })).filter((item) => item.value);
  }
  function bsp_company(ctx) {
    return ctx.filters && ctx.filters.company || frappe.defaults.get_user_default("Company") || frappe.boot.sysdefaults && frappe.boot.sysdefaults.company || "";
  }
  bsp_engineering.report_print.header = function(ctx) {
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
        const cells = items.slice(i, i + BSP_FILTERS_PER_ROW).map(
          (item) => `<td class="bsp-filter-label">${esc(item.label)}</td><td class="bsp-filter-value">${esc(item.value)}</td>`
        ).join("");
        rows += `<tr>${cells}</tr>`;
      }
      html += `<table class="bsp-report-filters">${rows}</table>`;
    }
    return html;
  };
  (function bsp_style_report_prints() {
    const templates = frappe.templates || {};
    if (templates.print_template && !templates.print_template.includes("bsp-report-print")) {
      templates.print_template = templates.print_template.replace("</head>", `<style>${BSP_REPORT_PRINT_CSS}</style></head>`).replace('class="print-format-gutter"', 'class="print-format-gutter bsp-report-print"');
    }
    const grid = templates.print_grid;
    if (grid && !grid.includes("bsp_engineering.report_print")) {
      const table_start = grid.indexOf("<table");
      let patched = grid.indexOf("<!-- title -->") !== -1 && table_start !== -1 ? "{{ bsp_engineering.report_print.header(obj) }}\n" + grid.slice(table_start) : grid;
      patched = patched.replace(
        '<tr style="height: 30px">',
        '<tr style="height: 30px" {% if (row.is_total_row) { %} class="bsp-total-row" {% } %}>'
      );
      patched = patched.replace(
        '<td {% if row.bold == 1 %} style="font-weight: bold" {% endif %} {% if longest_word',
        `<td data-bsp-fieldtype="{{ col.fieldtype || '' }}" data-bsp-field="{{ (col.fieldname || '').toLowerCase() }}" {% if row.bold == 1 %} style="font-weight: bold" {% endif %} {% if longest_word`
      );
      templates.print_grid = patched;
    }
    delete frappe.template.compiled.print_template;
    delete frappe.template.compiled.print_grid;
  })();
})();
//# sourceMappingURL=bsp_engineering.bundle.EKSBKRUL.js.map
