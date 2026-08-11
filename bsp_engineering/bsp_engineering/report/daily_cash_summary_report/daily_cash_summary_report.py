# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

"""Warehouse-wise, day-wise cash summary matching the branch cash-box
workflow: each branch sells during the day, receives fund transfers into
the till, pays small local expenses out of the till, and deposits what's
left to the bank (typically the next morning).

For each warehouse and day:
- Sales Collection Summary -- every Sales Invoice on its own line, plus Total.
- Fund Transfer -- Internal Transfer Payment Entries attributed to the
  warehouse via custom_warehouse (custom_fund_transfer=1), plus Total.
- Cash Out Outflow -- every Expense Claim on its own line, plus Total Expense.
- BSP Deposit -- every actual BSP Daily Deposit on its own line, plus Total
  Deposited, plus an "Expected Deposit" reference line (= Income, i.e.
  Collection + Fund Transfer - Expense) so a branch that deposits correctly
  reconciles to zero.
- Opening/Closing Balance, carried forward day to day per warehouse.
  Closing Balance = Opening Balance + Income - Bank Deposit, where Income is
  Collection + Fund Transfer - Expense -- so on a day where the branch
  deposits exactly what it should, nothing carries over.

"Selling Amount" is the invoice's gross total before discount
(grand_total + discount_amount); "Received Amount" (collection) is what's
been collected against that invoice so far (grand_total - outstanding_amount).
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
		{"label": _("Discount Amount"), "fieldname": "discount_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Due Amount"), "fieldname": "due_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Received Amount"), "fieldname": "received_amount", "fieldtype": "Currency", "width": 130},
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


def _resolve_return_warehouses(rows):
	"""A return Sales Invoice leaves its own `set_warehouse` blank (only the
	item rows carry a warehouse, and not reliably the selling branch's own --
	it can be wherever the returned stock physically lands). The branch that
	made the original sale is the one whose till the refund actually comes
	back out of, so a return with no warehouse of its own inherits its
	`return_against` invoice's warehouse instead. Mutates `warehouse` on each
	row in place and returns the same list, dropping rows that still have no
	resolvable warehouse (e.g. a return against a non-warehouse invoice)."""
	missing = {row.return_against for row in rows if not row.warehouse and row.return_against}
	if missing:
		fallback = frappe._dict(
			frappe.get_all(
				"Sales Invoice",
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


def get_fund_transfers(company, warehouse, from_date, to_date):
	"""Fund Transfer income -- Internal Transfer Payment Entries attributed to
	a warehouse via custom_warehouse (set from Account Paid To on create).
	custom_fund_transfer=1 excludes deposit Payment Entries which are also
	Internal Transfers but already shown under BSP Deposit."""
	if not frappe.get_meta("Payment Entry").has_field("custom_warehouse"):
		return []

	wh_condition, wh_params = _warehouse_condition("pe.custom_warehouse", warehouse)
	fund_transfer_filter = ""
	if frappe.get_meta("Payment Entry").has_field("custom_fund_transfer"):
		fund_transfer_filter = "AND IFNULL(pe.custom_fund_transfer, 0) = 1"

	return frappe.db.sql(
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


def get_opening_balances(company, warehouse, from_date):
	"""Opening Balance = Sales Invoice amounts + Fund Transfer income before
	from_date, minus Bank Deposits before from_date. Expenses are not part of
	the seed value -- the day-by-day rows within the selected range already
	show the full Sales / Fund Transfer / Expense / Deposit breakdown."""
	balances = {}

	sales_rows = frappe.db.sql(
		"""
		SELECT si.name, si.set_warehouse AS warehouse, si.grand_total,
		       si.is_return, si.return_against
		FROM `tabSales Invoice` si
		WHERE si.docstatus = 1 AND si.company = %(company)s
		  AND si.posting_date < %(from_date)s
		""",
		{"company": company, "from_date": from_date},
		as_dict=True,
	)
	for row in _resolve_return_warehouses(sales_rows):
		if warehouse and row.warehouse != warehouse:
			continue
		balances[row.warehouse] = balances.get(row.warehouse, 0.0) + flt(row.grand_total)

	if frappe.get_meta("Payment Entry").has_field("custom_warehouse"):
		wh_condition, wh_params = _warehouse_condition("pe.custom_warehouse", warehouse)
		fund_transfer_filter = ""
		if frappe.get_meta("Payment Entry").has_field("custom_fund_transfer"):
			fund_transfer_filter = "AND IFNULL(pe.custom_fund_transfer, 0) = 1"
		for row in frappe.db.sql(
			f"""
			SELECT pe.custom_warehouse AS warehouse, SUM(pe.paid_amount) AS amount
			FROM `tabPayment Entry` pe
			WHERE pe.docstatus = 1 AND pe.company = %(company)s
			  AND pe.payment_type = 'Internal Transfer'
			  AND pe.custom_warehouse IS NOT NULL AND pe.custom_warehouse != ''
			  AND pe.posting_date < %(from_date)s
			  {fund_transfer_filter}
			  {wh_condition}
			GROUP BY pe.custom_warehouse
			""",
			{"company": company, "from_date": from_date, **wh_params},
			as_dict=True,
		):
			balances[row.warehouse] = balances.get(row.warehouse, 0.0) + flt(row.amount)

	wh_condition, wh_params = _warehouse_condition("dd.warehouse", warehouse)
	for row in frappe.db.sql(
		f"""
		SELECT dd.warehouse AS warehouse, SUM(dd.amount) AS amount
		FROM `tabBSP Daily Deposit` dd
		INNER JOIN `tabWarehouse` wh ON wh.name = dd.warehouse
		WHERE dd.docstatus = 1 AND wh.company = %(company)s
		  AND dd.warehouse IS NOT NULL AND dd.warehouse != ''
		  AND dd.posting_date < %(from_date)s
		  {wh_condition}
		GROUP BY dd.warehouse
		""",
		{"company": company, "from_date": from_date, **wh_params},
		as_dict=True,
	):
		balances[row.warehouse] = balances.get(row.warehouse, 0.0) - flt(row.amount)

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
			{"sales": [], "expenses": [], "deposits": [], "fund_transfers": []},
		)

	for inv in get_sales_invoices(company, warehouse, from_date, to_date):
		ensure_group((inv.warehouse, inv.posting_date))["sales"].append(inv)

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

	data = []
	for wh in warehouses:
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
						"particulars": _("Fund Transfer"),
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

			income = sales_total["received_amount"] + fund_transfer_total - expense_total
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
				_("Expected Deposit (Collection + Fund Transfer - Expense)"),
				deposit_amount=income,
			))

			closing_balance = opening_balance + income - deposit_total
			data.append(_bold_row(wh, current_date, _("Closing Balance"), balance_amount=closing_balance))

			running_balance = closing_balance
			current_date = add_days(current_date, 1)

	return data
