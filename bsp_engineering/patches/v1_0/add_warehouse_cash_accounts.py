import frappe


def execute():
	"""Warehouse gets its own "Cash / Bank Accounts" table (custom_cash_accounts,
	a Warehouse Cash Account child table) so a warehouse's cash-report
	identity is picked explicitly instead of inferred from account/warehouse
	naming conventions -- those have drifted apart on some warehouses since
	Account.custom_warehouse (see add_account_warehouse_link.py) was seeded
	by exact-name matching only. A warehouse can now list more than one
	account (e.g. a Cash In Hand account plus a bank account) and every
	report that used to assume "one account = one warehouse" resolves
	through this table instead -- see
	bsp_engineering.bsp_engineering.utils.warehouse_accounts.

	This patch creates the custom field, then migrates every existing
	Account.custom_warehouse link into a row on that warehouse's new table
	so already-configured sites keep working unchanged.
	"""
	frappe.reload_doc('bsp_engineering', 'doctype', 'warehouse_cash_account', force=True)
	_create_custom_field({
		'dt': 'Warehouse',
		'fieldname': 'custom_cash_accounts',
		'fieldtype': 'Table',
		'options': 'Warehouse Cash Account',
		'label': 'Cash / Bank Accounts',
		'insert_after': 'account',
		'description': (
			'Accounts used to identify this warehouse\'s cash movement in the '
			'BSP cash-summary and fund-transfer reports (Payment Entries and '
			'Journal Entries against any of these accounts count toward this '
			'warehouse).'
		),
	})
	_migrate_existing_account_links()


def _create_custom_field(field):
	name = f"{field['dt']}-{field['fieldname']}"
	if frappe.db.exists('Custom Field', name):
		return
	frappe.get_doc({'doctype': 'Custom Field', **field}).insert(ignore_permissions=True)


def _migrate_existing_account_links():
	if not frappe.db.has_column('Account', 'custom_warehouse'):
		return

	linked_accounts = frappe.get_all(
		'Account',
		filters={'custom_warehouse': ['is', 'set']},
		fields=['name', 'custom_warehouse'],
	)
	for row in linked_accounts:
		if not row.custom_warehouse:
			continue
		already_present = frappe.db.exists(
			'Warehouse Cash Account',
			{'parent': row.custom_warehouse, 'parenttype': 'Warehouse', 'account': row.name},
		)
		if already_present:
			continue
		warehouse = frappe.get_doc('Warehouse', row.custom_warehouse)
		warehouse.append('custom_cash_accounts', {'account': row.name})
		warehouse.save(ignore_permissions=True)
