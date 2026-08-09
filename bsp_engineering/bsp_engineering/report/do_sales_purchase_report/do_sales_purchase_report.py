# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt


NOT_RECEIVED = "Not Received"
PARTLY_RECEIVED = "Partly Received"
RECEIVED = "Received"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("DO Number"),
			"fieldname": "do_number",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Purchase ID"),
			"fieldname": "purchase_id",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Purchase Date"),
			"fieldname": "purchase_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Total Purchase Qty"),
			"fieldname": "purchase_qty",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Purchase Receipt Date"),
			"fieldname": "purchase_receipt_date",
			"fieldtype": "Date",
			"width": 150,
		},
		{
			"label": _("Purchase Receipt Qty"),
			"fieldname": "purchase_receipt_qty",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": _("Received Status"),
			"fieldname": "received_status",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Undelivered Qty"),
			"fieldname": "undelivered_qty",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Sales ID"),
			"fieldname": "sales_id",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Sales Date"),
			"fieldname": "sales_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("Total Sales Qty"),
			"fieldname": "sales_qty",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Transfer ID"),
			"fieldname": "transfer_id",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Transfer Date"),
			"fieldname": "transfer_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Total Transfer Qty"),
			"fieldname": "transfer_qty",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Remaining Qty"),
			"fieldname": "remaining_qty",
			"fieldtype": "Float",
			"width": 130,
		},
	]


