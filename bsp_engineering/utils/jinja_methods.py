import frappe


def get_account_balance_on(account, date=None, company=None):
	"""Account balance as of a date -- used by print formats (e.g. BSP
	Fundtransfer) to show a showroom's Cash In Hand balance before/after a
	voucher, without duplicating ERPNext's GL balance logic."""
	from erpnext.accounts.utils import get_balance_on

	return get_balance_on(account=account, date=date, company=company)


def get_invoice_payment_modes(doctype, name):
	"""Payment methods for Sales/Purchase Invoice print formats.

	Reads invoice payment rows, custom split rows, then Payment Entries.
	When a PE has no mode_of_payment, infers Cash/Bank from the account.
	"""
	if not doctype or not name:
		return []

	modes = []

	def add(mode):
		mode = (mode or '').strip()
		if mode and mode not in modes:
			modes.append(mode)

	child_tables = []
	if doctype == 'Sales Invoice':
		child_tables = [
			'Sales Invoice Payment',
			'Sales Invoice Payment Split',
		]
	elif doctype == 'Purchase Invoice':
		child_tables = [
			'Purchase Invoice Payment',
			'Purchase Invoice Payment Split',
		]

	for child in child_tables:
		if not frappe.db.exists('DocType', child):
			continue
		rows = frappe.db.sql(
			f"""
			SELECT mode_of_payment
			FROM `tab{child}`
			WHERE parent=%s
			  AND IFNULL(mode_of_payment, '') != ''
			  AND IFNULL(amount, 0) != 0
			""",
			name,
		)
		for (mode,) in rows:
			add(mode)

	pe_rows = frappe.db.sql(
		"""
		SELECT pe.mode_of_payment, pe.paid_to, pe.paid_from,
		       pe.payment_type
		FROM `tabPayment Entry` pe
		INNER JOIN `tabPayment Entry Reference` r
			ON r.parent = pe.name
		WHERE r.reference_doctype = %s
		  AND r.reference_name = %s
		  AND pe.docstatus = 1
		""",
		(doctype, name),
	)
	for mode, paid_to, paid_from, payment_type in pe_rows:
		if mode:
			add(mode)
			continue
		account = paid_to if payment_type == 'Receive' else paid_from
		if not account:
			continue
		account_type = frappe.db.get_value(
			'Account', account, 'account_type'
		)
		if account_type not in ('Cash', 'Bank'):
			continue
		linked = frappe.db.get_value(
			'Mode of Payment Account',
			{'default_account': account},
			'parent',
		)
		add(linked or account_type)

	return modes


def can_view_all_warehouse_stock():
	"""Whether the current user may see every warehouse's stock (System
	Manager, BSP Admin, BSP Viewer) -- print formats use it to show the
	other warehouse's stock only to them. Same rule as the POS screens
	(posawesome's get_expanded_permitted_warehouses returns None for them)."""
	from posawesome.posawesome.utils.warehouse_doc_permissions import (
		get_expanded_permitted_warehouses,
	)

	return get_expanded_permitted_warehouses() is None
