"""Owner-only visibility for Sales/Purchase Invoice desk list views.

Users without the BSP Admin or System Manager role may only see invoices
they created themselves; privileged users see everything, same as before.
"""

import frappe

PRIVILEGED_ROLES = {'BSP Admin', 'System Manager'}


def is_privileged_invoice_viewer(user=None):
	user = user or frappe.session.user
	if user == 'Administrator':
		return True
	return bool(PRIVILEGED_ROLES & set(frappe.get_roles(user)))


def _owner_only_condition(doctype, user=None):
	user = user or frappe.session.user
	if is_privileged_invoice_viewer(user):
		return ''
	return f'`tab{doctype}`.owner = {frappe.db.escape(user)}'


def _has_owner_permission(doc, user=None):
	user = user or frappe.session.user
	if is_privileged_invoice_viewer(user):
		return None
	return doc.owner == user


def get_sales_invoice_permission_query(user, doctype=None):
	return _owner_only_condition('Sales Invoice', user)


def get_purchase_invoice_permission_query(user, doctype=None):
	return _owner_only_condition('Purchase Invoice', user)


def has_sales_invoice_permission(doc, ptype='read', user=None, debug=False):
	return _has_owner_permission(doc, user)


def has_purchase_invoice_permission(doc, ptype='read', user=None, debug=False):
	return _has_owner_permission(doc, user)
