import frappe
from frappe import _


def get_data(data=None):
	"""Dashboard for Requisition connections (Stock Entry transfers)."""
	if data is None:
		data = frappe._dict()
	else:
		data = frappe._dict(data)

	if not data.get('fieldname'):
		data.fieldname = 'custom_requisition'

	if not data.get('transactions'):
		data.transactions = []

	has_stock_entry = any(
		'Stock Entry' in (group.get('items') or [])
		for group in data.transactions
	)
	if not has_stock_entry:
		data.transactions.append(
			{
				'label': _('Stock Transfer'),
				'items': ['Stock Entry'],
			}
		)

	return data