def _build_conditions(filters, item_alias="item"):
	"""Shared WHERE clause: submitted, non-return rows with a non-empty
	custom_do_number, plus whichever of company/date-range/DO Number/item
	filters the user set."""
	conditions = [
		"main.docstatus = 1",
		"main.is_return = 0",
		"main.custom_do_number is not null",
		"main.custom_do_number != ''",
	]
	values = {}
	if filters.get("company"):
		conditions.append("main.company = %(company)s")
		values["company"] = filters.company
	if filters.get("from_date"):
		conditions.append("main.posting_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("main.posting_date <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("do_number"):
		conditions.append("main.custom_do_number like %(do_number)s")
		values["do_number"] = f"%{filters.do_number}%"
	if filters.get("item_code"):
		conditions.append(f"{item_alias}.item_code = %(item_code)s")
		values["item_code"] = filters.item_code
	return " AND ".join(conditions), values


def _build_transfer_conditions(filters, item_alias="item"):
	"""Same idea as _build_conditions but adapted to Material Transfer's
	actual schema: it dates itself by ``transaction_date`` (not
	``posting_date``), has no ``is_return`` concept, and has no ``company``
	column of its own -- company lives on the linked ``from_warehouse``, so
	that filter joins through ``tabWarehouse`` instead of reading a column
	directly off ``main``."""
	conditions = [
		"main.docstatus = 1",
		"main.custom_do_number is not null",
		"main.custom_do_number != ''",
	]
	values = {}
	if filters.get("company"):
		conditions.append(
			"main.from_warehouse in (select name from `tabWarehouse` where company = %(company)s)"
		)
		values["company"] = filters.company
	if filters.get("from_date"):
		conditions.append("main.transaction_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("main.transaction_date <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("do_number"):
		conditions.append("main.custom_do_number like %(do_number)s")
		values["do_number"] = f"%{filters.do_number}%"
	if filters.get("item_code"):
		conditions.append(f"{item_alias}.item_code = %(item_code)s")
		values["item_code"] = filters.item_code
	return " AND ".join(conditions), values


def _get_purchase_rows(filters):
	"""One row per Purchase Invoice Item under a DO Number, with the
	update_stock-aware "actually received" qty -- update_stock=1 invoices
	moved stock directly at submission (received_qty itself stays 0 on those
	rows, since no Purchase Receipt was ever made against them; see
	purchase_orders.get_receipt_statuses for the same rule applied
	elsewhere), so their full qty counts as received."""
	where_clause, values = _build_conditions(filters, item_alias="item")
	rows = frappe.db.sql(
		f"""
		SELECT main.custom_do_number as do_number, item.item_code as item_code,
		       item.item_name as item_name, item.name as row_name,
		       item.qty as qty, item.received_qty as received_qty,
		       main.update_stock as update_stock, main.posting_date as posting_date,
		       main.name as purchase_id
		FROM `tabPurchase Invoice Item` item
		INNER JOIN `tabPurchase Invoice` main ON main.name = item.parent
		WHERE {where_clause}
		""",
		values,
		as_dict=True,
	)
	for row in rows:
		row["effective_received_qty"] = flt(row.qty) if cint(row.update_stock) else flt(row.received_qty)
	return rows


def _get_receipt_dates(purchase_row_names):
	"""Latest Purchase Receipt posting_date per source Purchase Invoice Item
	row (Purchase Receipt Item.purchase_invoice_item is how a receipt made
	*against* an invoice -- via create_purchase_receipt -- links back)."""
	if not purchase_row_names:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT pri.purchase_invoice_item as row_name, MAX(pr.posting_date) as receipt_date
		FROM `tabPurchase Receipt Item` pri
		INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
		WHERE pr.docstatus = 1 AND pri.purchase_invoice_item in %(row_names)s
		GROUP BY pri.purchase_invoice_item
		""",
		{"row_names": tuple(purchase_row_names)},
		as_dict=True,
	)
	return {row.row_name: row.receipt_date for row in rows}


def _get_transfer_rows(filters):
	"""One row per Material Transfer Item under a DO Number -- a transfer
	moves goods out of the DO's receiving location just like a sale does, so
	it draws down the same remaining balance (see get_data's remaining_qty
	comment). Guarded by has_column since Material Transfer is posawesome's
	doctype, not this app's -- a bench without posawesome installed simply
	sees no Transfer rows rather than an error."""
	if not frappe.db.has_column("Material Transfer", "custom_do_number"):
		return []
	where_clause, values = _build_transfer_conditions(filters, item_alias="item")
	return frappe.db.sql(
		f"""
		SELECT main.custom_do_number as do_number, item.item_code as item_code,
		       item.item_name as item_name, item.qty as qty,
		       main.transaction_date as posting_date, main.name as transfer_id
		FROM `tabMaterial Transfer Item` item
		INNER JOIN `tabMaterial Transfer` main ON main.name = item.parent
		WHERE {where_clause}
		""",
		values,
		as_dict=True,
	)


def _get_sales_rows(filters):
	where_clause, values = _build_conditions(filters, item_alias="item")
	return frappe.db.sql(
		f"""
		SELECT main.custom_do_number as do_number, item.item_code as item_code,
		       item.item_name as item_name, item.qty as qty,
		       main.posting_date as posting_date, main.name as sales_id
		FROM `tabSales Invoice Item` item
		INNER JOIN `tabSales Invoice` main ON main.name = item.parent
		WHERE {where_clause}
		""",
		values,
		as_dict=True,
	)


def _receipt_status(purchase_qty, receipt_qty):
	if receipt_qty <= 0.0001:
		return NOT_RECEIVED
	if receipt_qty + 0.0001 < purchase_qty:
		return PARTLY_RECEIVED
	return RECEIVED


def get_data(filters):
	purchase_rows = _get_purchase_rows(filters)
	receipt_dates = _get_receipt_dates([row.row_name for row in purchase_rows])
	sales_rows = _get_sales_rows(filters)
	transfer_rows = _get_transfer_rows(filters)

	# Group all three sides by (DO Number, Item) -- one row per key in the
	# final report. A DO+item can span more than one document on any side
	# (e.g. a received batch sold across several customer invoices, or moved
	# in more than one Material Transfer), so purchase_id/sales_id/transfer_id
	# collect every distinct document touching that key rather than assuming
	# exactly one.
	grouped = {}

	def _bucket(do_number, item_code, item_name):
		key = (do_number, item_code)
		if key not in grouped:
			grouped[key] = {
				"do_number": do_number,
				"item_code": item_code,
				"item_name": item_name,
				"purchase_ids": set(),
				"purchase_dates": set(),
				"purchase_qty": 0.0,
				"purchase_receipt_dates": set(),
				"purchase_receipt_qty": 0.0,
				"sales_ids": set(),
				"sales_dates": set(),
				"sales_qty": 0.0,
				"transfer_ids": set(),
				"transfer_dates": set(),
				"transfer_qty": 0.0,
			}
		return grouped[key]

	for row in purchase_rows:
		bucket = _bucket(row.do_number, row.item_code, row.item_name)
		bucket["purchase_ids"].add(row.purchase_id)
		if row.posting_date:
			bucket["purchase_dates"].add(row.posting_date)
		bucket["purchase_qty"] += flt(row.qty)
		bucket["purchase_receipt_qty"] += row["effective_received_qty"]
		receipt_date = receipt_dates.get(row.row_name)
		if receipt_date:
			bucket["purchase_receipt_dates"].add(receipt_date)

	for row in sales_rows:
		bucket = _bucket(row.do_number, row.item_code, row.item_name)
		bucket["sales_ids"].add(row.sales_id)
		if row.posting_date:
			bucket["sales_dates"].add(row.posting_date)
		bucket["sales_qty"] += flt(row.qty)

	for row in transfer_rows:
		bucket = _bucket(row.do_number, row.item_code, row.item_name)
		bucket["transfer_ids"].add(row.transfer_id)
		if row.posting_date:
			bucket["transfer_dates"].add(row.posting_date)
		bucket["transfer_qty"] += flt(row.qty)

	data = []
	for bucket in grouped.values():
		purchase_qty = bucket["purchase_qty"]
		receipt_qty = bucket["purchase_receipt_qty"]
		sales_qty = bucket["sales_qty"]
		transfer_qty = bucket["transfer_qty"]
		data.append(
			{
				"do_number": bucket["do_number"],
				"item_code": bucket["item_code"],
				"item_name": bucket["item_name"],
				"purchase_id": ", ".join(sorted(bucket["purchase_ids"])),
				"purchase_date": max(bucket["purchase_dates"]) if bucket["purchase_dates"] else None,
				"purchase_qty": purchase_qty,
				"purchase_receipt_date": (
					max(bucket["purchase_receipt_dates"]) if bucket["purchase_receipt_dates"] else None
				),
				"purchase_receipt_qty": receipt_qty,
				"received_status": _receipt_status(purchase_qty, receipt_qty),
				"undelivered_qty": purchase_qty - receipt_qty,
				"sales_id": ", ".join(sorted(bucket["sales_ids"])),
				"sales_date": max(bucket["sales_dates"]) if bucket["sales_dates"] else None,
				"sales_qty": sales_qty,
				"transfer_id": ", ".join(sorted(bucket["transfer_ids"])),
				"transfer_date": max(bucket["transfer_dates"]) if bucket["transfer_dates"] else None,
				"transfer_qty": transfer_qty,
				# Per explicit request: remaining is measured against what was
				# actually *received*, not what was merely invoiced/ordered --
				# you can't sell (or transfer out) what never physically arrived,
				# even if it was invoiced. A transfer moves the batch to another
				# warehouse just like a sale moves it to a customer, so it draws
				# down the same remaining balance.
				"remaining_qty": receipt_qty - sales_qty - transfer_qty,
			}
		)

	if filters.get("received_status"):
		# Computed, not a raw column on either doctype, so it can only be
		# filtered after the fact here rather than in the SQL WHERE clauses.
		data = [row for row in data if row["received_status"] == filters.received_status]

	data.sort(key=lambda row: (row["do_number"] or "", row["item_code"] or ""))
	return data
