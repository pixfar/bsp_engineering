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


@frappe.whitelist()
def make_stock_entry(requisition):
	doc = frappe.get_doc('Requisition', requisition)
	doc.check_permission('read')

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


@frappe.whitelist()
def refresh_transfer_status(requisition):
	doc = frappe.get_doc('Requisition', requisition)
	doc.check_permission('read')
	update_requisition_transfer_status(requisition)
	return frappe.db.get_value('Requisition', requisition, 'transfer_status')
