import frappe
from frappe.utils import flt

CANCELLED_STATUS = 'Cancelled'


def update_delivery_status(doc, method=None):
	if doc.docstatus == 2:
		return

	if doc.update_stock or flt(doc.per_received) >= 100:
		status = 'Fully Received'
	elif flt(doc.per_received) > 0:
		status = 'Partially Received'
	else:
		status = 'Not Received'

	_set_delivery_status(doc, status)


def reset_delivery_status_on_cancel(doc, method=None):
	_set_delivery_status(doc, CANCELLED_STATUS)


def _set_delivery_status(doc, status):
	if not frappe.db.has_column(doc.doctype, 'custom_delivery_status'):
		return
	doc.db_set('custom_delivery_status', status, update_modified=False)
