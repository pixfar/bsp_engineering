"""After a Sales/Purchase Invoice return submits, restock via DN/PR return
when the source invoice moved stock through fulfillment notes instead of
update_stock on the invoice itself."""

import frappe


def restock_sales_invoice_return(doc, method=None):
	if not doc.get('is_return') or not doc.get('return_against'):
		return
	try:
		from posawesome.posawesome.api.invoice_processing.restock_on_return import (
			restock_sales_return,
		)

		source = frappe.get_doc('Sales Invoice', doc.return_against)
		restock_sales_return(source, doc)
	except Exception:
		frappe.log_error(
			title=f'DN restock failed for return {doc.name}',
			message=frappe.get_traceback(),
		)


def restock_purchase_invoice_return(doc, method=None):
	if not doc.get('is_return') or not doc.get('return_against'):
		return
	try:
		from posawesome.posawesome.api.invoice_processing.restock_on_return import (
			restock_purchase_return,
		)

		source = frappe.get_doc('Purchase Invoice', doc.return_against)
		restock_purchase_return(source, doc)
	except Exception:
		frappe.log_error(
			title=f'PR restock failed for return {doc.name}',
			message=frappe.get_traceback(),
		)
