import frappe


def execute():
	"""custom_fund_transfer marks Payment Entries created by the Fund Transfer
	feature (Internal Transfer, company default cash account -> a showroom's
	cash account) so its list can filter to exactly those, independent of
	any other Internal Transfer entries that might touch the same accounts
	(e.g. BSP Daily Deposit's entries, which move money the other way).
	"""
	name = 'Payment Entry-custom_fund_transfer'
	if frappe.db.exists('Custom Field', name):
		return
	frappe.get_doc(
		{
			'doctype': 'Custom Field',
			'dt': 'Payment Entry',
			'fieldname': 'custom_fund_transfer',
			'fieldtype': 'Check',
			'label': 'Fund Transfer',
			'default': '0',
			'insert_after': 'reference_no',
			'read_only': 1,
			'no_copy': 1,
			'print_hide': 1,
		}
	).insert(ignore_permissions=True)
