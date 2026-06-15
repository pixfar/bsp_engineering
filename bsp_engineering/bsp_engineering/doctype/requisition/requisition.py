# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from bsp_engineering.bsp_engineering.doctype.requisition.transfer_status import (
	STATUS_NOT,
	calculate_transfer_status,
	get_transferred_by_item,
	update_requisition_transfer_status,
)


class Requisition(Document):
	def before_insert(self):
		self.requested_by = frappe.session.user

	def on_submit(self):
		self.db_set('transfer_status', STATUS_NOT, update_modified=False)

	def validate(self):
		if self.docstatus == 1:
			self.transfer_status = calculate_transfer_status(self)

	def before_cancel(self):
		active_ses = frappe.get_all(
			'Stock Entry',
			filters={'custom_requisition': self.name, 'docstatus': ['!=', 2]},
			fields=['name', 'docstatus'],
		)
		if not active_ses:
			return
		names_html = ', '.join(frappe.bold(se.name) for se in active_ses)
		frappe.throw(
			_('The following Stock Entries must be cancelled or deleted before cancelling'
			  ' this Requisition: {0}').format(names_html),
			title=_('Active Stock Entries Exist'),
		)


@frappe.whitelist()
def can_create_stock_entry(requisition):
	"""Return whether the current user may create a Stock Entry for this requisition."""
	doc = frappe.get_doc('Requisition', requisition)
	doc.check_permission('read')

	if doc.requested_by == frappe.session.user:
		return {'can_create': False, 'reason': 'requester'}

	if 'System Manager' in frappe.get_roles():
		return {'can_create': True}

	if doc.source_warehouse and frappe.db.exists('User Permission', {
		'user': frappe.session.user,
		'allow': 'Warehouse',
		'for_value': doc.source_warehouse,
	}):
		return {'can_create': True}

	return {'can_create': False, 'reason': 'no_permission'}


@frappe.whitelist()
def make_stock_entry(requisition):
	doc = frappe.get_doc('Requisition', requisition)
	doc.check_permission('read')

	# The person who submitted the requisition cannot fulfil their own request
	if doc.requested_by == frappe.session.user:
		frappe.throw(
			_('You cannot create a Stock Entry for your own Requisition.'),
			title=_('Not Allowed'),
		)

	# Only System Manager or a user with permission on the Source Warehouse may create
	if 'System Manager' not in frappe.get_roles():
		if not doc.source_warehouse or not frappe.db.exists('User Permission', {
			'user': frappe.session.user,
			'allow': 'Warehouse',
			'for_value': doc.source_warehouse,
		}):
			frappe.throw(
				_('You need permission on the Source Warehouse ({0}) to create a Stock Entry.').format(
					doc.source_warehouse or _('not set')
				),
				title=_('No Warehouse Permission'),
			)

	if doc.docstatus != 1:
		frappe.throw(
			_('Submit the Requisition before creating a Stock Entry.'),
			title=_('Not Submitted'),
		)
	if not doc.source_warehouse:
		frappe.throw(_('Source Warehouse is required to transfer stock.'))
	if not doc.target_warehouse:
		frappe.throw(_('Target Warehouse is required to transfer stock.'))
	if doc.source_warehouse == doc.target_warehouse:
		frappe.throw(
			_('Source and Target Warehouse cannot be the same for a transfer.')
		)

	company = frappe.db.get_value('Warehouse', doc.source_warehouse, 'company')
	if not company:
		frappe.throw(_('Could not determine Company from Source Warehouse.'))

	transferred_by_item = get_transferred_by_item(doc.name)
	stock_entry = frappe.new_doc('Stock Entry')
	stock_entry.stock_entry_type = 'Material Transfer'
	stock_entry.purpose = 'Material Transfer'
	stock_entry.company = company
	stock_entry.from_warehouse = doc.source_warehouse
	stock_entry.to_warehouse = doc.target_warehouse
	stock_entry.custom_requisition = doc.name

	for row in doc.items:
		remaining = flt(row.required_qty) - flt(
			transferred_by_item.get(row.name)
		)
		if remaining <= 0:
			continue

		item_details = frappe.db.get_value(
			'Item',
			row.item_code,
			['item_name', 'stock_uom', 'description'],
			as_dict=True,
		)
		conversion_factor = 1
		stock_entry.append(
			'items',
			{
				'item_code': row.item_code,
				'item_name': row.item_name or item_details.item_name,
				'description': item_details.description,
				'qty': remaining,
				'transfer_qty': remaining * conversion_factor,
				'uom': row.uom or item_details.stock_uom,
				'stock_uom': item_details.stock_uom,
				'conversion_factor': conversion_factor,
				's_warehouse': doc.source_warehouse,
				't_warehouse': doc.target_warehouse,
				'custom_requisition_item': row.name,
			},
		)

	if not stock_entry.items:
		frappe.throw(
			_('All items on this Requisition are already fully transferred.'),
			title=_('Nothing to Transfer'),
		)

	stock_entry.set_stock_entry_type()
	return stock_entry.as_dict()


