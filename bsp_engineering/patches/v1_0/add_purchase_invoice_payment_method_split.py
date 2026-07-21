import frappe


def execute():
	_create_custom_field(
		{
			'dt': 'Purchase Invoice',
			'fieldname': 'custom_payment_method_split',
			'fieldtype': 'Table',
			'options': 'Purchase Invoice Payment Split',
			'label': 'Payment Method Split',
			'read_only': 1,
			# advances_section has no depends_on, so a field anchored here stays
			# visible unconditionally (see add_sales_invoice_payment_method_split.py
			# for why this matters: a field placed inside a conditionally-hidden
			# section is invisible even with its own depends_on).
			'insert_after': 'advances',
			'print_hide': 1,
		}
	)


def _create_custom_field(field):
	name = f"{field['dt']}-{field['fieldname']}"
	if frappe.db.exists('Custom Field', name):
		return
	frappe.get_doc({'doctype': 'Custom Field', **field}).insert(ignore_permissions=True)
