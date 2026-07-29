import frappe

# Doctypes that manage their own multi-step submission flow in application code
# (e.g. posawesome's invoice_processing: save a draft, finalize payments/taxes,
# THEN submit). Auto-submitting them the instant they're saved as a draft races
# with that code — it ends up submitting the invoice before the caller is done
# with it, so the caller's own later `.submit()`/field updates fail with
# "Cannot Update After Submit", even though the document was in fact submitted.
AUTO_SUBMIT_EXCLUDED_DOCTYPES = frozenset(
	{
		'Sales Invoice',
		'POS Invoice',
		'Purchase Invoice',
		# Same race as above: every Payment Entry creation path in this app
		# (Sales/Purchase Invoice payment splits, standalone Customer/Supplier
		# payments, Expense Claim reimbursements) does insert() then submit().
		# Auto-submitting inside insert() leaves the caller's later submit()
		# call operating on a stale in-memory doc, which throws
		# UpdateAfterSubmitError as soon as the Payment Entry has any
		# `references` rows. Also restores normal Draft-then-Submit behavior
		# for Payment Entries created by hand in the Desk UI.
		'Payment Entry',
	}
)


def auto_submit_after_save(doc, method):
	"""Auto-submit any submittable document immediately after it is saved in Draft state.
	Skipped for doctypes that have an active Workflow — the workflow controls submission."""
	if doc.docstatus != 0:
		return

	if doc.doctype in AUTO_SUBMIT_EXCLUDED_DOCTYPES:
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