def _get_in_transit_se_name(requisition):
	return frappe.db.get_value('Stock Entry', {
		'custom_requisition': requisition,
		'workflow_state': 'In Transit',
		'docstatus': ['!=', 2],
	}, 'name')


@frappe.whitelist()
def get_in_transit_se_items(requisition):
	"""Return the In Transit SE name and its items so the client can render the receipt dialog."""
	doc = frappe.get_doc('Requisition', requisition)
	doc.check_permission('read')

	se_name = _get_in_transit_se_name(requisition)
	if not se_name:
		frappe.throw(_('No In Transit Stock Entry found for this Requisition.'), title=_('Nothing to Confirm'))

	se = frappe.get_doc('Stock Entry', se_name)
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
	return {'se_name': se_name, 'items': items}


@frappe.whitelist()
def confirm_receipt_from_requisition(requisition, received_quantities=None):
	"""Apply 'Confirm Receipt' on the In Transit SE. Only the original requester may call this.
	received_quantities: JSON string mapping SE item name → received qty (allows partial receipt)."""
	doc = frappe.get_doc('Requisition', requisition)
	doc.check_permission('read')

	if frappe.session.user != doc.requested_by:
		frappe.throw(
			_('Only {0} (the person who submitted this Requisition) can confirm receipt.').format(
				frappe.bold(doc.requested_by)
			),
			title=_('Not Allowed'),
			exc=frappe.PermissionError,
		)

	se_name = _get_in_transit_se_name(requisition)
	if not se_name:
		frappe.throw(_('No In Transit Stock Entry found for this Requisition.'), title=_('Nothing to Confirm'))

	se = frappe.get_doc('Stock Entry', se_name)

	if received_quantities:
		import json
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
					_('Received quantity ({0}) cannot exceed sent quantity ({1}) for item {2}.').format(
						new_qty, item.qty, item.item_code
					)
				)
			item.qty = new_qty
			item.transfer_qty = new_qty * (flt(item.conversion_factor) or 1)

		# Drop items where receiver confirmed 0
		se.items = [item for item in se.items if flt(item.qty) > 0]

		if not se.items:
			frappe.throw(
				_('All received quantities are zero. Enter at least one positive quantity.'),
				title=_('Nothing to Confirm'),
			)

		se.flags.ignore_permissions = True
		se.save()

	# Submit the SE, bypassing the workflow role check (requester is already validated above).
	# Mirrors the pattern used in the Production Plan auto-workflow.
	se.reload()
	se.flags.ignore_permissions = True
	se.flags.ignore_workflow = True
	se.submit()
	frappe.db.set_value(
		'Stock Entry', se.name, 'workflow_state', 'Requisition Received', update_modified=False
	)

	update_requisition_transfer_status(requisition)
	return frappe.db.get_value('Requisition', requisition, 'transfer_status')


@frappe.whitelist()
def refresh_transfer_status(requisition):
	doc = frappe.get_doc('Requisition', requisition)
	doc.check_permission('read')
	update_requisition_transfer_status(requisition)
	return frappe.db.get_value('Requisition', requisition, 'transfer_status')
