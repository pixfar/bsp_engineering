# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Warehouse columns on the item summary reports follow the warehouse master,
not a fixed showroom list.

    bench --site bsp.localhost run-tests --module bsp_engineering.tests.test_item_warehouse_matrix
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from bsp_engineering.utils.item_warehouse_matrix import (
	assemble_rows,
	omit_empty_warehouse_columns,
	purchase_summary,
	sales_summary,
	stock_entry_summary,
	warehouse_fieldnames,
	weight_summary,
)

COMPANY = "BSP Engineering Works"


def _warehouses(*names):
	return [frappe._dict(name=name, warehouse_name=name.split(" - ")[0]) for name in names]


def _assert_shown_warehouses_have_a_figure(case, columns, rows):
	fixed = {"item_code", "item_name", "item_group", "quantity", "value"}
	by_warehouse = {}
	for column in columns:
		if column["fieldname"] in fixed:
			continue
		by_warehouse.setdefault(column["fieldname"].removesuffix("_value"), []).append(column["fieldname"])
	for fields in by_warehouse.values():
		case.assertTrue(any(flt(row.get(field)) for row in rows for field in fields))


class TestItemWarehouseMatrix(FrappeTestCase):
	def test_qty_lands_in_the_matching_warehouse_column(self):
		warehouses = _warehouses("Dhaka Showroom - BSP", "Asif Engineering - BSP")
		fieldnames = warehouse_fieldnames(warehouses)
		rows = assemble_rows(
			[
				frappe._dict(
					item_code="ITEM-A",
					item_name="Item A",
					item_group="Products",
					warehouse="Dhaka Showroom - BSP",
					qty=4,
					amount=40,
				),
				frappe._dict(
					item_code="ITEM-A",
					item_name="Item A",
					item_group="Products",
					warehouse="Dhaka Showroom - BSP",
					qty=1,
					amount=10,
				),
				frappe._dict(
					item_code="ITEM-A",
					item_name="Item A",
					item_group="Products",
					warehouse="Asif Engineering - BSP",
					qty=2,
					amount=20,
				),
				frappe._dict(
					item_code="ITEM-B",
					item_name="Item B",
					item_group="Products",
					warehouse="Dhaka Showroom - BSP",
					qty=0,
					amount=0,
				),
			],
			warehouses,
			fieldnames,
			with_value=True,
		)

		self.assertEqual([row["item_code"] for row in rows], ["ITEM-A"])
		dhaka = fieldnames["Dhaka Showroom - BSP"]
		asif = fieldnames["Asif Engineering - BSP"]
		self.assertEqual(rows[0][dhaka], 5)
		self.assertEqual(rows[0][f"{dhaka}_value"], 50)
		self.assertEqual(rows[0][asif], 2)
		self.assertEqual(rows[0][f"{asif}_value"], 20)
		self.assertEqual(rows[0]["quantity"], 7)
		self.assertEqual(rows[0]["value"], 70)

	def test_top_selling_keeps_items_with_no_movement(self):
		warehouses = _warehouses("Dhaka Showroom - BSP")
		fieldnames = warehouse_fieldnames(warehouses)
		rows = assemble_rows(
			[],
			warehouses,
			fieldnames,
			include_items=[
				frappe._dict(item_code="ITEM-Z", item_name="Idle", item_group="Products"),
			],
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0][fieldnames["Dhaka Showroom - BSP"]], 0)
		self.assertEqual(rows[0]["quantity"], 0)

	def test_all_zero_warehouse_column_is_omitted(self):
		warehouses = _warehouses("Dhaka Showroom - BSP", "Asif Engineering - BSP")
		fieldnames = warehouse_fieldnames(warehouses)
		columns = [
			{"label": "Item Code", "fieldname": "item_code"},
			{"label": "Quantity", "fieldname": "quantity"},
			{"label": "Value", "fieldname": "value"},
			{"label": "Dhaka Showroom Qty", "fieldname": fieldnames["Dhaka Showroom - BSP"]},
			{"label": "Dhaka Showroom Value", "fieldname": f"{fieldnames['Dhaka Showroom - BSP']}_value"},
			{"label": "Asif Engineering Qty", "fieldname": fieldnames["Asif Engineering - BSP"]},
			{"label": "Asif Engineering Value", "fieldname": f"{fieldnames['Asif Engineering - BSP']}_value"},
		]
		data = [
			{
				"item_code": "ITEM-A",
				"quantity": 2,
				"value": 20,
				fieldnames["Dhaka Showroom - BSP"]: 0,
				f"{fieldnames['Dhaka Showroom - BSP']}_value": 20,
				fieldnames["Asif Engineering - BSP"]: 0,
				f"{fieldnames['Asif Engineering - BSP']}_value": 0,
			}
		]
		kept = omit_empty_warehouse_columns(columns, data, warehouses, fieldnames, with_value=True)
		labels = [column["label"] for column in kept]
		self.assertEqual(labels, ["Item Code", "Quantity", "Value", "Dhaka Showroom Qty", "Dhaka Showroom Value"])

	def test_columns_keep_only_warehouses_with_a_figure(self):
		# Default keeps every warehouse column; Hide Zero Columns trims empties.
		columns, data = sales_summary(
			{
				"company": COMPANY,
				"from_date": "2026-01-01",
				"to_date": "2026-10-22",
				"hide_zero_columns": 1,
			}
		)
		labels = [column["label"] for column in columns]
		self.assertEqual(
			labels[:5],
			["Item Code", "Item Name", "Item Group", "Grand Total Qty", "Grand Total Value"],
		)
		self.assertIn("Dhaka Showroom Qty", labels)
		self.assertEqual(labels[labels.index("Dhaka Showroom Qty") + 1], "Dhaka Showroom Value")
		self.assertNotIn("All Warehouses", labels)
		_assert_shown_warehouses_have_a_figure(self, columns, data)
		purchase_columns, purchase_rows = purchase_summary(
			{
				"company": COMPANY,
				"from_date": "2026-01-01",
				"to_date": "2026-10-22",
				"hide_zero_columns": 1,
			}
		)
		_assert_shown_warehouses_have_a_figure(self, purchase_columns, purchase_rows)
		for row in data:
			self.assertIn("item_code", row)

	def test_transfer_receipt_and_issue_reports_run(self):
		filters = {"company": COMPANY, "from_date": add_days(nowdate(), -30), "to_date": nowdate()}
		for purpose, warehouse_field in (
			("Material Transfer", "t_warehouse"),
			("Material Receipt", "t_warehouse"),
			("Material Issue", "s_warehouse"),
		):
			columns, data = stock_entry_summary(filters, purpose=purpose, warehouse_field=warehouse_field)
			self.assertEqual(columns[0]["fieldname"], "item_code")
			self.assertGreater(len(columns), 3)
			self.assertIsInstance(data, list)

	def test_weight_report_uses_as_on_date_and_runs(self):
		columns, data = weight_summary(
			{"company": COMPANY, "to_date": nowdate(), "hide_zero_columns": 1}
		)
		self.assertEqual(
			[column["fieldname"] for column in columns[:4]],
			["item_code", "item_name", "item_group", "quantity"],
		)
		for column in columns[4:]:
			self.assertTrue(any(flt(row.get(column["fieldname"])) for row in data))

	def test_top_selling_includes_items_and_totals(self):
		columns, data = sales_summary(
			{
				"company": COMPANY,
				"from_date": add_days(nowdate(), 1),
				"to_date": add_days(nowdate(), 2),
				"hide_zero_columns": 1,
			},
			include_all_items=True,
		)
		labels = [column["label"] for column in columns]
		self.assertEqual(labels[3:5], ["Grand Total Qty", "Grand Total Value"])
		# Nothing sold in this range + hide zeros → only the grand-total columns remain.
		self.assertEqual(
			labels,
			["Item Code", "Item Name", "Item Group", "Grand Total Qty", "Grand Total Value"],
		)
		self.assertGreater(len(data), 100)
		self.assertTrue(all(row["quantity"] == 0 and row["value"] == 0 for row in data))

	def test_sales_warehouse_value_matches_invoice_amount(self):
		columns, data = sales_summary(
			{"company": COMPANY, "from_date": "2026-01-01", "to_date": "2026-10-22"}
		)
		value_field = next(column["fieldname"] for column in columns if column["label"] == "Dhaka Showroom Value")
		row = next(entry for entry in data if flt(entry.get(value_field)))
		db_amount = frappe.db.sql(
			"""
			select sum(ifnull(sii.base_net_amount, 0))
			from `tabSales Invoice Item` sii
			inner join `tabSales Invoice` si on si.name = sii.parent
			where si.docstatus = 1 and si.posting_date between '2026-01-01' and '2026-10-22'
				and si.company = %(company)s
				and sii.warehouse = 'Dhaka Showroom - BSP'
				and sii.item_code = %(item_code)s
				and sii.parenttype = 'Sales Invoice'
				and sii.parentfield = 'items'
			""",
			{"company": COMPANY, "item_code": row["item_code"]},
		)[0][0]
		self.assertEqual(flt(row[value_field]), flt(db_amount))
		warehouse_value = sum(
			flt(row[column["fieldname"]])
			for column in columns
			if column["label"].endswith(" Value")
		)
		self.assertEqual(flt(row["value"]), warehouse_value)
