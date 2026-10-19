"""POS Awesome's item search, applied to every Item search in Desk.

Frappe's default link search (and ERPNext's item_query) match the raw text
with one LIKE and sort by modified/idx, so "02" lists 00985029 before
00000002, Bangla digits never match ASCII ones ("৬" vs "6") and a two-word
query only matches when both words sit next to each other. POS Awesome's item
selector (frontend useItemSearch.ts + itemSearchSort.ts) does better, and this
module reproduces it in SQL:

- Bangla digits are folded to ASCII on both sides, so "৬/১৪" and "6/14" are
  the same query and match either spelling in the data.
- The query is split on whitespace; every word must appear (substring,
  case-insensitive) in the item code, name, brand, description or a barcode.
- Results are ranked like the POS: exact code, code ends with the query, code
  starts with it, code contains it (earlier is better), name contains it,
  barcode matches -- then by the numeric part of the code.

It is wired in through override_whitelisted_methods (hooks.py):

- search_link replaces frappe.desk.search.search_link, the endpoint behind
  every Link field, child-table cell, list/report filter and
  frappe.db.get_link_options(). Item searches that use Frappe's default
  search or ERPNext's item_query go through search_items(); everything else
  is passed to Frappe's own search_widget unchanged. It also accepts `start`
  (Frappe's search_link has no offset) so the Desk dropdowns can page in more
  results as the user scrolls (public/js/bsp_item_search.js).
- item_query replaces erpnext.controllers.queries.item_query for reports
  that call it directly (Stock Balance, Stock Ledger, ...).
- reportview_get / reportview_get_count rank and match the Item list view's
  "ID" / "Item Name" filter boxes the same way.

search_widget never applies override_whitelisted_methods to the `query` it
is handed, which is why the override sits on search_link rather than on
item_query alone.
"""

import json

import frappe
from frappe import scrub
from frappe.desk import reportview
from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.desk.search import build_for_autosuggest, search_widget
from frappe.utils import cint, cstr, nowdate

BANGLA_DIGITS = '০১২৩৪৫৬৭৮৯'
ASCII_DIGITS = '0123456789'
_TO_ASCII_DIGITS = str.maketrans(BANGLA_DIGITS, ASCII_DIGITS)

ERPNEXT_ITEM_QUERY = 'erpnext.controllers.queries.item_query'

# Fields the Item list view's filter boxes search; a LIKE filter on any of
# them is treated as a POS-style search instead.
LIST_SEARCH_FIELDS = ('name', 'item_code', 'item_name')


def normalize_digits(text):
	return cstr(text).translate(_TO_ASCII_DIGITS)


def _sql_normalize_digits(expr):
	for bangla, ascii_digit in zip(BANGLA_DIGITS, ASCII_DIGITS):
		expr = f"replace({expr}, '{bangla}', '{ascii_digit}')"
	return expr


def _escape_like(text):
	return text.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _split_words(txt):
	words = []
	for word in normalize_digits(txt).split():
		if word.lower() not in (w.lower() for w in words):
			words.append(word)
	return words


# Every word must be found in this text (fields joined by a space, which a
# word can never contain) or in one of the item's barcodes.
_SEARCH_BLOB = _sql_normalize_digits(
	'concat_ws(" ", tabItem.name, tabItem.item_name, tabItem.brand, tabItem.description)'
)
_NAME = _sql_normalize_digits('ifnull(tabItem.item_name, "")')
_BARCODE_LIKE = (
	'exists (select 1 from `tabItem Barcode` ib'
	' where ib.parent = tabItem.name and ib.barcode like {param})'
)


def _match_conditions(txt, values):
	"""SQL condition (AND of one clause per word) plus the rank expression."""
	words = _split_words(txt)
	conditions = []
	for i, word in enumerate(words):
		key = f'w{i}'
		values[key] = f'%{_escape_like(word)}%'
		conditions.append(
			f'({_SEARCH_BLOB} like %({key})s or {_BARCODE_LIKE.format(param=f"%({key})s")})'
		)

	term = ' '.join(words)
	if not term:
		return conditions, None

	values.update(
		term=term,
		term_ends=f'%{_escape_like(term)}',
		term_starts=f'{_escape_like(term)}%',
		term_contains=f'%{_escape_like(term)}%',
	)
	rank = f"""case
		when tabItem.name = %(term)s then 0
		when tabItem.name like %(term_ends)s then 1
		when tabItem.name like %(term_starts)s then 2
		when locate(%(term)s, tabItem.name) > 0 then 9 + locate(%(term)s, tabItem.name)
		when locate(%(term)s, {_NAME}) > 0 then 99 + locate(%(term)s, {_NAME})
		when {_BARCODE_LIKE.format(param='%(term)s')} then 200
		when {_BARCODE_LIKE.format(param='%(term_ends)s')} then 201
		when {_BARCODE_LIKE.format(param='%(term_contains)s')} then 210
		else 1000
	end"""
	return conditions, rank


