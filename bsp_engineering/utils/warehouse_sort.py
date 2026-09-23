import re

import frappe

# BSP's official warehouse order (Md. Jabed Mia, Sep 2026). Seeded into
# Warehouse.custom_sort_order by
# bsp_engineering.patches.v1_0.seed_warehouse_sort_order -- change the order
# afterwards from the Warehouse form's "Sort Order" field, not here.
OFFICIAL_WAREHOUSE_ORDER = [
	'Dhaka Showroom',
	'Daudkandi Showroom',
	'Chandpur Showroom',
	'Homna Showroom',
	'Shariatpur Showroom',
	'Joypara Showroom',
	'Bhairab Showroom',
	'Narsingdi Showroom',
	'N Poly Sanitary Showroom',
	'Konapara Service Center',
	'Noakhali Karkhana',
	'N Poly and RFL',
	'Store Room',
	'Oilseal Karkhana',
	'Servicing',
]

# Anything with no rank (0/NULL custom_sort_order, or a warehouse the map
# has never heard of) sorts after every ranked warehouse, alphabetically.
_UNRANKED = 1


def normalize_warehouse_name(name):
	"""'N. Poly  and RFL - BSP' -> 'n poly and rfl': drops the company
	abbreviation suffix, dots and repeated spaces so names typed slightly
	differently (warehouse vs. cash account names) still match."""
	name = re.sub(r'\s+-\s+[^-]+$', '', name or '')
	name = name.replace('.', ' ')
	return re.sub(r'\s+', ' ', name).strip().lower()


def get_warehouse_sort_map():
	"""{warehouse name: sort key} for every Warehouse, from
	Warehouse.custom_sort_order. Call once per report run and reuse it."""
	rows = frappe.get_all(
		'Warehouse',
		fields=['name', 'warehouse_name', 'custom_sort_order'],
		limit_page_length=0,
	)
	return {
		row.name: (0, row.custom_sort_order, '')
		if row.custom_sort_order
		else (_UNRANKED, 0, (row.warehouse_name or row.name).lower())
		for row in rows
	}


def warehouse_sort_key(sort_map, warehouse):
	"""Sort key for one warehouse name; safe for blank/unknown values
	(they sort last)."""
	if not warehouse:
		return (_UNRANKED + 1, 0, '')
	return sort_map.get(warehouse) or (_UNRANKED, 0, str(warehouse).lower())


def sort_warehouses(warehouses, sort_map=None, key=None):
	"""Return `warehouses` (names, or dicts/objects with a warehouse name
	under `key`) sorted in BSP's official warehouse order."""
	sort_map = sort_map or get_warehouse_sort_map()
	if key is None:
		return sorted(warehouses, key=lambda wh: warehouse_sort_key(sort_map, wh))
	return sorted(warehouses, key=lambda row: warehouse_sort_key(sort_map, row.get(key)))
