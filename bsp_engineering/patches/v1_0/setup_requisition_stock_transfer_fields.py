import frappe


def execute():
	_create_custom_field(
		{
			'dt': 'Stock Entry',
			'fieldname': 'custom_requisition',
			'fieldtype': 'Link',
			'label': 'Requisition',
			'options': 'Requisition',
			'read_only': 1,
			'insert_after': 'stock_entry_type',
			'in_standard_filter': 1,
		}
	)
	_create_custom_field(
		{
			'dt': 'Stock Entry Detail',
			'fieldname': 'custom_requisition_item',
			'fieldtype': 'Data',
			'label': 'Requisition Item',
			'hidden': 1,
			'read_only': 1,
			'insert_after': 'item_code',
		}
	)


def _create_custom_field(field):
	name = f"{field['dt']}-{field['fieldname']}"
	if frappe.db.exists('Custom Field', name):
		return
	frappe.get_doc({'doctype': 'Custom Field', **field}).insert(
		ignore_permissions=True
	)
