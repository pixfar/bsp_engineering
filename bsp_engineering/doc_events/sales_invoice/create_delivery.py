import frappe


def create_delivery_note_from_sales_invoice(doc):
	if _has_existing_delivery_note(doc.name):
		doc.db_set('custom_is_delivered', 1, update_modified=False)
		return True, 'Delivery Note already exists for this invoice.'

	try:
		items = _get_delivery_items(doc)
		if not items:
			doc.db_set('custom_is_delivered', 0, update_modified=False)
			return False, 'Unable to create Delivery Note: no pending items.'

		delivery_note = frappe.get_doc(
			{
				'doctype': 'Delivery Note',
				'customer': doc.customer,
				'company': doc.company,
				'posting_date': doc.posting_date,
				'posting_time': doc.posting_time,
				'set_warehouse': doc.set_warehouse,
				'selling_price_list': doc.selling_price_list,
				'currency': doc.currency,
				'conversion_rate': doc.conversion_rate,
				'taxes_and_charges': doc.taxes_and_charges,
				'tax_category': doc.tax_category,
				'shipping_address_name': doc.shipping_address_name,
				'customer_address': doc.customer_address,
				'contact_person': doc.contact_person,
				'items': items,
			}
		)
		delivery_note.insert(ignore_permissions=True)
		delivery_note.submit()
		doc.db_set('custom_is_delivered', 1, update_modified=False)
		return True, f'Delivery Note {delivery_note.name} created.'
	except Exception as error:
		frappe.log_error(
			frappe.get_traceback(),
			f'Delivery Note creation failed for Sales Invoice {doc.name}',
		)
		doc.db_set('custom_is_delivered', 0, update_modified=False)
		return False, f'Unable to create Delivery Note automatically: {error}'


def _get_delivery_items(doc):
	from posawesome.posawesome.api.invoice_processing.fulfillment_qty import (
		get_returned_qty_by_invoice_item,
		remaining_fulfillment_qty,
	)

	returned = get_returned_qty_by_invoice_item(
		'Sales Invoice', [doc.name]
	).get(doc.name, {})

	items = []
	for item in doc.items:
		if not item.item_code:
			continue

		qty = remaining_fulfillment_qty(
			item.qty, item.delivered_qty, returned.get(item.name, 0)
		)
		if qty <= 0:
			continue

		items.append(
			{
				'item_code': item.item_code,
				'item_name': item.item_name,
				'description': item.description,
				'uom': item.uom,
				'stock_uom': item.stock_uom,
				'conversion_factor': item.conversion_factor,
				'qty': qty,
				'rate': item.rate,
				'amount': item.rate * qty,
				'warehouse': item.warehouse or doc.set_warehouse,
				'against_sales_invoice': doc.name,
				'si_detail': item.name,
			}
		)

	return items


def _has_existing_delivery_note(sales_invoice):
	return bool(
		frappe.db.exists(
			'Delivery Note Item',
			{
				'against_sales_invoice': sales_invoice,
				'docstatus': ('!=', 2),
			},
		)
	)