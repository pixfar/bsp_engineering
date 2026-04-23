import frappe
from frappe import _


def send_stock_notification_on_submit(doc, method=None):
	item_wh_rows = _get_item_warehouse_rows(doc)
	if not item_wh_rows:
		return

	stock_map = _get_current_stock(item_wh_rows)
	subject, body = _build_stock_message(doc.name, item_wh_rows, stock_map)

	frappe.get_doc(
		{
			'doctype': 'Notification Log',
			'for_user': frappe.session.user,
			'type': 'Alert',
			'document_type': 'Delivery Note',
			'document_name': doc.name,
			'subject': subject,
			'from_user': 'Administrator',
			'email_content': body,
		}
	).insert(ignore_permissions=True)


def _get_item_warehouse_rows(doc):
	rows = []
	for row in doc.items:
		if not row.item_code:
			continue

		warehouse = row.warehouse or doc.set_warehouse
		rows.append(
			{
				'item_code': row.item_code,
				'warehouse': warehouse,
			}
		)

	return rows


def _get_current_stock(item_wh_rows):
	keys = {
		(item['item_code'], item.get('warehouse'))
		for item in item_wh_rows
		if item.get('warehouse')
	}
	if not keys:
		return {}

	item_codes = list({key[0] for key in keys})
	warehouses = list({key[1] for key in keys})

	stock_rows = frappe.db.sql(
		"""
		SELECT
			item_code,
			warehouse,
			actual_qty AS qty
		FROM `tabBin`
		WHERE item_code IN %(item_codes)s
			AND warehouse IN %(warehouses)s
		""",
		{
			'item_codes': tuple(item_codes),
			'warehouses': tuple(warehouses),
		},
		as_dict=True,
	)
	return {
		(row.item_code, row.warehouse): row.qty or 0
		for row in stock_rows
	}


def _build_stock_message(delivery_note, item_wh_rows, stock_map):
	lines = [
		_('Current stock after Delivery Note {0}:').format(
			frappe.bold(delivery_note)
		)
	]
	seen = set()
	for row in item_wh_rows:
		item_code = row['item_code']
		warehouse = row.get('warehouse')
		key = (item_code, warehouse)

		if key in seen:
			continue
		seen.add(key)

		if warehouse:
			qty = stock_map.get(key, 0)
			lines.append(f'- {item_code} | {warehouse}: {qty}')
		else:
			lines.append(f'- {item_code}: warehouse not set')

	subject = _('Stock update for Delivery Note {0}').format(delivery_note)
	body = '<br>'.join(lines)
	return subject, body
