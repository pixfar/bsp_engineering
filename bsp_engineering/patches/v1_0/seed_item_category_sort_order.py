import json
import os

import frappe

# Step between assigned ranks, both for groups and for items within a group --
# leaves room to manually slot something in between two existing ranks later
# (via the Sort Order field on Item Group / Item) without renumbering
# everything else.
RANK_STEP = 10

DATA_FILE = frappe.get_app_path('bsp_engineering', 'data', 'item_category_sort_order.json')


def execute():
	"""Seed Item Group.custom_sort_order and Item.custom_sort_order from BSP's
	official "Product List Category Wised" order (Md. Jabed Mia, Sep 2026),
	so every report that lists items can sort by (item group, item) in that
	exact order instead of alphabetically.

	A group/item with no rank set (0/NULL -- never in the source list) sorts
	after everything ranked here -- see bsp_engineering.utils.item_category_sort.
	That's also what happens automatically to anything added after this patch
	runs: a brand new Item Group has no rank until someone sets one, so it
	falls to the bottom of every report; a new Item under an existing, already
	-ranked group likewise falls to the bottom of that group.
	"""
	_ensure_sort_order_fields()

	if not os.path.exists(DATA_FILE):
		frappe.log_error(
			title='seed_item_category_sort_order',
			message=f'Data file not found: {DATA_FILE}',
		)
		return

	with open(DATA_FILE, encoding='utf-8') as f:
		entries = json.load(f)

	# item_code -> real, current Item Group (never the source PDF's own Item
	# Group text -- that's only used implicitly, via each item's actual
	# live item_group, so re-categorizing an item in the Item master is
	# immediately respected without needing to touch this list).
	item_groups = dict(
		frappe.get_all('Item', fields=['name', 'item_group'], limit_page_length=0, as_list=True)
	)

	group_rank = {}
	next_group_rank = RANK_STEP
	item_rank_in_group = {}
	next_item_rank = {}

	for entry in sorted(entries, key=lambda e: e['sl']):
		item_code = entry['item_code']
		item_group = item_groups.get(item_code)
		if not item_group:
			# Item code no longer exists (deleted/renamed since the sheet was
			# made) -- nothing to rank.
			continue

		if item_group not in group_rank:
			group_rank[item_group] = next_group_rank
			next_group_rank += RANK_STEP
			next_item_rank[item_group] = RANK_STEP

		item_rank_in_group[item_code] = next_item_rank[item_group]
		next_item_rank[item_group] += RANK_STEP

	for item_group, rank in group_rank.items():
		frappe.db.set_value('Item Group', item_group, 'custom_sort_order', rank, update_modified=False)

	for item_code, rank in item_rank_in_group.items():
		frappe.db.set_value('Item', item_code, 'custom_sort_order', rank, update_modified=False)

	frappe.db.commit()


def _ensure_sort_order_fields():
	_ensure_custom_field(
		dt='Item Group',
		fieldname='custom_sort_order',
		label='Sort Order',
		insert_after='is_group',
		description=(
			'Position of this group in BSP\'s official product-category order '
			'(lower sorts first). Reports that list items sort by this, then by '
			'each item\'s own Sort Order. 0/blank sorts after every ranked group.'
		),
	)
	_ensure_custom_field(
		dt='Item',
		fieldname='custom_sort_order',
		label='Sort Order',
		insert_after='item_group',
		description=(
			'Position of this item within its Item Group\'s official order '
			'(lower sorts first). 0/blank sorts after every ranked item in the '
			'same group.'
		),
	)


def _ensure_custom_field(dt, fieldname, label, insert_after, description):
	name = f'{dt}-{fieldname}'
	if frappe.db.exists('Custom Field', name):
		return

	frappe.get_doc(
		{
			'doctype': 'Custom Field',
			'dt': dt,
			'fieldname': fieldname,
			'label': label,
			'fieldtype': 'Int',
			'insert_after': insert_after,
			'description': description,
			'in_list_view': 1,
			'in_standard_filter': 1,
		}
	).insert(ignore_permissions=True)
