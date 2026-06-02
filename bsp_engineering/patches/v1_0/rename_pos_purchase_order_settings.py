import frappe

FIELD_RENAMES = {
	'POS Profile-posa_allow_purchase_order': {
		'label': 'Allow Purchase Invoice',
		'description': 'Allow creating Purchase Invoices from POS Awesome',
	},
	'POS Profile-posa_allow_purchase_receipt': {
		'label': 'Allow Receive Stock from POS',
		'depends_on': 'eval:doc.posa_allow_purchase_invoice||doc.posa_allow_purchase_order',
	},
	'POS Profile-posa_allow_create_purchase_items': {
		'depends_on': 'eval:doc.posa_allow_purchase_invoice||doc.posa_allow_purchase_order',
	},
	'POS Profile-posa_allow_create_purchase_suppliers': {
		'depends_on': 'eval:doc.posa_allow_purchase_invoice||doc.posa_allow_purchase_order',
	},
}


def execute():
	_ensure_purchase_invoice_profile_field()
	_update_custom_field_metadata()
	_copy_profile_flag_values()


def _ensure_purchase_invoice_profile_field():
	fieldname = 'POS Profile-posa_allow_purchase_invoice'
	if frappe.db.exists('Custom Field', fieldname):
		return

	order_field = frappe.get_doc('Custom Field', 'POS Profile-posa_allow_purchase_order')
	frappe.get_doc(
		{
			'doctype': 'Custom Field',
			'dt': 'POS Profile',
			'fieldname': 'posa_allow_purchase_invoice',
			'label': 'Allow Purchase Invoice',
			'fieldtype': 'Check',
			'insert_after': order_field.fieldname,
			'default': order_field.default or '0',
			'description': 'Allow creating Purchase Invoices from POS Awesome',
		}
	).insert(ignore_permissions=True)


def _update_custom_field_metadata():
	for name, values in FIELD_RENAMES.items():
		if not frappe.db.exists('Custom Field', name):
			continue
		frappe.db.set_value('Custom Field', name, values, update_modified=False)


def _copy_profile_flag_values():
	if not frappe.db.has_column('POS Profile', 'posa_allow_purchase_invoice'):
		return

	frappe.db.sql(
		"""
		UPDATE `tabPOS Profile`
		SET posa_allow_purchase_invoice = posa_allow_purchase_order
		WHERE IFNULL(posa_allow_purchase_order, 0) = 1
			AND IFNULL(posa_allow_purchase_invoice, 0) = 0
		"""
	)
