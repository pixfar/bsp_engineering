import frappe


def before_validate(doc, method):
	"""BSP doesn't manufacture sub-assemblies as separate stock -- a
	Production-Plan-linked Work Order's required_items must always be exactly
	the BOM's own item list, checked against stock as-is, never exploded into
	a linked sub-BOM's own raw materials.

	production_plan.py's create_work_order override already sets
	use_multi_level_bom = 0 at creation, but that value isn't no_copy, so an
	Amended Work Order (required_items is no_copy and gets rebuilt empty --
	see validate() below) would only stay flattened if nothing ever flips the
	flag back to the ERPNext default (1). Enforcing it here, before ERPNext's
	own validate() rebuilds required_items from the BOM, makes it self-healing
	instead of relying on that.
	"""
	if not doc.production_plan:
		return

	doc.use_multi_level_bom = 0


def validate(doc, method):
	"""Keep a Production-Plan-linked Work Order's raw materials pinned to the
	plan's chosen warehouse.

	ERPNext's own Work Order.validate() rebuilds `required_items` from the BOM
	whenever the table starts empty (production_plan.py's create_work_order
	override handles the normal creation path already). That empty-table
	rebuild also happens whenever such a Work Order is cancelled and
	Amended -- `required_items` is a no_copy field, so the amended draft
	starts with none, and ERPNext repopulates each row's source_warehouse
	from the BOM/Item default (e.g. "Stores - BSP") instead of the plan's
	warehouse. The header's `source_warehouse` field isn't no_copy, so it
	still shows the plan's warehouse -- leaving the header and the raw
	material rows pointing at two different warehouses, which surfaces
	later as a false "insufficient stock" error at Mark Production Complete.

	Re-pin every row here, after ERPNext's own validate() has run, so this
	self-heals on amendment (and on anything else that might reset the rows)
	rather than only at first creation.
	"""
	if not doc.production_plan:
		return

	from bsp_engineering.overrides.production_plan import get_source_warehouse_for_production_plan

	production_plan = frappe.get_cached_doc('Production Plan', doc.production_plan)
	source_warehouse = get_source_warehouse_for_production_plan(production_plan)
	if not source_warehouse:
		return

	doc.source_warehouse = source_warehouse
	for row in doc.required_items:
		row.source_warehouse = source_warehouse

	# required_items' cached available-qty columns were computed against
	# whatever (possibly wrong) warehouse set_required_items() just used --
	# recompute them now that every row points at the right one.
	doc.set_available_qty()