# Ties (and an empty query) sort by the digits of the code, codes without any
# digits last -- POS Awesome's sortItemsByCodeAsc.
_CODE_ORDER = (
	"cast(nullif(regexp_replace(tabItem.name, '[^0-9]', ''), '') as unsigned) is null,"
	" cast(nullif(regexp_replace(tabItem.name, '[^0-9]', ''), '') as unsigned),"
	' tabItem.name'
)


def _order_by(rank):
	return f'{rank}, {_CODE_ORDER}' if rank else _CODE_ORDER


def _apply_party_rules(filters):
	"""ERPNext item_query's customer/supplier handling (Party Specific Item)."""
	if not isinstance(filters, dict):
		return filters
	party = filters.get('customer') or filters.get('supplier')
	if party:
		rules = {}
		for rule in frappe.get_all(
			'Party Specific Item',
			filters={'party': party},
			fields=['restrict_based_on', 'based_on_value'],
		):
			field = 'name' if rule.restrict_based_on == 'Item' else rule.restrict_based_on
			rules.setdefault(field, []).append(rule.based_on_value)
		for field, allowed in rules.items():
			filters[scrub(field)] = ['in', allowed]
	filters.pop('customer', None)
	filters.pop('supplier', None)
	return filters


def _check_permission():
	if not (frappe.has_permission('Item', 'select') or frappe.has_permission('Item', 'read')):
		raise frappe.PermissionError


def _result_columns():
	"""Link search columns: the same set Frappe/ERPNext return for Item."""
	columns = ['tabItem.name']
	for field in frappe.get_meta('Item').get_search_fields():
		if field == 'name':
			continue
		if field == 'description':
			columns.append(
				'if(length(tabItem.description) > 40,'
				' concat(substr(tabItem.description, 1, 40), "..."), tabItem.description)'
				' as description'
			)
		else:
			columns.append(f'tabItem.`{field}`')
	return ', '.join(columns)


def search_items(
	txt,
	start=0,
	page_len=20,
	filters=None,
	erpnext_rules=False,
	ignore_user_permissions=False,
	as_dict=False,
):
	"""Ranked, paginated Item search returning link-search rows.

	erpnext_rules applies the fixed conditions of ERPNext's item_query (no
	templates, not past end of life, party-specific items); without it only
	disabled items are left out, as in Frappe's default link search.
	"""
	_check_permission()

	if isinstance(filters, str):
		filters = json.loads(filters) if filters else None

	conditions = ['tabItem.docstatus < 2', 'tabItem.disabled = 0']
	values = {'start': cint(start), 'page_len': cint(page_len) or 20}
	if erpnext_rules:
		filters = _apply_party_rules(filters)
		conditions += [
			'tabItem.has_variants = 0',
			"(tabItem.end_of_life > %(today)s or ifnull(tabItem.end_of_life, '0000-00-00') = '0000-00-00')",
		]
		values['today'] = nowdate()

	match_conditions, rank = _match_conditions(txt, values)
	conditions += match_conditions

	where = ' and '.join(conditions)
	# Both helpers return SQL with literal % (e.g. LIKE values) -- escape them
	# for the %(name)s parameter formatting below, as ERPNext's item_query does.
	where += get_filters_cond('Item', filters, []).replace('%', '%%')
	if not (cint(ignore_user_permissions) and frappe.has_permission('Item', 'select')):
		where += get_match_cond('Item').replace('%', '%%')

	return frappe.db.sql(
		f"""select {_result_columns()}
		from tabItem
		where {where}
		order by {_order_by(rank)}
		limit %(start)s, %(page_len)s""",
		values,
		as_dict=as_dict,
	)


def ranked_item_names(txt):
	"""Every Item name matching txt, best match first. Permissions and other
	filters are left to the caller (the list view's own query)."""
	values = {}
	conditions, rank = _match_conditions(txt, values)
	if not conditions:
		return None
	return frappe.db.sql_list(
		f"""select tabItem.name from tabItem
		where {' and '.join(conditions)}
		order by {_order_by(rank)}""",
		values,
	)


