import frappe

from bsp_engineering.utils.warehouse_sort import OFFICIAL_WAREHOUSE_ORDER, normalize_warehouse_name

# Same spacing as the item/item-group Sort Order, so a warehouse can be
# slotted in between two existing ones later without renumbering.
RANK_STEP = 10


def execute():
	"""Add Warehouse.custom_sort_order and seed it from BSP's official
	warehouse order, so every custom report lists warehouses (as rows or as
	columns) in that order instead of alphabetically. Warehouses not in the
	list keep 0 and sort after the ranked ones."""
	_ensure_sort_order_field()

	rank_by_name = {
		normalize_warehouse_name(name): (idx + 1) * RANK_STEP
		for idx, name in enumerate(OFFICIAL_WAREHOUSE_ORDER)
	}

	for wh in frappe.get_all('Warehouse', fields=['name', 'warehouse_name'], limit_page_length=0):
		rank = rank_by_name.get(normalize_warehouse_name(wh.warehouse_name or wh.name))
		if rank:
			frappe.db.set_value('Warehouse', wh.name, 'custom_sort_order', rank, update_modified=False)

	frappe.db.commit()


def _ensure_sort_order_field():
	if frappe.db.exists('Custom Field', 'Warehouse-custom_sort_order'):
		return

	frappe.get_doc(
		{
			'doctype': 'Custom Field',
			'dt': 'Warehouse',
			'fieldname': 'custom_sort_order',
			'label': 'Sort Order',
			'fieldtype': 'Int',
			'insert_after': 'warehouse_name',
			'description': (
				'Position of this warehouse in BSP\'s official warehouse order '
				'(lower sorts first). Custom reports list warehouses in this '
				'order. 0/blank sorts after every ranked warehouse.'
			),
			'in_list_view': 1,
		}
	).insert(ignore_permissions=True)
