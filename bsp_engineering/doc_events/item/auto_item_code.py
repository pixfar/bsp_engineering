"""Automatic Item Code for new Items.

BSP item codes are 8-digit, zero-padded numbers from one running internal
sequence (00000001, 00000002, ...). Codes at or above EXTERNAL_CODE_START
(e.g. RFL Pipe's 00083930, Molding Material's 00010701) are imported
supplier/external codes and are not part of that sequence, so they are
ignored when working out the next one.

The Item form and quick-entry dialog (public/js/item_auto_code.js) prefill
the next code but leave it editable. They also send the value they filled in
as `__bsp_auto_code`: if the user kept it and someone else saved that same
code first, before_insert moves this Item on to the next free code instead
of failing on a duplicate. A code the user typed themselves is never changed.
"""

import frappe
from frappe import _

CODE_WIDTH = 8
EXTERNAL_CODE_START = 10000


def get_next_code():
	last = frappe.db.sql(
		"""
		SELECT MAX(CAST(name AS UNSIGNED)) FROM `tabItem`
		WHERE name REGEXP %(pattern)s AND CAST(name AS UNSIGNED) < %(limit)s
		""",
		{'pattern': f'^[0-9]{{{CODE_WIDTH}}}$', 'limit': EXTERNAL_CODE_START},
	)[0][0]
	number = int(last or 0) + 1
	# Once the internal sequence reaches the external range, step over any
	# code that is already taken.
	while frappe.db.exists('Item', str(number).zfill(CODE_WIDTH)):
		number += 1
	return str(number).zfill(CODE_WIDTH)


@frappe.whitelist()
def get_next_item_code():
	if not frappe.has_permission('Item', 'create'):
		frappe.throw(_('You are not permitted to create Items.'), frappe.PermissionError)
	return get_next_code()


def set_auto_item_code(doc, method=None):
	"""before_insert: fill a missing code (API / Data Import / POS), and move an
	auto-filled code on if it was taken in the meantime."""
	if doc.variant_of:
		return
	if not doc.item_code:
		doc.item_code = get_next_code()
		return

	auto_code = doc.get('__bsp_auto_code')
	if auto_code and doc.item_code == auto_code and frappe.db.exists('Item', doc.item_code):
		taken = doc.item_code
		doc.item_code = get_next_code()
		frappe.msgprint(
			_('Item Code {0} was just used by another item, so this item was saved as {1}.').format(
				taken, doc.item_code
			),
			alert=True,
		)
