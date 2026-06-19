STANDARD_NAMING_SERIES = 'ACC-SINV-.YYYY.-'
RETURN_NAMING_SERIES = 'ACC-SIN-RET.YYYY.-'
LEGACY_RETURN_NAMING_SERIES = 'ACC-SINV-RET-.YYYY.-'


def enforce_return_naming_series(doc, method=None):
	if doc.is_return:
		if doc.naming_series != RETURN_NAMING_SERIES:
			doc.naming_series = RETURN_NAMING_SERIES
		if doc.get('custom_is_paid'):
			doc.custom_is_paid = 0
		return

	if doc.naming_series in (RETURN_NAMING_SERIES, LEGACY_RETURN_NAMING_SERIES):
		doc.naming_series = STANDARD_NAMING_SERIES
