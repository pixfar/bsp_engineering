# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from posawesome.posawesome.utils.warehouse_doc_permissions import (
	ensure_warehouse_doc_read_access,
	get_expanded_permitted_warehouses,
	is_system_manager,
)

STATUS_IN_TRANSIT = 'In Transit'
STATUS_PARTIAL = 'Partially Received'
STATUS_FULL = 'Fully Received'


class MaterialTransfer(Document):
	def before_insert(self):
		self.requested_by = frappe.session.user

	def validate(self):
		if self.from_warehouse and self.to_warehouse:
			if self.from_warehouse == self.to_warehouse:
				frappe.throw(
					_('From Warehouse and To Warehouse cannot be the same.'),
					title=_('Invalid Warehouses'),
				)

	def on_submit(self):
		self._create_stock_entry()
		self._dispatch_stock_entry()

	def before_cancel(self):
		if not self.stock_entry:
			return
		se = frappe.db.get_value('Stock Entry', self.stock_entry, ['docstatus', 'name'], as_dict=True)
		if se and se.docstatus != 2:
			frappe.throw(
				_('Cancel the linked Stock Entry {0} before cancelling this Material Transfer.').format(
					frappe.bold(self.stock_entry)
				),
				title=_('Active Stock Entry Exists'),
			)

	def _create_stock_entry(self):
		if not self.from_warehouse:
			frappe.throw(_('From Warehouse is required.'))
		if not self.to_warehouse:
			frappe.throw(_('To Warehouse is required.'))

		company = frappe.db.get_value('Warehouse', self.from_warehouse, 'company')
		if not company:
			frappe.throw(_('Could not determine Company from From Warehouse.'))

		se = frappe.new_doc('Stock Entry')
		se.stock_entry_type = 'Material Transfer'
		se.purpose = 'Material Transfer'
		se.company = company
		se.from_warehouse = self.from_warehouse
		se.to_warehouse = self.to_warehouse
		se.custom_material_transfer = self.name

		for row in self.items:
			item_details = frappe.db.get_value(
				'Item',
				row.item_code,
				['item_name', 'stock_uom', 'description'],
				as_dict=True,
			)
			if not item_details:
				frappe.throw(_('Item {0} not found.').format(row.item_code))

			se.append('items', {
				'item_code': row.item_code,
				'item_name': row.item_name or item_details.item_name,
				'description': item_details.description,
				'qty': flt(row.qty),
				'transfer_qty': flt(row.qty),
				'uom': row.uom or item_details.stock_uom,
				'stock_uom': item_details.stock_uom,
				'conversion_factor': 1,
				's_warehouse': self.from_warehouse,
				't_warehouse': self.to_warehouse,
				'custom_material_transfer_item': row.name,
			})

		se.set_stock_entry_type()
		se.insert(ignore_permissions=True)
		self.db_set('stock_entry', se.name, update_modified=False)

	def _dispatch_stock_entry(self):
		if not self.stock_entry:
			return

		se = frappe.get_doc('Stock Entry', self.stock_entry)
		if se.docstatus != 0:
			return

		se.flags.ignore_permissions = True
		se.flags.ignore_workflow = True
		se.submit()
		frappe.db.set_value(
			'Stock Entry',
			se.name,
			'workflow_state',
			STATUS_IN_TRANSIT,
			update_modified=False,
		)
		self.db_set('transfer_status', STATUS_IN_TRANSIT, update_modified=False)


def _calculate_receipt_status(doc):
	if not doc.items:
		return STATUS_FULL

	any_received = False
	fully_received = True
	for row in doc.items:
		received = flt(row.received_qty)
		requested = flt(row.qty)
		if received > 0:
			any_received = True
		if received < requested:
			fully_received = False

	if not any_received:
		return STATUS_IN_TRANSIT
	return STATUS_FULL if fully_received else STATUS_PARTIAL


def _check_target_warehouse_permission(doc):
	if is_system_manager():
		return

	if frappe.session.user == doc.requested_by:
		frappe.throw(
			_('You cannot receive your own Material Transfer request.'),
			title=_('Not Allowed'),
		)

	warehouses = get_expanded_permitted_warehouses() or []
	if doc.to_warehouse and doc.to_warehouse in warehouses:
		return

	frappe.throw(
		_('You need a User Permission on the Target Warehouse ({0}) to perform this action.').format(
			doc.to_warehouse or _('not set')
		),
		title=_('No Warehouse Permission'),
		exc=frappe.PermissionError,
	)


