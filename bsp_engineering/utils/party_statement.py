"""Shared logic for the Customer / Supplier Accounts Statement reports.

Both reports read the party's General Ledger (GL Entry) and list every
transaction with a running balance:

    Closing Balance row
    one row per voucher, newest first (Sales/Purchase Invoice, Payment Entry, ...)
    Opening Balance row

Each voucher row's Balance is the running balance right after that voucher.

When no party is selected, the same block is repeated for every party
that has an opening balance or a transaction in the period.

Balance sign follows the party's side of the books so a positive number
always means "money outstanding":
    Customer: Debit - Credit   (customer owes us)
    Supplier: Credit - Debit   (we owe the supplier)
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

PARTY_CONFIG = {
	"Customer": {
		"name_field": "customer_name",
		"group_field": "customer_group",
		"group_doctype": "Customer Group",
		"sign": 1,
	},
	"Supplier": {
		"name_field": "supplier_name",
		"group_field": "supplier_group",
		"group_doctype": "Supplier Group",
		"sign": -1,
	},
}


def execute(party_type, filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	config = PARTY_CONFIG[party_type]
	currency = frappe.get_cached_value("Company", filters.company, "default_currency")

	columns = get_columns(party_type)
	data = get_data(party_type, config, filters, currency)
	return columns, data


def validate_filters(filters):
	if not filters.get("company"):
		frappe.throw(_("Company is required."))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))


def get_columns(party_type):
	return [
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _(party_type),
			"fieldname": "party",
			"fieldtype": "Link",
			"options": party_type,
			"width": 130,
		},
		{
			"label": _("{0} Name").format(_(party_type)),
			"fieldname": "party_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Voucher Type"),
			"fieldname": "voucher_type",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Voucher No"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 170,
		},
		{
			"label": _("Remarks"),
			"fieldname": "remarks",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": _("Debit"),
			"fieldname": "debit",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 130,
		},
		{
			"label": _("Credit"),
			"fieldname": "credit",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 130,
		},
		{
			"label": _("Balance"),
			"fieldname": "balance",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
	]


def get_parties(party_type, config, filters):
	"""party -> party name, limited by the party / party group filters."""
	party_filters = {}
	if filters.get("party"):
		party_filters["name"] = filters.party
	if filters.get("party_group"):
		lft, rgt = frappe.db.get_value(config["group_doctype"], filters.party_group, ["lft", "rgt"])
		groups = frappe.get_all(
			config["group_doctype"],
			filters={"lft": [">=", lft], "rgt": ["<=", rgt]},
			pluck="name",
		)
		party_filters[config["group_field"]] = ["in", groups]

	rows = frappe.get_all(party_type, filters=party_filters, fields=["name", config["name_field"]])
	return {row.name: row.get(config["name_field"]) or row.name for row in rows}


def get_data(party_type, config, filters, currency):
	parties = get_parties(party_type, config, filters)
	if not parties:
		return []

	sign = config["sign"]
	opening = get_opening_balances(party_type, parties, filters)
	entries = get_period_entries(party_type, parties, filters)

	entries_by_party = {}
	for entry in entries:
		entries_by_party.setdefault(entry.party, []).append(entry)

	data = []
	total_debit = total_credit = 0.0

	for party in sorted(parties, key=lambda p: (parties[p] or p).lower()):
		party_entries = entries_by_party.get(party, [])
		opening_row = opening.get(party) or frappe._dict(debit=0.0, credit=0.0)
		opening_balance = sign * (flt(opening_row.debit) - flt(opening_row.credit))

		if not party_entries and not flt(opening_balance, 2):
			continue

		party_name = parties[party]
		block = []
		block.append(
			{
				"posting_date": filters.from_date,
				"party": party,
				"party_name": party_name,
				"remarks": _("Opening Balance"),
				"debit": flt(opening_row.debit),
				"credit": flt(opening_row.credit),
				"balance": opening_balance,
				"currency": currency,
				"bold": 1,
			}
		)

		balance = opening_balance
		period_debit = period_credit = 0.0
		for entry in party_entries:
			balance += sign * (flt(entry.debit) - flt(entry.credit))
			period_debit += flt(entry.debit)
			period_credit += flt(entry.credit)
			block.append(
				{
					"posting_date": entry.posting_date,
					"party": party,
					"party_name": party_name,
					"voucher_type": entry.voucher_type,
					"voucher_no": entry.voucher_no,
					"remarks": entry.remarks,
					"debit": flt(entry.debit),
					"credit": flt(entry.credit),
					"balance": balance,
					"currency": currency,
				}
			)

		block.append(
			{
				"posting_date": filters.to_date,
				"party": party,
				"party_name": party_name,
				"remarks": _("Closing Balance"),
				"debit": flt(opening_row.debit) + period_debit,
				"credit": flt(opening_row.credit) + period_credit,
				"balance": balance,
				"currency": currency,
				"bold": 1,
			}
		)
		# Built oldest-first (the running balance needs that order), shown
		# newest-first so the latest transactions are at the top.
		data.extend(reversed(block))
		data.append({})

		total_debit += period_debit
		total_credit += period_credit

	if data and not filters.get("party"):
		data.append(
			{
				"remarks": _("Total (Period)"),
				"debit": total_debit,
				"credit": total_credit,
				"currency": currency,
				"bold": 1,
			}
		)

	return data


def get_party_condition(filters):
	# Without a party / party group filter every party of this type is in
	# scope, so skip the (possibly very long) IN list and let the query
	# return whoever has GL entries.
	if filters.get("party") or filters.get("party_group"):
		return "AND party IN %(parties)s"
	return ""


def get_opening_balances(party_type, parties, filters):
	rows = frappe.db.sql(
		"""
		SELECT party, SUM(debit) AS debit, SUM(credit) AS credit
		FROM `tabGL Entry`
		WHERE company = %(company)s
			AND party_type = %(party_type)s
			{party_condition}
			AND is_cancelled = 0
			AND (posting_date < %(from_date)s OR IFNULL(is_opening, 'No') = 'Yes')
		GROUP BY party
		""".format(party_condition=get_party_condition(filters)),
		{
			"company": filters.company,
			"party_type": party_type,
			"parties": tuple(parties),
			"from_date": filters.from_date,
		},
		as_dict=True,
	)
	return {row.party: row for row in rows}


def get_period_entries(party_type, parties, filters):
	# One row per voucher: an invoice or payment can post several GL lines
	# against the same party (e.g. multiple receivable rows).
	return frappe.db.sql(
		"""
		SELECT
			party, posting_date, voucher_type, voucher_no,
			SUM(debit) AS debit, SUM(credit) AS credit,
			MAX(remarks) AS remarks, MIN(creation) AS creation
		FROM `tabGL Entry`
		WHERE company = %(company)s
			AND party_type = %(party_type)s
			{party_condition}
			AND is_cancelled = 0
			AND posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND IFNULL(is_opening, 'No') = 'No'
		GROUP BY party, posting_date, voucher_type, voucher_no
		ORDER BY posting_date, creation, voucher_no
		""".format(party_condition=get_party_condition(filters)),
		{
			"company": filters.company,
			"party_type": party_type,
			"parties": tuple(parties),
			"from_date": filters.from_date,
			"to_date": filters.to_date,
		},
		as_dict=True,
	)
