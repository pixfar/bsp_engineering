"""Warehouse <-> Account mapping used by the BSP cash-summary and fund-transfer
reports (Daily Cash Summary, Warehouse Wise Daily Cash Summary, Warehouse Wise
Owner Fund Transfer, Warehouse Wise Owner Fund Transfer Summary).

A warehouse's Cash / Bank Accounts table (Warehouse.custom_cash_accounts, a
Warehouse Cash Account child table) is the single, explicit source of truth
for "which account(s) represent this warehouse's till/bank" -- picked by a
person on the Warehouse form, not inferred from account/warehouse names
matching (they can and do drift apart; see
bsp_engineering.patches.v1_0.add_warehouse_cash_accounts). A warehouse can
list more than one account (e.g. a Cash In Hand account plus a bank
account), and every account maps back to at most one warehouse.
"""

import frappe


def get_accounts_for_warehouse(warehouse):
	"""All accounts configured on one warehouse's Cash / Bank Accounts table."""
	if not warehouse:
		return []
	return frappe.get_all(
		'Warehouse Cash Account',
		filters={'parent': warehouse, 'parenttype': 'Warehouse'},
		pluck='account',
	)


def get_warehouse_by_account_map(company=None):
	"""{account: warehouse} for every configured Warehouse Cash Account row,
	optionally scoped to warehouses belonging to one company."""
	rows = frappe.get_all(
		'Warehouse Cash Account',
		filters={'parenttype': 'Warehouse'},
		fields=['account', 'parent'],
	)
	if not rows:
		return {}

	if company:
		warehouses_in_company = set(
			frappe.get_all('Warehouse', filters={'company': company}, pluck='name')
		)
		rows = [row for row in rows if row.parent in warehouses_in_company]

	# A misconfigured site could list the same account under two warehouses;
	# first row wins rather than silently double-counting it under both.
	mapping = {}
	for row in rows:
		mapping.setdefault(row.account, row.parent)
	return mapping


def get_mapped_accounts(company=None):
	"""Flat list of every account configured on any warehouse (optionally
	scoped to one company) -- for an `account IN (...)` SQL filter."""
	return list(get_warehouse_by_account_map(company=company).keys())
