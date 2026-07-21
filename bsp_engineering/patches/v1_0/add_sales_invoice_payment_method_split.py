import frappe


def execute():
	_create_custom_field(
		{
			'dt': 'Sales Invoice',
			'fieldname': 'custom_payment_method_split',
			'fieldtype': 'Table',
			'options': 'Sales Invoice Payment Split',
			'label': 'Payment Method Split',
			'read_only': 1,
			# NOTE: must NOT be inside `payments_section` (insert_after="payments"
			# would put it there) — that whole section has its own
			# depends_on: eval:doc.is_pos===1, so it's hidden exactly when this
			# field needs to be visible (is_pos=0). section_break_84 (right
			# after "payments") has no depends_on, so anchor there instead.
			'insert_after': 'section_break_84',
			'depends_on': 'eval:!doc.is_pos',
			'print_hide': 1,
		}
	)


def _create_custom_field(field):
	name = f"{field['dt']}-{field['fieldname']}"
	if frappe.db.exists('Custom Field', name):
		return
	frappe.get_doc({'doctype': 'Custom Field', **field}).insert(ignore_permissions=True)
