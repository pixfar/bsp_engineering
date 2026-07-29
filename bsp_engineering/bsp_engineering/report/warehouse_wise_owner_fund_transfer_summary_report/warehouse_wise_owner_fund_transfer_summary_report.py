# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""One row per Cash In Hand account (i.e. per showroom, once each has its
own account set up in the Chart of Accounts), summarizing the Fund
Transfers shown voucher-wise in Warehouse Wise Owner Fund Transfer Report
-- total voucher count and total amount sent, over the selected date
range. Every Cash In Hand account appears even with zero transfers, not
just the ones that received one. Reuses that report's account and query
helpers so the figures always match.

The "Warehouse Name" column is the Cash In Hand account itself -- each
showroom's account is named after it, so no separate Warehouse doctype
lookup is involved.

Send From / Description / Payment Method only make sense to show directly
when every voucher for an account agrees on that value; otherwise the cell
is left blank rather than picking one arbitrarily -- see the detail report
for the per-voucher breakdown.
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
		{"label": _("SL"), "fieldname": "sl", "fieldtype": "Int", "width": 50},
		{
			"label": _("Warehouse Name"),
			"fieldname": "cash_in_hand_account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 200,
		},
		{"label": _("Total Voucher"), "fieldname": "total_voucher", "fieldtype": "Int", "width": 110},
		{"label": _("Send From"), "fieldname": "send_from", "fieldtype": "Data", "width": 150},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 200},
		{"label": _("Payment Method"), "fieldname": "payment_method", "fieldtype": "Data", "width": 130},
		{"label": _("Send Amount"), "fieldname": "send_amount", "fieldtype": "Currency", "width": 140},
	]


def _get_report_functions():
	# Lazy import: avoids a hard import-time dependency between report
	# modules, matching the pattern warehouse_wise_daily_cash_summary_report
	# already uses to reuse daily_cash_summary_report's query functions.
	from bsp_engineering.bsp_engineering.report.warehouse_wise_owner_fund_transfer_report.warehouse_wise_owner_fund_transfer_report import (
		get_cash_in_hand_accounts,
		get_fund_transfers,
	)

	return get_cash_in_hand_accounts, get_fund_transfers


def _single_value_or_blank(values):
	unique = {v for v in values if v}
	return unique.pop() if len(unique) == 1 else ""


def get_data(filters, from_date, to_date):
	company = filters.company
	account = filters.get("cash_in_hand_account")
	get_cash_in_hand_accounts, get_fund_transfers = _get_report_functions()

	accounts = get_cash_in_hand_accounts(company)
	if account:
		accounts = [a for a in accounts if a.name == account]
	if not accounts:
		return []

	rows = get_fund_transfers(company, account, from_date, to_date)
	by_account = {}
	for row in rows:
		by_account.setdefault(row.paid_to, []).append(row)

	owners = {r.owner for acc_rows in by_account.values() for r in acc_rows}
	full_names = (
		{
			u.name: u.full_name
			for u in frappe.get_all("User", filters={"name": ["in", list(owners)]}, fields=["name", "full_name"])
		}
		if owners
		else {}
	)

	data = []
	for idx, acc in enumerate(accounts, start=1):
		acc_rows = by_account.get(acc.name, [])
		data.append(
			{
				"sl": idx,
				"cash_in_hand_account": acc.name,
				"total_voucher": len(acc_rows),
				"send_from": _single_value_or_blank(full_names.get(r.owner, r.owner) for r in acc_rows),
				"description": _single_value_or_blank(r.reference_no for r in acc_rows),
				"payment_method": _single_value_or_blank(r.mode_of_payment for r in acc_rows),
				"send_amount": flt(sum(flt(r.paid_amount) for r in acc_rows)),
			}
		)

	return data