@frappe.whitelist()
def search_link(
	doctype,
	txt,
	query=None,
	filters=None,
	page_length=10,
	searchfield=None,
	reference_doctype=None,
	ignore_user_permissions=False,
	start=0,
):
	"""Drop-in for frappe.desk.search.search_link, plus a `start` offset."""
	if doctype == 'Item' and (not query or query == ERPNEXT_ITEM_QUERY):
		results = search_items(
			txt,
			start=start,
			page_len=page_length,
			filters=filters,
			erpnext_rules=bool(query),
			ignore_user_permissions=ignore_user_permissions,
		)
	else:
		results = search_widget(
			doctype,
			txt.strip(),
			query,
			searchfield=searchfield,
			start=start,
			page_length=page_length,
			filters=filters,
			reference_doctype=reference_doctype,
			ignore_user_permissions=ignore_user_permissions,
		)
	return build_for_autosuggest(results, doctype=doctype)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	"""Drop-in for erpnext.controllers.queries.item_query."""
	return search_items(
		txt,
		start=start,
		page_len=page_len,
		filters=filters,
		erpnext_rules=True,
		as_dict=as_dict,
	)


# ---------------------------------------------------------------------------
# Item list view
# ---------------------------------------------------------------------------


def _pop_list_search(filters):
	"""Remove LIKE filters on the list's search fields from `filters` (list or
	dict, as the list view sends them) and return their joined search text."""
	terms = []

	def is_search(fieldname, operator, value):
		return (
			fieldname in LIST_SEARCH_FIELDS
			and cstr(operator).lower() == 'like'
			and cstr(value).strip('% ')
		)

	if isinstance(filters, dict):
		for fieldname in list(filters):
			value = filters[fieldname]
			if isinstance(value, (list, tuple)) and len(value) == 2 and is_search(fieldname, *value):
				terms.append(cstr(value[1]).strip('% '))
				del filters[fieldname]
		return filters, ' '.join(terms)

	kept = []
	for f in filters or []:
		if isinstance(f, (list, tuple)) and len(f) in (3, 4):
			doctype = f[0] if len(f) == 4 else 'Item'
			fieldname, operator, value = f[-3:]
			if doctype == 'Item' and is_search(fieldname, operator, value):
				terms.append(cstr(value).strip('% '))
				continue
		kept.append(f)
	return kept, ' '.join(terms)


def _load_filters(raw):
	if isinstance(raw, str):
		return json.loads(raw) if raw else []
	return raw or []


def _with_name_filter(filters, names):
	if isinstance(filters, dict):
		filters['name'] = ['in', names]
	else:
		filters.append(['Item', 'name', 'in', names])
	return filters


def _item_list_search():
	"""(filters without the search boxes, ranked names) when the current
	request is an Item list query with a search box filled in, else None."""
	form = frappe.local.form_dict
	if form.get('doctype') != 'Item':
		return None
	filters, txt = _pop_list_search(_load_filters(form.get('filters')))
	if not txt:
		return None
	return filters, ranked_item_names(txt) or ['']


@frappe.whitelist()
@frappe.read_only()
def reportview_get():
	"""frappe.desk.reportview.get, ranking the Item list by search relevance."""
	search = _item_list_search()
	form = frappe.local.form_dict
	if not search or form.get('group_by'):
		return reportview.get()

	filters, names = search
	start = cint(form.get('start'))
	page_length = cint(form.get('page_length')) or 20
	page = names[start : start + page_length] or ['']

	form.filters = json.dumps(_with_name_filter(filters, page))
	form.start = 0
	result = reportview.get()

	# Reorder the page by rank (the query itself sorted by the list's column).
	keys = (result or {}).get('keys') or []
	if 'name' in keys:
		position = {name: i for i, name in enumerate(page)}
		idx = keys.index('name')
		result['values'].sort(key=lambda row: position.get(row[idx], len(page)))
	return result


@frappe.whitelist()
@frappe.read_only()
def reportview_get_count():
	"""frappe.desk.reportview.get_count, matching reportview_get's search."""
	search = _item_list_search()
	if search:
		filters, names = search
		frappe.local.form_dict.filters = json.dumps(_with_name_filter(filters, names))
	return reportview.get_count()
