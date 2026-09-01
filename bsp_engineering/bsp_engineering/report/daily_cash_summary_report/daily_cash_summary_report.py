# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Warehouse-wise, day-wise cash summary matching the branch cash-box
workflow: each branch sells during the day, receives fund transfers into
the till, pays small local expenses and local purchases out of the till,
and deposits what's left to the bank (typically the next morning).

For each warehouse and day:
- Sales Collection Summary -- every Sales Invoice on its own line, plus Total.
  Sales Returns (is_return=1) are included with a negative amount, so a
  refund correctly *reduces* the day's collection/balance -- cash going back
  out to the customer.
- Purchase Summary -- every Purchase Invoice on its own line, plus Total.
  Purchase Returns (is_return=1) are included with a negative amount, so a
  supplier refund correctly *reduces* the day's purchase outflow, i.e.
  *increases* the balance -- cash coming back into the till.
- Fund Transfer -- Internal Transfer Payment Entries attributed to the
  warehouse via custom_warehouse (custom_fund_transfer=1), PLUS manual
  Journal Entry adjustments against that warehouse's own Cash / Bank
  Accounts (Warehouse.custom_cash_accounts -- e.g. a till-count correction,
  or an opening balance booked straight to the account) -- both shown as
  separate traceable rows but summed into the same Total.
- Cash Out Outflow -- every Expense Claim on its own line, plus Total Expense.
- BSP Deposit -- every actual BSP Daily Deposit on its own line, plus Total
  Deposited, plus an "Expected Deposit" reference line (= Income, i.e.
  Collection + Fund Transfer - Expense - Purchase Paid) so a branch that
  deposits correctly reconciles to zero.
- Opening/Closing Balance, carried forward day to day per warehouse.
  Closing Balance = Opening Balance + Income - Bank Deposit, where Income is
  Collection + Fund Transfer - Expense - Purchase Paid -- so on a day where
  the branch deposits exactly what it should, nothing carries over.

"Selling/Purchase Amount" is the invoice's gross total before discount
(grand_total + discount_amount); "Received/Paid Amount" (collection) is what
has been collected/paid against that invoice so far
(grand_total - outstanding_amount). A return invoice's grand_total is
negative, so both figures -- and everything derived from them -- net out
automatically once the return is entered; no separate "return" bookkeeping
is needed.
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
	data = get_data(filters, from_date, to_date)
	return columns, data


def get_columns():
	return [
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Data", "width": 170},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Data", "width": 95},
		{"label": _("S.L"), "fieldname": "sl", "fieldtype": "Data", "width": 40},
		{"label": _("Particulars"), "fieldname": "particulars", "fieldtype": "Data", "width": 230},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 170},
		{"label": _("Reference No"), "fieldname": "reference_no", "fieldtype": "Data", "width": 140},
		{"label": _("Selling Amount"), "fieldname": "selling_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Purchase Amount"), "fieldname": "purchase_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Discount Amount"), "fieldname": "discount_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Due Amount"), "fieldname": "due_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Received Amount"), "fieldname": "received_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Paid Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Fund Transfer"), "fieldname": "fund_transfer_amount", "fieldtype": "Currency", "width": 150},
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


