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

	# Frappe's insert() sets __islocal=True at the start and only deletes it AFTER
	# run_post_save_methods() completes. Since on_update fires inside run_post_save_methods,
	# calling submit() → save() → _save() here would see __islocal=True and try a second
	# insert(), hitting a DuplicateEntryError. Clear it first so _save() takes the UPDATE path.
	if hasattr(doc, '__islocal'):
		delattr(doc, '__islocal')

	doc.submit()
