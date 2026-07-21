# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""One row per warehouse, summarizing the same figures the (per-transaction)
Daily Cash Summary Report shows in detail over the selected date range:
invoice count, sales/discount/due/collection totals, expense total, bank
deposit total, and the resulting net cash movement and closing balance.

Reuses the warehouse-scoped query helpers from daily_cash_summary_report.py
(Sales Invoice via `set_warehouse`, Expense Claim via `custom_warehouse`,
BSP Daily Deposit via its own `warehouse` field) so the figures always match
that report and posawesome's daily cash summary PDF -- see that module's
docstring for the full accounting model this mirrors.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company"):
		frappe.throw(_("Please select a Company."))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("Please select a date range."))

	from_date = getdate(filters.from_date)
	to_date = getdate(filters.to_date)
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date."))

	columns = get_columns()
	data = get_data(filters, from_date, to_date)
	return columns, data


def get_columns():
	return [
		{"label": _("Warehouse Name"), "fieldname": "warehouse_name", "fieldtype": "Data", "width": 220},
		{"label": _("Total Invoice"), "fieldname": "total_invoice", "fieldtype": "Int", "width": 110},
		{"label": _("Total Sales Amount"), "fieldname": "total_sales_amount", "fieldtype": "Currency", "width": 140},
		{"label": _("Total Discount"), "fieldname": "total_discount", "fieldtype": "Currency", "width": 120},
		{"label": _("Total Due"), "fieldname": "total_due", "fieldtype": "Currency", "width": 120},
		{"label": _("Total Collection"), "fieldname": "total_collection", "fieldtype": "Currency", "width": 140},
		{"label": _("Total Expense"), "fieldname": "total_expense", "fieldtype": "Currency", "width": 120},
		{"label": _("Net Cash Balance"), "fieldname": "net_cash_balance", "fieldtype": "Currency", "width": 140},
		{"label": _("Bank Deposit"), "fieldname": "bank_deposit", "fieldtype": "Currency", "width": 130},
		{
			"label": _("Closing Cash Balance"),
			"fieldname": "closing_cash_balance",
			"fieldtype": "Currency",
			"width": 150,
		},
	]


def _get_report_functions():
	# Lazy import: avoids a hard import-time dependency between report
	# modules, matching the same pattern posawesome's daily_cash_summary_pdf
	# already uses to reuse these same functions.
	from bsp_engineering.bsp_engineering.report.daily_cash_summary_report.daily_cash_summary_report import (
		get_deposits,
		get_expense_claims,
		get_opening_balances,
		get_sales_invoices,
	)

	return get_sales_invoices, get_expense_claims, get_deposits, get_opening_balances


def _empty_bucket():
	return {
		"total_invoice": 0,
		"total_sales_amount": 0.0,
		"total_discount": 0.0,
		"total_due": 0.0,
		"total_collection": 0.0,
		"total_expense": 0.0,
		"bank_deposit": 0.0,
	}


def get_data(filters, from_date, to_date):
	company = filters.company
	warehouse = filters.get("warehouse")
	get_sales_invoices, get_expense_claims, get_deposits, get_opening_balances = _get_report_functions()

	sales_invoices = get_sales_invoices(company, warehouse, from_date, to_date)
	expense_claims = get_expense_claims(company, warehouse, from_date, to_date)
	deposits = get_deposits(company, warehouse, from_date, to_date)
	opening_balances = get_opening_balances(company, warehouse, from_date)

	totals_by_wh = {}
	warehouses = set(opening_balances.keys())

	def bucket(wh):
		warehouses.add(wh)
		return totals_by_wh.setdefault(wh, _empty_bucket())

	for inv in sales_invoices:
		b = bucket(inv.warehouse)
		b["total_invoice"] += 1
		b["total_sales_amount"] += flt(inv.grand_total) + flt(inv.discount_amount)
		b["total_discount"] += flt(inv.discount_amount)
		b["total_due"] += flt(inv.outstanding_amount)
		b["total_collection"] += flt(inv.grand_total) - flt(inv.outstanding_amount)

	for row in expense_claims:
		bucket(row.warehouse)["total_expense"] += flt(row.grand_total)

	for row in deposits:
		bucket(row.warehouse)["bank_deposit"] += flt(row.amount)

	if not warehouses:
		return []

	warehouse_names = {
		w.name: w.warehouse_name
		for w in frappe.get_all(
			"Warehouse",
			filters={"name": ["in", list(warehouses)]},
			fields=["name", "warehouse_name"],
		)
	}

	data = []
	for wh in sorted(warehouses, key=lambda w: warehouse_names.get(w, w)):
		b = totals_by_wh.get(wh) or _empty_bucket()
		net_cash_balance = b["total_collection"] - b["total_expense"]
		opening = flt(opening_balances.get(wh))
		closing_cash_balance = opening + net_cash_balance - b["bank_deposit"]

		data.append(
			{
				"warehouse_name": warehouse_names.get(wh, wh),
				"total_invoice": b["total_invoice"],
				"total_sales_amount": b["total_sales_amount"],
				"total_discount": b["total_discount"],
				"total_due": b["total_due"],
				"total_collection": b["total_collection"],
				"total_expense": b["total_expense"],
				"net_cash_balance": net_cash_balance,
				"bank_deposit": b["bank_deposit"],
				"closing_cash_balance": closing_cash_balance,
			}
		)

	return data
