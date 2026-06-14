import frappe


def auto_submit_after_save(doc, method):
	"""Auto-submit any submittable document immediately after it is saved in Draft state.
	Skipped for doctypes that have an active Workflow — the workflow controls submission."""
	if doc.docstatus != 0:
		return

	if not frappe.get_meta(doc.doctype).is_submittable:
		return

	if frappe.db.exists('Workflow', {'document_type': doc.doctype, 'is_active': 1}):
		return

	doc.submit()