def get_data(filters, from_date, to_date):
	company = filters.company
	warehouse = filters.get("warehouse")

	groups = {}

	def ensure_group(key):
		return groups.setdefault(
			key,
			{"sales": [], "purchases": [], "expenses": [], "deposits": [], "fund_transfers": []},
		)

	for inv in get_sales_invoices(company, warehouse, from_date, to_date):
		ensure_group((inv.warehouse, inv.posting_date))["sales"].append(inv)

	for inv in get_purchase_invoices(company, warehouse, from_date, to_date):
		ensure_group((inv.warehouse, inv.posting_date))["purchases"].append(inv)

	for row in get_expense_claims(company, warehouse, from_date, to_date):
		ensure_group((row.warehouse, row.posting_date))["expenses"].append(row)

	for row in get_deposits(company, warehouse, from_date, to_date):
		ensure_group((row.warehouse, row.posting_date))["deposits"].append(row)

	for row in get_fund_transfers(company, warehouse, from_date, to_date):
		ensure_group((row.warehouse, row.posting_date))["fund_transfers"].append(row)

	if not groups:
		return []

	warehouses = sorted({wh for wh, _d in groups.keys()})
	opening_balances = get_opening_balances(company, warehouse, from_date)

	from bsp_engineering.utils.warehouse_accounts import get_accounts_for_warehouse

	accounts_by_wh = {wh: get_accounts_for_warehouse(wh) for wh in warehouses}

	data = []
	for wh in warehouses:
		wh_accounts = accounts_by_wh[wh]
		running_balance = flt(opening_balances.get(wh))
		current_date = from_date
		while current_date <= to_date:
			key = (wh, current_date)
			if key not in groups:
				current_date = add_days(current_date, 1)
				continue

			group = groups[key]
			opening_balance = running_balance

			data.append(_bold_row(wh, current_date, _("Opening Balance"), balance_amount=opening_balance))

			sales_total = {"selling_amount": 0.0, "discount_amount": 0.0, "due_amount": 0.0, "received_amount": 0.0}
			if group["sales"]:
				data.append(_section_title(wh, current_date, _("Sales Collection Summary")))
				for idx, inv in enumerate(group["sales"], start=1):
					selling = flt(inv.grand_total) + flt(inv.discount_amount)
					discount = flt(inv.discount_amount)
					due = flt(inv.outstanding_amount)
					received = flt(inv.grand_total) - flt(inv.outstanding_amount)
					sales_total["selling_amount"] += selling
					sales_total["discount_amount"] += discount
					sales_total["due_amount"] += due
					sales_total["received_amount"] += received
					data.append({
						"warehouse": wh,
						"date": current_date,
						"sl": idx,
						"particulars": inv.name,
						"description": _("Return against {0}").format(inv.return_against) if inv.is_return else "",
						"selling_amount": selling,
						"discount_amount": discount,
						"due_amount": due,
						"received_amount": received,
					})
				data.append(_bold_row(wh, current_date, _("Total"), **sales_total))

			purchase_total = {"purchase_amount": 0.0, "discount_amount": 0.0, "due_amount": 0.0, "paid_amount": 0.0}
			if group["purchases"]:
				data.append(_section_title(wh, current_date, _("Purchase Summary")))
				for idx, inv in enumerate(group["purchases"], start=1):
					purchase_amount = flt(inv.grand_total) + flt(inv.discount_amount)
					discount = flt(inv.discount_amount)
					due = flt(inv.outstanding_amount)
					paid = flt(inv.grand_total) - flt(inv.outstanding_amount)
					purchase_total["purchase_amount"] += purchase_amount
					purchase_total["discount_amount"] += discount
					purchase_total["due_amount"] += due
					purchase_total["paid_amount"] += paid
					data.append({
						"warehouse": wh,
						"date": current_date,
						"sl": idx,
						"particulars": inv.name,
						"description": _("Return against {0}").format(inv.return_against) if inv.is_return else "",
						"purchase_amount": purchase_amount,
						"discount_amount": discount,
						"due_amount": due,
						"paid_amount": paid,
					})
				data.append(_bold_row(wh, current_date, _("Total"), **purchase_total))

			fund_transfer_total = 0.0
			if group["fund_transfers"]:
				data.append(_section_title(wh, current_date, _("Fund Transfer")))
				for idx, row in enumerate(group["fund_transfers"], start=1):
					amount = flt(row.amount)
					fund_transfer_total += amount
					data.append({
						"warehouse": wh,
						"date": current_date,
						"sl": idx,
						"particulars": row.get("source_label") or _("Fund Transfer"),
						"description": row.paid_to or "",
						"reference_no": row.name,
						"fund_transfer_amount": amount,
					})
				data.append(
					_bold_row(
						wh,
						current_date,
						_("Total Fund Transfer"),
						fund_transfer_amount=fund_transfer_total,
					)
				)

			expense_total = 0.0
			if group["expenses"]:
				data.append(_section_title(wh, current_date, _("Cash Out Outflow")))
				for idx, row in enumerate(group["expenses"], start=1):
					amount = flt(row.grand_total)
					expense_total += amount
					data.append({
						"warehouse": wh,
						"date": current_date,
						"sl": idx,
						"particulars": _("Expense"),
						"description": row.remark or "",
						"reference_no": row.name,
						"expense_amount": amount,
					})
				data.append(_bold_row(wh, current_date, _("Total Expense"), expense_amount=expense_total))

			income = (
				sales_total["received_amount"]
				+ fund_transfer_total
				- expense_total
				- purchase_total["paid_amount"]
			)
			deposit_total = 0.0
			data.append(_section_title(wh, current_date, _("BSP Deposit")))
			if group["deposits"]:
				for idx, row in enumerate(group["deposits"], start=1):
					amount = flt(row.amount)
					deposit_total += amount
					data.append({
						"warehouse": wh,
						"date": current_date,
						"sl": idx,
						"particulars": row.deposit_type or _("Deposit"),
						"description": row.bank_name or "",
						"reference_no": row.name,
						"deposit_amount": amount,
					})
				data.append(_bold_row(wh, current_date, _("Total Deposited"), deposit_amount=deposit_total))
			data.append(_bold_row(
				wh,
				current_date,
				_("Expected Deposit (Collection + Fund Transfer - Expense - Purchase Paid)"),
				deposit_amount=income,
			))

			if wh_accounts:
				# GL-mapped warehouse: Closing Balance is the *real* ledger
				# balance for this warehouse's Cash / Bank Accounts as of
				# today (get_gl_balance) -- the same figure Trial Balance
				# would show -- not the arithmetic derivation below, which is
				# blind to anything posted to the account outside the
				# Sales/Purchase/Expense/Deposit/Fund Transfer types this
				# report tracks. The gap between the two (if any) is real
				# ledger activity this report doesn't itemise -- surfaced
				# explicitly rather than silently absorbed into the balance.
				closing_balance = get_gl_balance(wh_accounts, company, current_date)
				other_activity = closing_balance - opening_balance - income + deposit_total
				if other_activity:
					data.append(
						_bold_row(
							wh,
							current_date,
							_("Other Ledger Activity (not itemised above)"),
							balance_amount=other_activity,
						)
					)
			else:
				closing_balance = opening_balance + income - deposit_total
			data.append(_bold_row(wh, current_date, _("Closing Balance"), balance_amount=closing_balance))

			running_balance = closing_balance
			current_date = add_days(current_date, 1)

	return data
