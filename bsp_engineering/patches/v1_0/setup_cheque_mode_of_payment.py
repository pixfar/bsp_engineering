import frappe


def execute():
	"""The POS Supplier Payment screen pays cheques under the "Cheque" Mode of
	Payment. ERPNext refuses a Mode of Payment with no default account, so
	give it each company's Default Cash Account -- same as Bank Draft. The
	money itself still leaves from the showroom / selected cash account
	(see posawesome payment_processing.creation.create_payment_entry)."""
	if not frappe.db.exists('Mode of Payment', 'Cheque'):
		frappe.get_doc({'doctype': 'Mode of Payment', 'mode_of_payment': 'Cheque', 'type': 'Bank', 'enabled': 1}).insert(
			ignore_permissions=True
		)

	mop = frappe.get_doc('Mode of Payment', 'Cheque')
	if not mop.enabled:
		mop.enabled = 1
	existing = {row.company for row in mop.accounts}
	changed = False
	for company in frappe.get_all('Company', fields=['name', 'default_cash_account']):
		if company.name in existing or not company.default_cash_account:
			continue
		mop.append('accounts', {'company': company.name, 'default_account': company.default_cash_account})
		changed = True
	if changed or mop.has_value_changed('enabled'):
		mop.save(ignore_permissions=True)
