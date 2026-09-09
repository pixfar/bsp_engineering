import frappe

# Sentinel used for anything with no rank (0/NULL custom_sort_order, or an
# item_code the map has never heard of) -- sorts after every ranked value.
_UNRANKED = (1, '')


def get_item_sort_map():
	"""{item_code: (group_key, item_key)} for every Item, driven by
	Item Group.custom_sort_order and Item.custom_sort_order (see
	bsp_engineering.patches.v1_0.seed_item_category_sort_order, which fills
	these in from BSP's official product-category order).

	A group or item with no custom_sort_order set (0/NULL -- not in the
	official order) sorts after every ranked one: a newly added Item Group
	falls to the very bottom of a report, and a newly added Item falls to the
	bottom of its own group, until someone gives it a Sort Order. Call once
	per report run and reuse the returned map -- it's a single query.
	"""
	rows = frappe.db.sql(
		"""
		select
			item.name as item_code,
			item.custom_sort_order as item_order,
			item.item_group as item_group,
			item_group.custom_sort_order as group_order
		from `tabItem` item
		left join `tabItem Group` item_group on item_group.name = item.item_group
		""",
		as_dict=True,
	)

	sort_map = {}
	for row in rows:
		group_order = row.group_order or 0
		group_key = (0, group_order) if group_order else (1, row.item_group or '')

		item_order = row.item_order or 0
		item_key = (0, item_order) if item_order else (1, row.item_code or '')

		sort_map[row.item_code] = (group_key, item_key)
	return sort_map


def item_category_sort_key(sort_map, item_code):
	"""Sort key for one item_code -- safe for an item_code the map doesn't
	have (blank/None on the row, or deleted since the map was built): sorts
	last, same as an unranked item in an unranked group."""
	if not item_code:
		return (_UNRANKED, _UNRANKED)
	return sort_map.get(item_code, (_UNRANKED, _UNRANKED))


def sort_rows_by_item_category(rows, sort_map, item_code_key='item_code'):
	"""Stable sort of report rows (dicts or frappe._dicts) by BSP's official
	item-category order. Combine with other keys yourself (e.g. warehouse,
	invoice) when a report needs those to stay primary -- this only orders
	items relative to each other."""
	return sorted(
		rows,
		key=lambda r: item_category_sort_key(sort_map, r.get(item_code_key)),
	)
