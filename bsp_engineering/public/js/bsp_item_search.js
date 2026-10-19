// Client half of POS Awesome-style Item search in Desk. Matching and ranking
// happen on the server (bsp_engineering/api/item_search.py); this file adds
// what Frappe's controls lack:
//
// - Infinite scroll: Item Link dropdowns (forms, child tables, filters) and
//   Item MultiSelectList report filters fetch the next page when scrolled to
//   the bottom, instead of stopping at the first 10 results.
// - MultiSelectList re-filters fetched options client-side with one plain
//   substring match, which would hide results the server matched through
//   Bangla digits or several words; it now uses the same rule as the server.

const ITEM = "Item";
const PAGE_LENGTH = 20;
// Distance (px) from the bottom of a dropdown at which the next page loads.
const SCROLL_THRESHOLD = 40;
const BANGLA_DIGITS = "০১২৩৪৫৬৭৮৯";

const normalize = (value) =>
	String(value ?? "")
		.replace(/[০-৯]/g, (digit) => BANGLA_DIGITS.indexOf(digit))
		.toLowerCase();

// POS Awesome's rule: every word of `txt` appears in at least one value.
function matches_all_words(txt, values) {
	const words = normalize(txt).split(/\s+/).filter(Boolean);
	if (!words.length) return true;
	const haystack = values.map(normalize);
	return words.every((word) => haystack.some((value) => value.includes(word)));
}

const near_bottom = (el) => el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_THRESHOLD;

// ---------------------------------------------------------------------------
// Paging for report get_data() callbacks
// ---------------------------------------------------------------------------
// Report filters fetch their options through their own get_data(txt), which
// has no paging argument. While call_with_page() runs one, the search call it
// makes (synchronously, before its first await) gets the requested page added.

const PAGED_METHODS = {
	"frappe.desk.search.search_link": (args, page) => ({
		...args,
		start: page.start,
		page_length: page.page_length,
	}),
	"erpnext.controllers.queries.item_query": (args, page) => ({
		...args,
		start: page.start,
		page_len: page.page_length,
	}),
};

let pending_page = null;
const original_call = frappe.call;
frappe.call = function (opts, ...rest) {
	const add_page = pending_page && opts && typeof opts === "object" && PAGED_METHODS[opts.method];
	if (add_page) {
		opts = { ...opts, args: add_page(opts.args || {}, pending_page) };
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

// ---------------------------------------------------------------------------
// Link fields
// ---------------------------------------------------------------------------

const link_proto = frappe.ui.form.ControlLink.prototype;
const original_setup_awesomeplete = link_proto.setup_awesomeplete;

link_proto.setup_awesomeplete = function () {
	original_setup_awesomeplete.call(this);
	this._bsp_exhausted = {};
	$(this.awesomplete.ul).on("scroll", () => this.bsp_load_more_items());
};

link_proto.bsp_load_more_items = function () {
	const doctype = this.get_options();
	const ul = this.awesomplete.ul;
	if (doctype !== ITEM || this._bsp_loading || !near_bottom(ul)) return;

	// Same key the control's own input handler caches the first page under.
	const term = this.$input.val();
	const cache = this.$input.cache[doctype];
	const list = cache && cache[term];
	if (!list || this._bsp_exhausted[term]) return;

	// The list ends with action rows (filter note, Create new, Advanced Search).
	const results = list.filter((d) => !d.action);
	const actions = list.filter((d) => d.action);
	const first_page = cint(frappe.boot.sysdefaults?.link_field_results_limit) || 10;
	if (results.length < first_page) return;

	const args = {
		txt: term,
		doctype: doctype,
		ignore_user_permissions: this.df?.ignore_user_permissions,
		reference_doctype: this.get_reference_doctype() || "",
		page_length: PAGE_LENGTH,
		start: results.length,
	};
	this.set_custom_query(args);

	this._bsp_loading = true;
	frappe
		.call({
			type: "POST",
			method: "frappe.desk.search.search_link",
			no_spinner: true,
			args: args,
		})
		.then((r) => {
			const page = r.message || [];
			if (page.length < PAGE_LENGTH) this._bsp_exhausted[term] = true;

			const seen = new Set(results.map((d) => d.value));
			const more = page.filter((d) => !seen.has(d.value));
			if (!more.length) return;
			more.forEach((d) => frappe.utils.add_link_title(doctype, d.value, d.label));

			cache[term] = results.concat(more, actions);
			if (this.$input.val() !== term) return;

			// Re-rendering jumps back to the first row; keep the user's place.
			const top = ul.scrollTop;
			this.awesomplete.maxItems = Math.max(this.awesomplete.maxItems, cache[term].length);
			this.awesomplete.list = cache[term];
			ul.scrollTop = top;
		})
		.always(() => {
			this._bsp_loading = false;
		});
};

// ---------------------------------------------------------------------------
// MultiSelectList report filters
// ---------------------------------------------------------------------------

const msl_proto = frappe.ui.form.ControlMultiSelectList.prototype;
const original_msl_make_input = msl_proto.make_input;

const to_options = (options) =>
	(options || []).map((option) => {
		if (typeof option === "string") return { label: option, value: option };
		if (!option.label) option.label = option.value;
		return option;
	});

msl_proto.make_input = function () {
	original_msl_make_input.call(this);

	// Replace Frappe's filter-as-you-type handler (see the header comment).
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
	this.$list_wrapper
		.find(".selectable-items")
		.on("scroll", (e) => this.bsp_load_more_options(e.currentTarget));
};

msl_proto.bsp_render_options = function () {
	const txt = this.$filter_input.val();
	const filtered = this._options.filter(
		(opt) =>
			this.values.includes(opt.value) ||
			matches_all_words(txt, [opt.label, opt.value, opt.description])
	);
	this.set_selectable_items(this._selected_values.concat(filtered).uniqBy((opt) => opt.value));
};

msl_proto.bsp_load_more_options = function (el) {
	if (this.df.options !== ITEM || !this.df.get_data) return;
	if (this._bsp_loading || this._bsp_exhausted || !near_bottom(el)) return;

	const txt = this.$filter_input.val();
	this._bsp_loading = true;
	Promise.resolve(
		call_with_page({ start: this._options.length, page_length: PAGE_LENGTH }, () =>
			this.df.get_data(txt)
		)
	)
		.then((options) => {
			options = to_options(options);
			const seen = new Set(this._options.map((opt) => opt.value));
			const more = options.filter((opt) => !seen.has(opt.value));
			// A get_data() that ignores paging returns its first page again.
			if (options.length < PAGE_LENGTH || !more.length) this._bsp_exhausted = true;
			if (!more.length || this.$filter_input.val() !== txt) return;

			this._options = this._options.concat(more);
			const top = el.scrollTop;
			this.bsp_render_options();
			el.scrollTop = top;
		})
		.finally(() => {
			this._bsp_loading = false;
		});
};
