import frappe
from frappe import _


def get_data(data=None):
	"""Dashboard for BSP Daily Deposit connections (its Payment Entry)."""
	if data is None:
		data = frappe._dict()
	else:
		data = frappe._dict(data)

	if not data.get('fieldname'):
		data.fieldname = 'custom_bsp_daily_deposit'

	if not data.get('transactions'):
		data.transactions = []

	has_payment_entry = any(
		'Payment Entry' in (group.get('items') or [])
		for group in data.transactions
	)
	if not has_payment_entry:
		data.transactions.append(
			{
				'label': _('Payments'),
				'items': ['Payment Entry'],
			}
		)

	return data
