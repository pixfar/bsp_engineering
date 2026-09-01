# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Voucher-wise listing of Fund Transfers -- the Internal Transfer Payment
Entries posawesome's Fund Transfer feature creates, moving cash from the
company's central default_cash_account out to a showroom's own Cash In
Hand account (posawesome.posawesome.api.fund_transfer.create_fund_transfer)
-- plus manual Journal Entry adjustments posted directly against one of
those same accounts (e.g. correcting a till count, or an opening balance
that never went through a Payment Entry).

Which accounts count as a warehouse's own is picked explicitly on the
Warehouse form (Warehouse.custom_cash_accounts, a Warehouse Cash Account
child table) rather than inferred from account/warehouse naming -- see
bsp_engineering.utils.warehouse_accounts. The "Warehouse" column is the
real Warehouse link; "Account" is the specific Cash/Bank account the
voucher moved money through (a warehouse can have more than one).
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
		{"label": _("Voucher"), "fieldname": "voucher", "fieldtype": "Data", "width": 150},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 170,
		},
		{
			"label": _("Account"),
			"fieldname": "cash_in_hand_account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 200,
		},
		{"label": _("Send From"), "fieldname": "send_from", "fieldtype": "Data", "width": 150},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 200},
		{"label": _("Payment Method"), "fieldname": "payment_method", "fieldtype": "Data", "width": 130},
		{"label": _("Send Amount"), "fieldname": "send_amount", "fieldtype": "Currency", "width": 130},
	]


def get_cash_in_hand_accounts(company):
	"""Every account configured on a warehouse's Cash / Bank Accounts table
	(Warehouse.custom_cash_accounts) for warehouses belonging to this
	company -- the authoritative set now, rather than inferring "Cash In
	Hand" accounts by their position in the Chart of Accounts. Each
	returned row also carries its `warehouse` so callers don't need a
	second lookup."""
	account_to_warehouse = _get_account_warehouse_map(company)
	if not account_to_warehouse:
		return []

	names = {
		row.name: row.account_name
		for row in frappe.get_all(
			"Account",
			filters={"name": ["in", list(account_to_warehouse.keys())]},
			fields=["name", "account_name"],
		)
	}

	accounts = [
		frappe._dict({"name": account, "account_name": names.get(account, account), "warehouse": warehouse})
		for account, warehouse in account_to_warehouse.items()
	]
	accounts.sort(key=lambda row: (row.warehouse, row.account_name))
	return accounts


def _get_account_warehouse_map(company):
	from bsp_engineering.utils.warehouse_accounts import get_warehouse_by_account_map

	return get_warehouse_by_account_map(company)


def _resolve_accounts(company, account, warehouse):
	"""Narrow down which account(s) a query should scope to, from whichever
	of `account` / `warehouse` filters are set. Returns None for "no
	scoping" (every mapped account for the company)."""
	from bsp_engineering.utils.warehouse_accounts import get_accounts_for_warehouse

	if warehouse:
		accounts = get_accounts_for_warehouse(warehouse)
		if account:
			accounts = [a for a in accounts if a == account]
		return accounts
	if account:
		return [account]
	return None


def get_fund_transfers(company, account, from_date, to_date, warehouse=None):
	"""Every Fund Transfer Payment Entry in range, optionally scoped to a
	single Cash/Bank account and/or warehouse, plus manual Journal Entry
	adjustments against those same accounts -- see the module docstring."""
	from bsp_engineering.bsp_engineering.report.daily_cash_summary_report.daily_cash_summary_report import (
		get_journal_adjustments,
	)

	accounts = _resolve_accounts(company, account, warehouse)
	if accounts is not None and not accounts:
		return []

	if accounts is None:
		condition, params = "", {}
	else:
		condition, params = "AND pe.paid_to IN %(accounts)s", {"accounts": tuple(accounts)}

	pe_rows = frappe.db.sql(
		f"""
		SELECT pe.name, pe.posting_date, pe.owner, pe.paid_from, pe.paid_to,
		       pe.mode_of_payment, pe.paid_amount, pe.reference_no
		FROM `tabPayment Entry` pe
		WHERE pe.docstatus = 1
		  AND pe.custom_fund_transfer = 1
		  AND pe.payment_type = 'Internal Transfer'
		  AND pe.company = %(company)s
		  AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
		  {condition}
		ORDER BY pe.posting_date, pe.name
		""",
		{"company": company, "from_date": from_date, "to_date": to_date, **params},
		as_dict=True,
	)

	je_rows = get_journal_adjustments(company, warehouse, from_date, to_date)
	if accounts is not None:
		je_rows = [row for row in je_rows if row.account in accounts]

	for row in je_rows:
		row["owner"] = None
		row["paid_amount"] = row.amount

	rows = list(pe_rows) + je_rows
	rows.sort(key=lambda row: (row.posting_date, row.name))
	return rows


def get_data(filters, from_date, to_date):
	company = filters.company
	account = filters.get("cash_in_hand_account")
	warehouse = filters.get("warehouse")

	rows = get_fund_transfers(company, account, from_date, to_date, warehouse=warehouse)
	if not rows:
		return []

	account_to_warehouse = _get_account_warehouse_map(company)

	full_names = {
		u.name: u.full_name
		for u in frappe.get_all(
			"User",
			filters={"name": ["in", list({r.owner for r in rows if r.owner})]},
			fields=["name", "full_name"],
		)
	}

	data = []
	for idx, row in enumerate(rows, start=1):
		data.append(
			{
				"sl": idx,
				"voucher": row.name,
				"posting_date": row.posting_date,
				"warehouse": row.get("warehouse") or account_to_warehouse.get(row.paid_to),
				"cash_in_hand_account": row.paid_to,
				"send_from": full_names.get(row.owner, row.owner) if row.owner else "",
				"description": row.reference_no or "",
				"payment_method": row.mode_of_payment or "",
				"send_amount": flt(row.paid_amount),
			}
		)

	return data
