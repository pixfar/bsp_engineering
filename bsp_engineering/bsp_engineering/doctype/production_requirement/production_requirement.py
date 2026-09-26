# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Production Requirement -- a per-warehouse production plan sheet: for
each item, the Shortage Qty (from the Production Requirement Report) and the
Plan Qty decided against it.

Shortage Qty is a snapshot: it is looked up server-side when an item is first
added and kept as-is on later edits, so the document records the shortage
the plan was made against even as stock moves on. Live stock is only ever
shown on screen, never stored. Status is set by hand (Pending, In Progress,
Completed, On Hold, Cancelled) to track where the requirement stands.

Access is scoped by warehouse the same way Requisition/Material Transfer are
(see posawesome's warehouse_doc_permissions): System Manager, BSP Admin and
BSP Viewer see every warehouse; everyone else only their permitted one(s).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from bsp_engineering.bsp_engineering.utils.production_requirement import get_current_shortage
from posawesome.posawesome.utils.warehouse_doc_permissions import (
	get_expanded_permitted_warehouses,
)


class ProductionRequirement(Document):
	def validate(self):
		if not self.production_by:
			self.production_by = frappe.session.user
		if not self.company:
			self.company = frappe.db.get_value('Warehouse', self.warehouse, 'company') or frappe.defaults.get_default(
				'company'
			)
		self.validate_warehouse_access()
		self.validate_items()
		self.set_shortage_qty()
		self.calculate_totals()

	def validate_warehouse_access(self):
		permitted = get_expanded_permitted_warehouses()
		if permitted is not None and self.warehouse not in permitted:
			frappe.throw(
				_('You do not have permission to use warehouse {0}.').format(frappe.bold(self.warehouse)),
				frappe.PermissionError,
			)

	def validate_items(self):
		if not self.items:
			frappe.throw(_('Add at least one item.'), title=_('Items Required'))

		seen = {}
		for row in self.items:
			if flt(row.plan_qty) <= 0:
				frappe.throw(_('Row #{0}: Plan Qty for {1} must be greater than zero.').format(row.idx, row.item_code))
			if row.item_code in seen:
				frappe.throw(
					_('Row #{0}: Item {1} is already added in row #{2}.').format(
						row.idx, row.item_code, seen[row.item_code]
					)
				)
			seen[row.item_code] = row.idx

	def set_shortage_qty(self):
		"""Items already on the saved document keep their recorded shortage;
		only newly added items get today's figure. Rows are matched by
		item_code (unique per document) since the POS screen rebuilds the
		child table on every save."""
		before = None if self.is_new() else self.get_doc_before_save()
		previous = {row.item_code: flt(row.shortage_qty) for row in (before.items if before else [])}
		new_codes = [row.item_code for row in self.items if row.item_code not in previous]
		current = get_current_shortage(new_codes) if new_codes else {}
		for row in self.items:
			row.shortage_qty = previous[row.item_code] if row.item_code in previous else current.get(row.item_code, 0.0)

	def calculate_totals(self):
		self.total_plan_qty = sum(flt(row.plan_qty) for row in self.items)
		self.total_shortage_qty = sum(flt(row.shortage_qty) for row in self.items)


def get_permission_query_conditions(user=None, doctype=None):
	permitted = get_expanded_permitted_warehouses(user)
	if permitted is None:
		return ''
	if not permitted:
		return '1=0'
	values = ', '.join(frappe.db.escape(name) for name in permitted)
	return f'`tabProduction Requirement`.`warehouse` in ({values})'


def has_permission(doc, ptype='read', user=None, debug=False):
	permitted = get_expanded_permitted_warehouses(user)
	if permitted is None or not doc.get('warehouse'):
		return True
	return doc.warehouse in permitted
