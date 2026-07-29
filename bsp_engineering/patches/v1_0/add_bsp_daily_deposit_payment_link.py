import frappe


def execute():
	"""custom_bsp_daily_deposit on Payment Entry: the reverse-lookup field the
	BSP Daily Deposit dashboard connection uses to show its linked Payment
	Entry. Internal Transfer entries clear the `references` child table on
	every save (see PaymentEntry.set_missing_values), so a Dynamic Link
	reference can't be used for this -- a plain Link field is required.
	"""
	name = 'Payment Entry-custom_bsp_daily_deposit'
	if frappe.db.exists('Custom Field', name):
		return
	frappe.get_doc(
		{
			'doctype': 'Custom Field',
			'dt': 'Payment Entry',
			'fieldname': 'custom_bsp_daily_deposit',
			'fieldtype': 'Link',
			'options': 'BSP Daily Deposit',
			'label': 'BSP Daily Deposit',
			'insert_after': 'reference_no',
			'read_only': 1,
			'no_copy': 1,
			'print_hide': 1,
		}
	).insert(ignore_permissions=True)
