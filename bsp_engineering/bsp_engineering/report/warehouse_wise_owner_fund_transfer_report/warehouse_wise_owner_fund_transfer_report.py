# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Voucher-wise listing of Fund Transfers -- the Internal Transfer Payment
Entries posawesome's Fund Transfer feature creates, moving cash from the
company's central default_cash_account out to a showroom's own Cash In
Hand account (posawesome.posawesome.api.fund_transfer.create_fund_transfer).

The "Warehouse Name" column is the Cash In Hand account itself (paid_to)
-- each showroom's account is named after it, so the account IS the
warehouse identifier here; the actual Warehouse doctype isn't involved.
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
		{"label": _("Voucher"), "fieldname": "voucher", "fieldtype": "Link", "options": "Payment Entry", "width": 150},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Warehouse Name"),
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
	"""Every Cash In Hand leaf account under the same parent group as the
	company's default cash account, excluding that account itself -- the
	same set posawesome's Fund Transfer feature offers as "Account Paid
	To" options."""
	default_account = frappe.get_cached_value("Company", company, "default_cash_account")
	if not default_account:
		return []
	parent_account = frappe.db.get_value("Account", default_account, "parent_account")
	if not parent_account:
		return []
	return frappe.get_all(
		"Account",
		filters={
			"parent_account": parent_account,
			"is_group": 0,
			"company": company,
			"name": ["!=", default_account],
		},
		fields=["name", "account_name"],
		order_by="account_name asc",
	)


def _account_condition(account):
	if account:
		return "AND pe.paid_to = %(account)s", {"account": account}
	return "", {}


def get_fund_transfers(company, account, from_date, to_date):
	"""Every Fund Transfer Payment Entry in range, optionally scoped to a
	single Cash In Hand account (paid_to)."""
	condition, params = _account_condition(account)
	return frappe.db.sql(
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


def get_data(filters, from_date, to_date):
	company = filters.company
	account = filters.get("cash_in_hand_account")

	rows = get_fund_transfers(company, account, from_date, to_date)
	if not rows:
		return []

	full_names = {
		u.name: u.full_name
		for u in frappe.get_all(
			"User",
			filters={"name": ["in", list({r.owner for r in rows})]},
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
				"cash_in_hand_account": row.paid_to,
				"send_from": full_names.get(row.owner, row.owner),
				"description": row.reference_no or "",
				"payment_method": row.mode_of_payment or "",
				"send_amount": flt(row.paid_amount),
			}
		)

	return data
