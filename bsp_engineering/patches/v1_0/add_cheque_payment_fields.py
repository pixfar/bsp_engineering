import frappe

# Cheque details captured by the POS Supplier Payment screen's "Bank / Cheque
# Payment" section. The cheque number itself goes in the standard
# reference_no field; these hold the rest.
FIELDS = [
	{
		'fieldname': 'custom_cheque_bank',
		'fieldtype': 'Link',
		'options': 'Bank',
		'label': 'Cheque Bank',
		'insert_after': 'reference_date',
	},
	{
		'fieldname': 'custom_payee',
		'fieldtype': 'Link',
		'options': 'User',
		'label': 'Payee',
		'insert_after': 'custom_cheque_bank',
	},
	{
		'fieldname': 'custom_cheque_image',
		'fieldtype': 'Attach',
		'label': 'Cheque Image',
		'insert_after': 'custom_payee',
	},
]


def execute():
	for field in FIELDS:
		name = f"Payment Entry-{field['fieldname']}"
		if frappe.db.exists('Custom Field', name):
			continue
		frappe.get_doc({'doctype': 'Custom Field', 'dt': 'Payment Entry', 'no_copy': 1, **field}).insert(
			ignore_permissions=True
		)