@frappe.whitelist()
def can_action(transfer):
	"""Return whether the current user may confirm receipt for this transfer."""
	doc = frappe.get_doc('Material Transfer', transfer)
	ensure_warehouse_doc_read_access(doc, 'from_warehouse', 'to_warehouse')

	if doc.requested_by == frappe.session.user:
		return {'can_action': False, 'reason': 'requester'}

	if is_system_manager():
		return {'can_action': True}

	warehouses = get_expanded_permitted_warehouses() or []
	if doc.to_warehouse and doc.to_warehouse in warehouses:
		return {'can_action': True}

	return {'can_action': False, 'reason': 'no_permission'}


@frappe.whitelist()
def get_stock_entry_items(transfer):
	"""Return In-Transit SE items so the client can render the receipt dialog."""
	doc = frappe.get_doc('Material Transfer', transfer)
	ensure_warehouse_doc_read_access(doc, 'from_warehouse', 'to_warehouse')

	if not doc.stock_entry:
		frappe.throw(_('No Stock Entry found for this Material Transfer.'), title=_('Nothing to Receive'))

	se = frappe.get_doc('Stock Entry', doc.stock_entry)
	if se.docstatus == 2:
		frappe.throw(_('Stock Entry has been cancelled.'), title=_('Cannot Receive'))
	if se.docstatus == 0:
		frappe.throw(
			_('Goods have not been dispatched yet.'),
			title=_('Not In Transit'),
		)

	items = [
		{
			'name': item.name,
			'item_code': item.item_code,
			'item_name': item.item_name,
			'qty': item.qty,
			'uom': item.uom,
			'stock_uom': item.stock_uom,
			'conversion_factor': flt(item.conversion_factor) or 1,
		}
		for item in se.items
	]
	return {'se_name': se.name, 'items': items}


@frappe.whitelist()
def confirm_receipt(transfer, received_quantities=None):
	"""Confirm receipt with actual quantities.
	Only target-warehouse permission holders (not the requester) may do this."""
	doc = frappe.get_doc('Material Transfer', transfer)
	ensure_warehouse_doc_read_access(doc, 'from_warehouse', 'to_warehouse')

	if doc.docstatus != 1:
		frappe.throw(_('Material Transfer must be submitted.'))
	if doc.transfer_status != STATUS_IN_TRANSIT:
		frappe.throw(
			_('Receipt can only be confirmed while goods are in transit — current status: {0}.').format(
				doc.transfer_status
			)
		)
	if not doc.stock_entry:
		frappe.throw(_('No Stock Entry linked to this Material Transfer.'))

	_check_target_warehouse_permission(doc)

	se = frappe.get_doc('Stock Entry', doc.stock_entry)
	if se.docstatus not in (0, 1):
		frappe.throw(_('Goods are not in transit yet.'))

	if received_quantities:
		if isinstance(received_quantities, str):
			received_quantities = json.loads(received_quantities)

		for item in se.items:
			if item.name not in received_quantities:
				continue
			new_qty = flt(received_quantities[item.name])
			if new_qty < 0:
				frappe.throw(_('Received quantity cannot be negative for item {0}.').format(item.item_code))
			if new_qty > flt(item.qty):
				frappe.throw(
					_('Received qty ({0}) cannot exceed sent qty ({1}) for item {2}.').format(
						new_qty, item.qty, item.item_code
					)
				)
			item.qty = new_qty
			item.transfer_qty = new_qty * (flt(item.conversion_factor) or 1)

		se.items = [i for i in se.items if flt(i.qty) > 0]
		if not se.items:
			frappe.throw(
				_('All received quantities are zero. Enter at least one positive quantity.'),
				title=_('Nothing to Receive'),
			)
		se.flags.ignore_permissions = True
		se.save()

	se.reload()
	se.flags.ignore_permissions = True
	se.flags.ignore_workflow = True
	if se.docstatus == 0:
		se.submit()
	frappe.db.set_value(
		'Stock Entry',
		se.name,
		'workflow_state',
		'Requisition Received',
		update_modified=False,
	)

	mt_item_by_name = {row.name: row for row in doc.items}
	for se_item in se.items:
		mt_item_name = getattr(se_item, 'custom_material_transfer_item', None)
		if mt_item_name and mt_item_name in mt_item_by_name:
			frappe.db.set_value(
				'Material Transfer Item',
				mt_item_name,
				'received_qty',
				flt(se_item.qty),
				update_modified=False,
			)

	doc.reload()
	status = _calculate_receipt_status(doc)
	doc.db_set('transfer_status', status, update_modified=False)
	return status
