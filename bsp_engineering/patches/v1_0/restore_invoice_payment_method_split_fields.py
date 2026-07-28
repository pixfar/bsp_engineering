import frappe


def execute():
	"""Recreate custom_payment_method_split on Sales/Purchase Invoice.

	The original patches that created these fields already ran (see
	add_sales_invoice_payment_method_split / add_purchase_invoice_payment_method_split),
	so a plain `bench migrate` won't recreate them if they were deleted by
	hand later -- this patch re-adds them whenever they're missing.
	"""
	_create_custom_field(
		{
			'dt': 'Sales Invoice',
			'fieldname': 'custom_payment_method_split',
			'fieldtype': 'Table',
			'options': 'Sales Invoice Payment Split',
			'label': 'Payment Method Split',
			'read_only': 1,
			'insert_after': 'section_break_84',
			'depends_on': 'eval:!doc.is_pos',
			'print_hide': 1,
		}
	)
	_create_custom_field(
		{
			'dt': 'Purchase Invoice',
			'fieldname': 'custom_payment_method_split',
			'fieldtype': 'Table',
			'options': 'Purchase Invoice Payment Split',
			'label': 'Payment Method Split',
			'read_only': 1,
			'insert_after': 'advances',
			'print_hide': 1,
		}
	)


def _create_custom_field(field):
	name = f"{field['dt']}-{field['fieldname']}"
	if frappe.db.exists('Custom Field', name):
		return
	frappe.get_doc({'doctype': 'Custom Field', **field}).insert(ignore_permissions=True)
