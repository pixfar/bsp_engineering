import frappe
from frappe import _


def guard_confirm_receipt(doc, method=None):
	"""Block the 'Confirm Receipt' workflow action for anyone other than the requisition requester."""
	if getattr(doc, 'workflow_action', None) != 'Confirm Receipt':
		return

	requisition = doc.get('custom_requisition')
	if not requisition:
		return

	requested_by = frappe.db.get_value('Requisition', requisition, 'requested_by')
	if not requested_by:
		return

	if frappe.session.user != requested_by:
		frappe.throw(
			_('Only {0} (the person who submitted this Requisition) can confirm receipt.').format(
				frappe.bold(requested_by)
			),
			title=_('Not Allowed'),
			exc=frappe.PermissionError,
		)
