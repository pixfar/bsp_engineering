import frappe
from frappe.utils import flt


def execute():
    """Backfill custom_delivery_status for all submitted Purchase Invoices."""
    if not frappe.db.has_column("Purchase Invoice", "custom_delivery_status"):
        return

    invoices = frappe.db.get_all(
        "Purchase Invoice",
        filters={"docstatus": 1},
        fields=["name", "update_stock", "per_received"],
    )

    for inv in invoices:
        if inv.update_stock or flt(inv.per_received) >= 100:
            status = "Fully Received"
        elif flt(inv.per_received) > 0:
            status = "Partially Received"
        else:
            status = "Not Received"

        frappe.db.set_value(
            "Purchase Invoice",
            inv.name,
            "custom_delivery_status",
            status,
            update_modified=False,
        )

    frappe.db.commit()
