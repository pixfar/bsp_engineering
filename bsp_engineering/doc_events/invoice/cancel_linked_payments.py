import frappe
from frappe import _
from frappe.utils import flt


def cancel_linked_payment_entries(doc, method=None):
	"""Cancel Payment Entries allocated against this Sales or Purchase Invoice."""
	if getattr(doc, 'is_consolidated', False):
		return

	payment_entries = _get_linked_payment_entries(doc.doctype, doc.name)
	if not payment_entries:
		return

	cancelled = []
	failed = []

	for pe_name in payment_entries:
		try:
			_cancel_payment_entry_for_invoice(pe_name, doc.doctype, doc.name)
			cancelled.append(pe_name)
		except Exception as error:
			frappe.log_error(
				frappe.get_traceback(),
				(
					f'Payment Entry cancellation failed for {doc.doctype} '
					f'{doc.name} ({pe_name})'
				),
			)
			failed.append(f'{pe_name}: {error}')

	if failed:
		frappe.throw(
			_('Could not cancel linked Payment Entries:<br>{0}').format(
				'<br>'.join(failed)
			),
			title=_('Payment Cancellation Failed'),
		)

	if cancelled and frappe.db.has_column(doc.doctype, 'custom_is_paid'):
		doc.db_set('custom_is_paid', 0, update_modified=False)


def _get_linked_payment_entries(reference_doctype, reference_name):
	return frappe.db.sql_list(
		"""
		SELECT DISTINCT pe.name
		FROM `tabPayment Entry` pe
		INNER JOIN `tabPayment Entry Reference` per
			ON per.parent = pe.name
		WHERE pe.docstatus = 1
			AND per.reference_doctype = %s
			AND per.reference_name = %s
		ORDER BY pe.creation DESC
		""",
		(reference_doctype, reference_name),
	)


def _cancel_payment_entry_for_invoice(pe_name, reference_doctype, reference_name):
	pe = frappe.get_doc('Payment Entry', pe_name)
	if pe.docstatus != 1:
		return

	if not _payment_entry_allocated_only_to_invoice(
		pe, reference_doctype, reference_name
	):
		frappe.throw(
			_(
				'Payment Entry {0} is allocated to other documents. '
				'Cancel or amend it manually before cancelling this invoice.'
			).format(pe_name)
		)

	pe.flags.ignore_permissions = True
	pe.cancel()


def _payment_entry_allocated_only_to_invoice(pe, reference_doctype, reference_name):
	allocated_refs = [
		row
		for row in pe.references
		if flt(row.allocated_amount) > 0
	]
	if not allocated_refs:
		return True

	for row in allocated_refs:
		if (
			row.reference_doctype != reference_doctype
			or row.reference_name != reference_name
		):
			return False
	return True
