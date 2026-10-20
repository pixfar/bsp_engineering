# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Warehouse-wise, day-wise cash summary matching the branch cash-box
workflow: each branch sells during the day, receives payments and fund
transfers into the till, pays small local expenses and local purchases out of
the till, and deposits what's left to the bank (typically the next morning).

Every warehouse-day is built by get_day_summary() -- the same function POS
Awesome's Daily Cash Summary page and PDF use -- so this report shows exactly
the same sections and figures:
- Sales Collection Summary -- each Sales Invoice of the day; Received is what
  was paid against it by that day's Payment Entries.
- Customer Payments -- that day's customer Payment Entries for older invoices
  (or on account).
- Purchase Summary / Supplier Payments -- the same, for money paid out.
- Fund Transfer, Journal Entries (against the till's cash accounts), Cash Out
  Outflow (Expense Claim lines) and BSP Deposit.
- Opening/Closing Balance. For a warehouse with Cash / Bank Accounts mapped,
  Closing Balance is the real ledger balance and anything posted there that
  isn't itemised shows as Other Ledger Activity.

"Selling/Purchase Amount" is the invoice's gross total before discount
(grand_total + discount_amount). Returns (is_return=1) carry a negative
grand_total, so they net out automatically.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, add_days


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
	data, report_summary = get_data(filters, from_date, to_date)
	return columns, data, None, None, report_summary


def get_columns():
	return [
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Data", "width": 170},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 95},
		{"label": _("S.L"), "fieldname": "sl", "fieldtype": "Data", "width": 40},
		{"label": _("Particulars"), "fieldname": "particulars", "fieldtype": "Data", "width": 230},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 230},
		{"label": _("Reference No"), "fieldname": "reference_no", "fieldtype": "Data", "width": 150},
		{"label": _("Selling Amount"), "fieldname": "selling_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Purchase Amount"), "fieldname": "purchase_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Discount Amount"), "fieldname": "discount_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Due Amount"), "fieldname": "due_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Received Amount"), "fieldname": "received_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Paid Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Fund Transfer"), "fieldname": "fund_transfer_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Journal Amount"), "fieldname": "journal_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Expense Amount"), "fieldname": "expense_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Deposit Amount"), "fieldname": "deposit_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Balance"), "fieldname": "balance_amount", "fieldtype": "Currency", "width": 130},
	]


def _warehouse_condition(column, warehouse):
	"""column must be the fully-qualified column, e.g. "si.set_warehouse" --
	each doctype involved names its warehouse field differently."""
	if warehouse:
		return f"AND {column} = %(warehouse)s", {"warehouse": warehouse}
	return "", {}


def _resolve_return_warehouses(rows, doctype="Sales Invoice"):
	"""A return Sales/Purchase Invoice leaves its own `set_warehouse` blank
	(only the item rows carry a warehouse, and not reliably the selling/
	receiving branch's own -- it can be wherever the returned stock
	physically lands). The branch that made the original transaction is the
	one whose till the refund actually flows through, so a return with no
	warehouse of its own inherits its `return_against` invoice's warehouse
	instead. Mutates `warehouse` on each row in place and returns the same
	list, dropping rows that still have no resolvable warehouse (e.g. a
	return against a non-warehouse invoice)."""
	missing = {row.return_against for row in rows if not row.warehouse and row.return_against}
	if missing:
		fallback = frappe._dict(
			frappe.get_all(
				doctype,
				filters={"name": ["in", list(missing)]},
				fields=["name", "set_warehouse"],
				as_list=True,
			)
		)
		for row in rows:
			if not row.warehouse and row.return_against:
				row.warehouse = fallback.get(row.return_against)
	return [row for row in rows if row.warehouse]


