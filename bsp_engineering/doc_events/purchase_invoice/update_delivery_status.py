import frappe
from frappe.utils import flt


def update_delivery_status(doc, method=None):
    if doc.update_stock or flt(doc.per_received) >= 100:
        status = "Fully Received"
    elif flt(doc.per_received) > 0:
        status = "Partially Received"
    else:
        status = "Not Received"

    doc.db_set("custom_delivery_status", status, update_modified=False)
