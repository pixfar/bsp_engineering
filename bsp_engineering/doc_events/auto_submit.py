import frappe


def auto_submit_after_save(doc, method):
	"""Auto-submit any submittable document immediately after it is saved in Draft state."""
	if doc.docstatus != 0:
		return

	if not frappe.get_meta(doc.doctype).is_submittable:
		return

	doc.submit()
