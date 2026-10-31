"""Warehouse scoping for BSP reports.

A user restricted by a User Permission on Warehouse -- or on Territory
(Warehouse.custom_territory) -- sees only those warehouses' data in every
BSP report: warehouse columns, warehouse rows, and the figures/totals built
from them. That includes System Manager / BSP Admin / BSP Viewer: Warehouse
User Permissions always win over the usual all-showroom role bypass.
Everyone else with no such User Permission keeps seeing every warehouse.

Use get_report_permitted_warehouses() (None = unrestricted) at the point a
report picks its warehouses, so totals are computed from permitted data only.
"""

import frappe
from frappe import _

from bsp_engineering.utils.pos_warehouse import POS_WAREHOUSE_UNRESTRICTED_ROLES


def _expand_tree(doctype, names):
	expanded = set()
	for name in names or []:
		if not name:
			continue
		expanded.add(name)
		if frappe.db.get_value(doctype, name, "is_group"):
			expanded.update(frappe.db.get_descendants(doctype, name) or [])
	return expanded


def get_report_permitted_warehouses(user=None):
	"""None when the user may see every warehouse, else the set of warehouse
	names they may see (possibly empty). Warehouse permissions win over
	privileged roles; Territory permissions apply when the user has no
	Warehouse permission."""
	user = user or frappe.session.user
	if user == "Administrator":
		return None

	# Per-request cache (a report may ask several times).
	cache = getattr(frappe.local, "bsp_report_permitted_warehouses", None)
	if cache is None:
		cache = frappe.local.bsp_report_permitted_warehouses = {}
	if user in cache:
		return cache[user]

	warehouse_perms = frappe.get_all(
		"User Permission", filters={"user": user, "allow": "Warehouse"}, pluck="for_value"
	)
	if warehouse_perms:
		permitted = _expand_tree("Warehouse", warehouse_perms)
	else:
		# No Warehouse UP: privileged roles stay unrestricted.
		if POS_WAREHOUSE_UNRESTRICTED_ROLES.intersection(frappe.get_roles(user)):
			permitted = None
		else:
			territory_perms = frappe.get_all(
				"User Permission", filters={"user": user, "allow": "Territory"}, pluck="for_value"
			)
			if territory_perms and frappe.get_meta("Warehouse").has_field("custom_territory"):
				territories = _expand_tree("Territory", territory_perms)
				permitted = set(
					frappe.get_all(
						"Warehouse",
						filters={"custom_territory": ["in", list(territories)]},
						pluck="name",
					)
				)
			else:
				permitted = None

	cache[user] = permitted
	return permitted


def filter_permitted_warehouses(warehouses, key=None):
	"""Keep only permitted warehouses, preserving order. `warehouses` are
	names, or dicts/rows whose `key` holds the name."""
	permitted = get_report_permitted_warehouses()
	if permitted is None:
		return list(warehouses)
	if key is None:
		return [w for w in warehouses if w in permitted]
	return [w for w in warehouses if (w.get(key) if hasattr(w, "get") else None) in permitted]


def check_warehouse_filter(warehouse):
	"""Throw when a restricted user explicitly filters on a warehouse they
	may not see (filters can be typed into the URL)."""
	if not warehouse:
		return
	selected = warehouse if isinstance(warehouse, (list, tuple, set)) else [warehouse]
	permitted = get_report_permitted_warehouses()
	if permitted is None:
		return
	denied = [w for w in selected if w and w not in permitted]
	if denied:
		frappe.throw(
			_("You do not have permission to view warehouse {0}.").format(", ".join(denied)),
			frappe.PermissionError,
		)
