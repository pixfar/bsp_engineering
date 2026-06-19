import frappe

STANDARD_NAMING_SERIES = 'ACC-SINV-.YYYY.-'
RETURN_NAMING_SERIES = 'ACC-SIN-RET.YYYY.-'
NAMING_SERIES_OPTIONS = f'{STANDARD_NAMING_SERIES}\n{RETURN_NAMING_SERIES}'


def execute():
	_update_naming_series_options()
	_update_draft_return_invoices()


def _update_naming_series_options():
	property_setter_name = 'Sales Invoice-naming_series-options'
	if frappe.db.exists('Property Setter', property_setter_name):
		frappe.db.set_value(
			'Property Setter',
			property_setter_name,
			'value',
			NAMING_SERIES_OPTIONS,
		)
		return

	frappe.get_doc(
		{
			'doctype': 'Property Setter',
			'name': property_setter_name,
			'doc_type': 'Sales Invoice',
			'doctype_or_field': 'DocField',
			'field_name': 'naming_series',
			'property': 'options',
			'property_type': 'Text',
			'value': NAMING_SERIES_OPTIONS,
		}
	).insert(ignore_permissions=True)


def _update_draft_return_invoices():
	frappe.db.sql(
		"""
		UPDATE `tabSales Invoice`
		SET naming_series = %s
		WHERE docstatus = 0
			AND is_return = 1
			AND naming_series != %s
		""",
		(RETURN_NAMING_SERIES, RETURN_NAMING_SERIES),
	)