def get_sales_invoices(company, warehouse, from_date, to_date):
	rows = frappe.db.sql(
		"""
		SELECT si.name, si.set_warehouse AS warehouse, si.posting_date,
		       si.grand_total, si.discount_amount, si.outstanding_amount,
		       si.is_return, si.return_against
		FROM `tabSales Invoice` si
		WHERE si.docstatus = 1
		  AND si.company = %(company)s
		  AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		""",
		{"company": company, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	rows = _resolve_return_warehouses(rows)
	if warehouse:
		rows = [row for row in rows if row.warehouse == warehouse]
	rows.sort(key=lambda row: (row.warehouse, row.posting_date, row.name))
	return rows


def get_purchase_invoices(company, warehouse, from_date, to_date):
	"""Mirrors get_sales_invoices() -- same shape, same return handling, but
	for cash paid *out* of the till for local purchases. Purchase Returns
	(is_return=1) come back with a negative grand_total/outstanding_amount,
	so they net out of the totals below automatically."""
	rows = frappe.db.sql(
		"""
		SELECT pi.name, pi.set_warehouse AS warehouse, pi.posting_date,
		       pi.grand_total, pi.discount_amount, pi.outstanding_amount,
		       pi.is_return, pi.return_against
		FROM `tabPurchase Invoice` pi
		WHERE pi.docstatus = 1
		  AND pi.company = %(company)s
		  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
		""",
		{"company": company, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	rows = _resolve_return_warehouses(rows, doctype="Purchase Invoice")
	if warehouse:
		rows = [row for row in rows if row.warehouse == warehouse]
	rows.sort(key=lambda row: (row.warehouse, row.posting_date, row.name))
	return rows


def get_expense_claims(company, warehouse, from_date, to_date):
	wh_condition, wh_params = _warehouse_condition("ec.custom_warehouse", warehouse)
	return frappe.db.sql(
		f"""
		SELECT ec.name, ec.custom_warehouse AS warehouse, ec.posting_date,
		       ec.grand_total, ec.remark
		FROM `tabExpense Claim` ec
		WHERE ec.docstatus = 1
		  AND ec.company = %(company)s
		  AND ec.custom_warehouse IS NOT NULL AND ec.custom_warehouse != ''
		  AND ec.posting_date BETWEEN %(from_date)s AND %(to_date)s
		  {wh_condition}
		ORDER BY ec.custom_warehouse, ec.posting_date, ec.name
		""",
		{"company": company, "from_date": from_date, "to_date": to_date, **wh_params},
		as_dict=True,
	)


def get_deposits(company, warehouse, from_date, to_date):
	# BSP Daily Deposit has no `company` field of its own -- scope by company
	# via the warehouse it belongs to instead.
	wh_condition, wh_params = _warehouse_condition("dd.warehouse", warehouse)
	return frappe.db.sql(
		f"""
		SELECT dd.name, dd.warehouse, dd.posting_date, dd.amount,
		       dd.deposit_type, dd.bank_name
		FROM `tabBSP Daily Deposit` dd
		INNER JOIN `tabWarehouse` wh ON wh.name = dd.warehouse
		WHERE dd.docstatus = 1
		  AND wh.company = %(company)s
		  AND dd.warehouse IS NOT NULL AND dd.warehouse != ''
		  AND dd.posting_date BETWEEN %(from_date)s AND %(to_date)s
		  {wh_condition}
		ORDER BY dd.warehouse, dd.posting_date, dd.name
		""",
		{"company": company, "from_date": from_date, "to_date": to_date, **wh_params},
		as_dict=True,
	)


def get_journal_adjustments(company, warehouse, from_date, to_date):
	"""Manual cash adjustments/receipts posted directly via Journal Entry
	against one of a warehouse's Cash / Bank Accounts (Warehouse.
	custom_cash_accounts -- see bsp_engineering.utils.warehouse_accounts)
	-- e.g. correcting a till count, or booking an opening balance that
	never went through a Payment Entry. `amount` is signed (net debit minus
	credit against that account), so a corrective credit reduces the
	warehouse's balance same as any other outflow. Merged into
	get_fund_transfers()'s return value below so every downstream
	consumer (opening balance carry-forward, this report, and the
	warehouse-wise summary/PDF that reuse it) picks these up for free."""
	from bsp_engineering.utils.warehouse_accounts import (
		get_accounts_for_warehouse,
		get_warehouse_by_account_map,
	)

	if warehouse:
		accounts = get_accounts_for_warehouse(warehouse)
		account_to_warehouse = {account: warehouse for account in accounts}
	else:
		account_to_warehouse = get_warehouse_by_account_map(company)
		accounts = list(account_to_warehouse.keys())

	if not accounts:
		return []

	rows = frappe.db.sql(
		"""
		SELECT je.name, jea.account,
		       (IFNULL(jea.debit_in_account_currency, 0)
		        - IFNULL(jea.credit_in_account_currency, 0)) AS amount,
		       je.posting_date, je.user_remark, je.cheque_no
		FROM `tabJournal Entry Account` jea
		INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
		WHERE je.docstatus = 1
		  AND je.company = %(company)s
		  AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s
		  AND jea.account IN %(accounts)s
		ORDER BY je.posting_date, je.name
		""",
		{
			"company": company,
			"from_date": from_date,
			"to_date": to_date,
			"accounts": tuple(accounts),
		},
		as_dict=True,
	)

	for row in rows:
		row["warehouse"] = account_to_warehouse.get(row.account)
		row["paid_from"] = ""
		row["paid_to"] = row.account
		row["mode_of_payment"] = _("Journal Entry")
		row["reference_no"] = row.user_remark or row.cheque_no or ""
		row["source_label"] = _("Journal Entry")

	return [row for row in rows if row.warehouse]


def get_fund_transfers(company, warehouse, from_date, to_date):
	"""Fund Transfer income -- Internal Transfer Payment Entries attributed to
	a warehouse via custom_warehouse (set from Account Paid To on create),
	plus manual Journal Entry adjustments against that warehouse's own Cash
	/ Bank Accounts (see get_journal_adjustments) -- both shown as separate
	traceable rows but counted toward the same Fund Transfer total.
	custom_fund_transfer=1 excludes deposit Payment Entries which are also
	Internal Transfers but already shown under BSP Deposit."""
	pe_rows = []
	if frappe.get_meta("Payment Entry").has_field("custom_warehouse"):
		wh_condition, wh_params = _warehouse_condition("pe.custom_warehouse", warehouse)
		fund_transfer_filter = ""
		if frappe.get_meta("Payment Entry").has_field("custom_fund_transfer"):
			fund_transfer_filter = "AND IFNULL(pe.custom_fund_transfer, 0) = 1"

		pe_rows = frappe.db.sql(
			f"""
			SELECT pe.name, pe.custom_warehouse AS warehouse, pe.posting_date,
			       pe.paid_amount AS amount, pe.paid_from, pe.paid_to,
			       pe.mode_of_payment, pe.reference_no
			FROM `tabPayment Entry` pe
			WHERE pe.docstatus = 1
			  AND pe.company = %(company)s
			  AND pe.payment_type = 'Internal Transfer'
			  AND pe.custom_warehouse IS NOT NULL AND pe.custom_warehouse != ''
			  AND pe.posting_date BETWEEN %(from_date)s AND %(to_date)s
			  {fund_transfer_filter}
			  {wh_condition}
			ORDER BY pe.custom_warehouse, pe.posting_date, pe.name
			""",
			{"company": company, "from_date": from_date, "to_date": to_date, **wh_params},
			as_dict=True,
		)

	je_rows = get_journal_adjustments(company, warehouse, from_date, to_date)

	rows = list(pe_rows) + je_rows
	rows.sort(key=lambda row: (row.warehouse, row.posting_date, row.name))
	return rows


def get_gl_balance(accounts, company, as_of_date):
	"""Real ledger balance (debit - credit) for a set of accounts, as of the
	end of as_of_date -- the exact same figure the Trial Balance report
	shows for those accounts. This is the authoritative source of truth;
	see get_opening_balances() for why it's preferred over the formula-based
	estimate below wherever it's available."""
	if not accounts:
		return 0.0
	result = frappe.db.sql(
		"""
		SELECT SUM(debit) - SUM(credit)
		FROM `tabGL Entry`
		WHERE account IN %(accounts)s
		  AND company = %(company)s
		  AND is_cancelled = 0
		  AND posting_date <= %(as_of_date)s
		""",
		{"accounts": tuple(accounts), "company": company, "as_of_date": as_of_date},
	)
	return flt(result[0][0]) if result and result[0][0] is not None else 0.0


def get_opening_balances(company, warehouse, from_date):
	"""Opening Balance for from_date, per warehouse.

	For a warehouse with a Cash / Bank Accounts table configured
	(Warehouse.custom_cash_accounts -- see
	bsp_engineering.utils.warehouse_accounts), this is the *real* ledger
	balance of those accounts as of the day before from_date (get_gl_balance)
	-- the same figure Trial Balance shows, since it comes from the same GL
	Entry table. This is authoritative: unlike the formula below, it isn't
	blind to ordinary Payment Entries, Journal Entries posted for reasons
	other than a till adjustment, or anything else posted straight to the
	account -- all of which silently drove the formula-based estimate further
	and further from the truth the longer a warehouse had been running.

	A warehouse with no Cash / Bank Accounts configured yet has no ledger to
	query, so it falls back to the old formula-based estimate (same as
	before this GL-based lookup existed):
	    Income = Collection (received) + Fund Transfer - Expense - Purchase Paid
	    Balance += Income - Deposit
	compounded over all history strictly before from_date, reusing
	get_sales_invoices/get_purchase_invoices/get_expense_claims/get_deposits/
	get_fund_transfers themselves (same warehouse resolution, same filters)
	so it can't drift from the day-by-day math elsewhere in this module.
	Configure Warehouse.custom_cash_accounts for accurate figures."""
	from bsp_engineering.utils.warehouse_accounts import get_accounts_for_warehouse, get_warehouse_by_account_map

	from_date = getdate(from_date)
	epoch = getdate("1900-01-01")
	if from_date <= epoch:
		return {}
	cutoff = add_days(from_date, -1)

	balances = {}

	if warehouse:
		mapped_warehouses = [warehouse] if get_accounts_for_warehouse(warehouse) else []
	else:
		mapped_warehouses = sorted(set(get_warehouse_by_account_map(company).values()))

	for wh in mapped_warehouses:
		balances[wh] = get_gl_balance(get_accounts_for_warehouse(wh), company, cutoff)

	def apply(rows, amount_fn, sign):
		for row in rows:
			# GL-based warehouses already have an authoritative balance above --
			# don't let the formula-based estimate silently overwrite it.
			if not row.warehouse or row.warehouse in balances:
				continue
			balances[row.warehouse] = balances.get(row.warehouse, 0.0) + sign * amount_fn(row)

	apply(
		get_sales_invoices(company, warehouse, epoch, cutoff),
		lambda row: flt(row.grand_total) - flt(row.outstanding_amount),
		1,
	)
	apply(
		get_purchase_invoices(company, warehouse, epoch, cutoff),
		lambda row: flt(row.grand_total) - flt(row.outstanding_amount),
		-1,
	)
	apply(get_fund_transfers(company, warehouse, epoch, cutoff), lambda row: flt(row.amount), 1)
	apply(get_expense_claims(company, warehouse, epoch, cutoff), lambda row: flt(row.grand_total), -1)
	apply(get_deposits(company, warehouse, epoch, cutoff), lambda row: flt(row.amount), -1)

	return balances


def get_party_payments(company, warehouse, accounts, report_date):
	"""Customer / Supplier Payment Entries posted on report_date that moved
	money through this warehouse's till -- its cash account(s) as paid_to /
	paid_from, or tagged with the warehouse (custom_warehouse). Covers the
	sale-time payments POS creates as well as payments made later from
	Payments > Customer / Supplier.

	`cash` is the signed effect on the till: + money in, - money out.
	`refs` is the Payment Entry's references (allocated_amount in company currency)."""
	conditions = ["pe.custom_warehouse = %(warehouse)s"]
	if accounts:
		conditions += ["pe.paid_to IN %(accounts)s", "pe.paid_from IN %(accounts)s"]

	rows = frappe.db.sql(
		f"""
		SELECT pe.name, pe.payment_type, pe.party_type, pe.party, pe.party_name,
		       pe.mode_of_payment, pe.reference_no, pe.custom_cheque_bank,
		       pe.base_paid_amount, pe.base_received_amount
		FROM `tabPayment Entry` pe
		WHERE pe.docstatus = 1
		  AND pe.company = %(company)s
		  AND pe.posting_date = %(date)s
		  AND pe.party_type IN ('Customer', 'Supplier')
		  AND ({" OR ".join(conditions)})
		ORDER BY pe.creation, pe.name
		""",
		{"company": company, "date": report_date, "warehouse": warehouse, "accounts": tuple(accounts or [""])},
		as_dict=True,
	)
	if not rows:
		return []

	refs = frappe.db.sql(
		"""
		SELECT parent, reference_doctype, reference_name, allocated_amount
		FROM `tabPayment Entry Reference`
		WHERE parent IN %(names)s
		ORDER BY idx
		""",
		{"names": tuple(row.name for row in rows)},
		as_dict=True,
	)
	refs_by_pe = {}
	for ref in refs:
		refs_by_pe.setdefault(ref.parent, []).append(ref)

	for row in rows:
		row.cash = flt(row.base_received_amount) if row.payment_type == "Receive" else -flt(row.base_paid_amount)
		row.refs = refs_by_pe.get(row.name, [])
	return rows


def get_journal_party_map(journal_names):
	"""{journal entry: "Customer: X, Supplier: Y"} -- the parties named on the
	other rows of each Journal Entry, so a JE payment to/from a customer or
	supplier shows who it was for."""
	if not journal_names:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT parent, party_type, party
		FROM `tabJournal Entry Account`
		WHERE parent IN %(names)s AND IFNULL(party, '') != ''
		""",
		{"names": tuple(journal_names)},
		as_dict=True,
	)
	parties = {}
	for row in rows:
		parties.setdefault(row.parent, []).append(f"{row.party_type}: {row.party}")
	return {name: ", ".join(values) for name, values in parties.items()}


def get_day_summary(company, warehouse, report_date, opening_balance=None):
	"""One warehouse, one day -- the branch's cash-box handover slip. Shared
	by this Script Report and POS Awesome's Daily Cash Summary page/PDF
	(posawesome.posawesome.api.daily_cash_summary_pdf) so both always show
	the same rows and figures. Amounts are raw floats; callers format them.

	Money received / paid is counted on the Payment Entry's own posting
	date, so a customer paying an old invoice today shows up today
	(Customer Payments) and never changes an earlier day's figures.

	opening_balance: pass the previous day's closing balance when walking a
	date range; when None it is looked up (get_opening_balances)."""
	from bsp_engineering.utils.warehouse_accounts import get_accounts_for_warehouse

	report_date = getdate(report_date)
	wh_accounts = get_accounts_for_warehouse(warehouse)

	invoices = get_sales_invoices(company, warehouse, report_date, report_date)
	purchases = get_purchase_invoices(company, warehouse, report_date, report_date)
	expenses = get_expense_claims(company, warehouse, report_date, report_date)
	deposits = get_deposits(company, warehouse, report_date, report_date)
	transfers = get_fund_transfers(company, warehouse, report_date, report_date)
	payments = get_party_payments(company, warehouse, wh_accounts, report_date)
	if opening_balance is None:
		opening_balance = get_opening_balances(company, warehouse, report_date).get(warehouse)
	opening_balance = flt(opening_balance)

	# get_fund_transfers() also returns manual Journal Entries against the
	# till's accounts -- shown in their own section.
	fund_transfers = [row for row in transfers if row.get("source_label") != _("Journal Entry")]
	journals = [row for row in transfers if row.get("source_label") == _("Journal Entry")]

	# ── Money received / paid today against today's own invoices ─────────
	sales_names = {inv.name for inv in invoices}
	purchase_names = {inv.name for inv in purchases}
	received_today, paid_today = {}, {}
	for pe in payments:
		for ref in pe.refs:
			if pe.party_type == "Customer" and ref.reference_name in sales_names:
				received_today[ref.reference_name] = received_today.get(ref.reference_name, 0.0) + flt(
					ref.allocated_amount
				)
			elif pe.party_type == "Supplier" and ref.reference_name in purchase_names:
				paid_today[ref.reference_name] = paid_today.get(ref.reference_name, 0.0) + flt(
					ref.allocated_amount
				)

	# ── Sales Collection Summary ──────────────────────────────────────────
	sales_rows = []
	sales_total = {"selling": 0.0, "discount": 0.0, "due": 0.0, "received": 0.0}
	for idx, inv in enumerate(invoices, start=1):
		selling = flt(inv.grand_total) + flt(inv.discount_amount)
		discount = flt(inv.discount_amount)
		received = received_today.get(inv.name, 0.0)
		due = flt(inv.grand_total) - received
		sales_total["selling"] += selling
		sales_total["discount"] += discount
		sales_total["due"] += due
		sales_total["received"] += received
		sales_rows.append(
			frappe._dict(
				sl=idx,
				invoice_no=inv.name,
				description=_("Return against {0}").format(inv.return_against) if inv.is_return else "",
				selling=selling,
				discount=discount,
				due=due,
				received=received,
			)
		)

	# ── Purchase Summary ──────────────────────────────────────────────────
	purchase_rows = []
	purchase_total = {"purchase": 0.0, "discount": 0.0, "due": 0.0, "paid": 0.0}
	for idx, inv in enumerate(purchases, start=1):
		amount = flt(inv.grand_total) + flt(inv.discount_amount)
		discount = flt(inv.discount_amount)
		paid = paid_today.get(inv.name, 0.0)
		due = flt(inv.grand_total) - paid
		purchase_total["purchase"] += amount
		purchase_total["discount"] += discount
		purchase_total["due"] += due
		purchase_total["paid"] += paid
		purchase_rows.append(
			frappe._dict(
				sl=idx,
				invoice_no=inv.name,
				supplier=frappe.db.get_value("Purchase Invoice", inv.name, "supplier_name") or "",
				description=_("Return against {0}").format(inv.return_against) if inv.is_return else "",
				purchase=amount,
				discount=discount,
				due=due,
				paid=paid,
			)
		)

	# ── Customer / Supplier Payments (not for today's own invoices) ───────
	def payment_rows_for(party_type, own_invoices):
		rows, total = [], 0.0
		for pe in payments:
			if pe.party_type != party_type:
				continue
			own = sum(flt(r.allocated_amount) for r in pe.refs if r.reference_name in own_invoices)
			# Signed from the till's point of view: + in, - out.
			own_cash = own if party_type == "Customer" else -own
			amount = flt(pe.cash) - own_cash
			if abs(amount) < 0.005:
				continue
			other_refs = [r.reference_name for r in pe.refs if r.reference_name not in own_invoices]
			total += amount
			rows.append(
				frappe._dict(
					sl=len(rows) + 1,
					party=pe.party_name or pe.party,
					payment_type=_(pe.payment_type),
					mode_of_payment=pe.mode_of_payment or "",
					against=", ".join(other_refs) if other_refs else _("Advance / On Account"),
					reference_no=pe.name,
					cheque=" ".join(filter(None, [pe.custom_cheque_bank, pe.reference_no]))
					if pe.custom_cheque_bank
					else "",
					amount=amount,
				)
			)
		return rows, total

	customer_payment_rows, customer_payment_total = payment_rows_for("Customer", sales_names)
	supplier_payment_rows, supplier_payment_total = payment_rows_for("Supplier", purchase_names)
	# Supplier total as money *out* of the till (positive = paid out).
	supplier_payment_out = -supplier_payment_total

	# ── Fund Transfer ─────────────────────────────────────────────────────
	fund_transfer_rows = [
		frappe._dict(
			sl=idx,
			particulars=_("Fund Transfer"),
			description=row.paid_to or "",
			reference_no=row.name,
			amount=flt(row.amount),
		)
		for idx, row in enumerate(fund_transfers, start=1)
	]
	fund_transfer_total = sum(row.amount for row in fund_transfer_rows)

	# ── Journal Entries against the till's cash account(s) ────────────────
	journal_parties = get_journal_party_map([row.name for row in journals])
	journal_rows = [
		frappe._dict(
			sl=idx,
			party=journal_parties.get(row.name, ""),
			description=row.get("reference_no") or "",
			reference_no=row.name,
			direction=_("In") if flt(row.amount) >= 0 else _("Out"),
			amount=flt(row.amount),
		)
		for idx, row in enumerate(journals, start=1)
	]
	journal_total = sum(row.amount for row in journal_rows)

	# ── Cash Out Outflow (expense claim lines) ────────────────────────────
	expense_total = sum(flt(row.grand_total) for row in expenses)
	expense_claim_names = [row.name for row in expenses]
	expense_lines = (
		frappe.get_all(
			"Expense Claim Detail",
			filters={"parent": ["in", expense_claim_names]},
			fields=["parent", "expense_type", "description", "amount", "sanctioned_amount"],
			order_by="parent, idx",
		)
		if expense_claim_names
		else []
	)
	expense_rows = [
		frappe._dict(
			sl=idx,
			cash_out_type=row.expense_type or _("Expense"),
			description=row.description or "",
			reference_no=row.parent,
			amount=flt(row.sanctioned_amount) or flt(row.amount),
		)
		for idx, row in enumerate(expense_lines, start=1)
	]

	# ── BSP Deposit ───────────────────────────────────────────────────────
	deposit_rows = [
		frappe._dict(
			sl=idx,
			deposit_type=row.deposit_type or _("Deposit"),
			bank_name=row.bank_name or "",
			reference_no=row.name,
			amount=flt(row.amount),
		)
		for idx, row in enumerate(deposits, start=1)
	]
	deposit_total = sum(row.amount for row in deposit_rows)

	# ── Totals ────────────────────────────────────────────────────────────
	total_collection = sales_total["received"] + customer_payment_total
	total_purchase_paid = purchase_total["paid"] + supplier_payment_out
	income = total_collection + fund_transfer_total + journal_total - expense_total - total_purchase_paid
	formula_closing_balance = opening_balance + income - deposit_total

	# GL-mapped warehouse: the real ledger balance of its cash account(s) --
	# the same figure Trial Balance shows. Anything posted to those accounts
	# that none of the sections above list is Other Ledger Activity instead
	# of being silently absorbed.
	closing_balance = (
		get_gl_balance(wh_accounts, company, report_date) if wh_accounts else formula_closing_balance
	)
	other_activity = closing_balance - formula_closing_balance if wh_accounts else 0.0
	if abs(other_activity) < 0.005:
		other_activity = 0.0

	has_activity = bool(
		sales_rows
		or purchase_rows
		or customer_payment_rows
		or supplier_payment_rows
		or fund_transfer_rows
		or journal_rows
		or expense_rows
		or deposit_rows
		or other_activity
	)

	return frappe._dict(
		warehouse=warehouse,
		report_date=report_date,
		has_activity=has_activity,
		opening_balance=opening_balance,
		closing_balance=closing_balance,
		other_activity=other_activity,
		income=income,
		total_collection=total_collection,
		total_purchase_paid=total_purchase_paid,
		sales_rows=sales_rows,
		sales_total=sales_total,
		purchase_rows=purchase_rows,
		purchase_total=purchase_total,
		customer_payment_rows=customer_payment_rows,
		customer_payment_total=customer_payment_total,
		supplier_payment_rows=supplier_payment_rows,
		supplier_payment_out=supplier_payment_out,
		fund_transfer_rows=fund_transfer_rows,
		fund_transfer_total=fund_transfer_total,
		journal_rows=journal_rows,
		journal_total=journal_total,
		expense_rows=expense_rows,
		expense_total=expense_total,
		deposit_rows=deposit_rows,
		deposit_total=deposit_total,
	)


def _section_title(warehouse, date, title):
	return {
		"warehouse": warehouse,
		"date": date,
		"particulars": f"<span style='font-weight:700;color:#178a4c;'>{title}</span>",
	}


def _bold_row(warehouse, date, particulars, **amounts):
	row = {"warehouse": warehouse, "date": date, "particulars": f"<b>{particulars}</b>"}
	row.update(amounts)
	return row


def _active_days(company, warehouse, from_date, to_date):
	"""{warehouse: set(dates)} that have anything to show -- itemised
	documents, Customer/Supplier Payment Entries, or any ledger posting to the
	warehouse's own Cash / Bank Accounts (so Other Ledger Activity days
	aren't skipped either)."""
	from bsp_engineering.utils.warehouse_accounts import get_accounts_for_warehouse

	if warehouse:
		warehouses = [warehouse]
	else:
		warehouses = frappe.get_all("Warehouse", filters={"company": company, "is_group": 0}, pluck="name")

	active = {}

	def mark(wh, date):
		if wh and (not warehouse or wh == warehouse):
			active.setdefault(wh, set()).add(getdate(date))

	for fetch in (get_sales_invoices, get_purchase_invoices, get_expense_claims, get_deposits, get_fund_transfers):
		for row in fetch(company, warehouse, from_date, to_date):
			mark(row.warehouse, row.posting_date)

	if frappe.get_meta("Payment Entry").has_field("custom_warehouse"):
		for row in frappe.db.sql(
			"""
			SELECT DISTINCT custom_warehouse AS warehouse, posting_date
			FROM `tabPayment Entry`
			WHERE docstatus = 1 AND company = %(company)s
			  AND party_type IN ('Customer', 'Supplier')
			  AND IFNULL(custom_warehouse, '') != ''
			  AND posting_date BETWEEN %(from_date)s AND %(to_date)s
			""",
			{"company": company, "from_date": from_date, "to_date": to_date},
			as_dict=True,
		):
			mark(row.warehouse, row.posting_date)

	warehouses_by_account = {}
	for wh in warehouses:
		for account in get_accounts_for_warehouse(wh):
			warehouses_by_account.setdefault(account, []).append(wh)
	if warehouses_by_account:
		for row in frappe.db.sql(
			"""
			SELECT DISTINCT account, posting_date
			FROM `tabGL Entry`
			WHERE is_cancelled = 0 AND company = %(company)s
			  AND account IN %(accounts)s
			  AND posting_date BETWEEN %(from_date)s AND %(to_date)s
			""",
			{
				"company": company,
				"accounts": tuple(warehouses_by_account),
				"from_date": from_date,
				"to_date": to_date,
			},
			as_dict=True,
		):
			for wh in warehouses_by_account[row.account]:
				mark(wh, row.posting_date)

	return active


def _day_rows(day):
	"""Report rows for one warehouse-day (get_day_summary), laid out section
	by section the same way as POS Awesome's Daily Cash Summary page."""
	wh, date = day.warehouse, day.report_date
	rows = [_bold_row(wh, date, _("Opening Balance"), balance_amount=day.opening_balance)]

	def line(**values):
		rows.append({"warehouse": wh, "date": date, **values})

	def payment_particulars(row):
		return " · ".join(filter(None, [row.party, row.payment_type, row.mode_of_payment]))

	if day.sales_rows:
		rows.append(_section_title(wh, date, _("Sales Collection Summary")))
		for row in day.sales_rows:
			line(
				sl=row.sl,
				particulars=row.invoice_no,
				description=row.description,
				selling_amount=row.selling,
				discount_amount=row.discount,
				due_amount=row.due,
				received_amount=row.received,
			)
		total = day.sales_total
		rows.append(
			_bold_row(
				wh,
				date,
				_("Total Received"),
				selling_amount=total["selling"],
				discount_amount=total["discount"],
				due_amount=total["due"],
				received_amount=total["received"],
			)
		)

	if day.customer_payment_rows:
		rows.append(_section_title(wh, date, _("Customer Payments")))
		for row in day.customer_payment_rows:
			line(
				sl=row.sl,
				particulars=payment_particulars(row),
				description=" ".join(filter(None, [row.against, row.cheque])),
				reference_no=row.reference_no,
				received_amount=row.amount,
			)
		rows.append(
			_bold_row(wh, date, _("Total Customer Payments"), received_amount=day.customer_payment_total)
		)

	if day.purchase_rows:
		rows.append(_section_title(wh, date, _("Purchase Summary")))
		for row in day.purchase_rows:
			line(
				sl=row.sl,
				particulars=row.invoice_no,
				description=" · ".join(filter(None, [row.supplier, row.description])),
				purchase_amount=row.purchase,
				discount_amount=row.discount,
				due_amount=row.due,
				paid_amount=row.paid,
			)
		total = day.purchase_total
		rows.append(
			_bold_row(
				wh,
				date,
				_("Total Paid"),
				purchase_amount=total["purchase"],
				discount_amount=total["discount"],
				due_amount=total["due"],
				paid_amount=total["paid"],
			)
		)

	if day.supplier_payment_rows:
		rows.append(_section_title(wh, date, _("Supplier Payments")))
		for row in day.supplier_payment_rows:
			line(
				sl=row.sl,
				particulars=payment_particulars(row),
				description=" ".join(filter(None, [row.against, row.cheque])),
				reference_no=row.reference_no,
				# Money out of the till, shown positive.
				paid_amount=-row.amount,
			)
		rows.append(_bold_row(wh, date, _("Total Supplier Payments"), paid_amount=day.supplier_payment_out))

	if day.fund_transfer_rows:
		rows.append(_section_title(wh, date, _("Fund Transfer")))
		for row in day.fund_transfer_rows:
			line(
				sl=row.sl,
				particulars=row.particulars,
				description=row.description,
				reference_no=row.reference_no,
				fund_transfer_amount=row.amount,
			)
		rows.append(
			_bold_row(wh, date, _("Total Fund Transfer"), fund_transfer_amount=day.fund_transfer_total)
		)

	if day.journal_rows:
		rows.append(_section_title(wh, date, _("Journal Entries")))
		for row in day.journal_rows:
			line(
				sl=row.sl,
				particulars=row.party or _("Journal Entry"),
				description=" · ".join(filter(None, [row.direction, row.description])),
				reference_no=row.reference_no,
				journal_amount=row.amount,
			)
		rows.append(_bold_row(wh, date, _("Total Journal Entries"), journal_amount=day.journal_total))

	if day.expense_rows:
		rows.append(_section_title(wh, date, _("Cash Out Outflow")))
		for row in day.expense_rows:
			line(
				sl=row.sl,
				particulars=row.cash_out_type,
				description=row.description,
				reference_no=row.reference_no,
				expense_amount=row.amount,
			)
		rows.append(_bold_row(wh, date, _("Total Expense"), expense_amount=day.expense_total))

	rows.append(_section_title(wh, date, _("BSP Deposit")))
	for row in day.deposit_rows:
		line(
			sl=row.sl,
			particulars=row.deposit_type,
			description=row.bank_name,
			reference_no=row.reference_no,
			deposit_amount=row.amount,
		)
	if day.deposit_rows:
		rows.append(_bold_row(wh, date, _("Total Deposited"), deposit_amount=day.deposit_total))

	rows.append(_section_title(wh, date, _("Summary")))
	rows.append(_bold_row(wh, date, _("Total Collection"), received_amount=day.total_collection))
	rows.append(_bold_row(wh, date, _("Total Purchase Paid"), paid_amount=day.total_purchase_paid))
	rows.append(
		_bold_row(
			wh,
			date,
			_("Expected Deposit (Collection + Fund Transfer + Journal - Expense - Purchase Paid)"),
			deposit_amount=day.income,
		)
	)
	if day.other_activity:
		rows.append(
			_bold_row(
				wh,
				date,
				_("Other Ledger Activity (not itemised above)"),
				balance_amount=day.other_activity,
			)
		)
	rows.append(_bold_row(wh, date, _("Closing Balance"), balance_amount=day.closing_balance))
	return rows


def _report_summary(days_by_warehouse):
	"""Header cards, same as POS Awesome's Daily Cash Summary page: totals over
	the period, with Opening/Closing Balance taken from each warehouse's first
	and last day and summed across warehouses."""
	days = [day for wh_days in days_by_warehouse.values() for day in wh_days]
	if not days:
		return None

	def total(field):
		return sum(flt(day[field]) for day in days)

	cards = [
		(_("Opening Balance"), sum(wh_days[0].opening_balance for wh_days in days_by_warehouse.values()), "Blue"),
		(_("Total Collection"), total("total_collection"), "Green"),
		(_("Fund Transfer"), total("fund_transfer_total"), "Green"),
		(_("Journal Entries"), total("journal_total"), "Purple"),
		(_("Purchase Paid"), total("total_purchase_paid"), "Red"),
		(_("Total Expense"), total("expense_total"), "Red"),
		(_("Total Deposited"), total("deposit_total"), "Purple"),
		(_("Closing Balance"), sum(wh_days[-1].closing_balance for wh_days in days_by_warehouse.values()), "Blue"),
	]
	return [
		{"label": label, "value": value, "datatype": "Currency", "indicator": indicator}
		for label, value, indicator in cards
	]


def get_data(filters, from_date, to_date):
	"""Every warehouse-day with activity, each built by get_day_summary() --
	the same function POS Awesome's Daily Cash Summary page and PDF use --
	so this report shows exactly the same rows and figures."""
	company = filters.company
	warehouse = filters.get("warehouse")

	active = _active_days(company, warehouse, from_date, to_date)
	if not active:
		return [], None

	# Warehouse blocks follow BSP's official warehouse order (Warehouse Sort Order).
	from bsp_engineering.utils.warehouse_sort import sort_warehouses

	data = []
	days_by_warehouse = {}
	for wh in sort_warehouses(set(active)):
		# Each day opens with the previous day's closing balance (for a
		# GL-mapped warehouse that's its ledger balance either way).
		running_balance = None
		for date in sorted(active[wh]):
			day = get_day_summary(company, wh, date, opening_balance=running_balance)
			running_balance = day.closing_balance
			if not day.has_activity:
				continue
			days_by_warehouse.setdefault(wh, []).append(day)
			data.extend(_day_rows(day))

	return data, _report_summary(days_by_warehouse)
