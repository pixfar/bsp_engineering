import frappe
from frappe import _
from frappe.utils import flt


def on_update(doc, method):
    """Auto-create Work Orders the first time a Production Plan is saved with items."""
    if doc.docstatus != 0:
        return
    if not doc.get('po_items'):
        return
    # Idempotent: skip if Work Orders already exist for this Production Plan
    if frappe.db.exists('Work Order', {'production_plan': doc.name}):
        return
    doc.make_work_order()


def on_submit(doc, method):
    """Fires when PP workflow transitions to Completed (docstatus 0 → 1).
    Creates Stock Entries for all linked Work Orders and marks them Completed."""
    _complete_all_work_orders(doc)


def _complete_all_work_orders(doc):
    work_orders = frappe.get_all(
        'Work Order',
        filters={
            'production_plan': doc.name,
            'docstatus': 1,
            'status': ['not in', ['Completed', 'Closed']],
        },
        fields=['name', 'skip_transfer', 'qty', 'produced_qty'],
    )

    completed = 0
    for wo in work_orders:
        remaining_qty = flt(wo.qty) - flt(wo.produced_qty)
        if remaining_qty <= 0:
            completed += 1
            continue

        try:
            wo_doc = frappe.get_doc('Work Order', wo.name)

            if not wo_doc.skip_transfer:
                _create_and_submit_stock_entry(wo.name, 'Material Transfer for Manufacture', remaining_qty)

            _create_and_submit_stock_entry(wo.name, 'Manufacture', remaining_qty)
            completed += 1

        except Exception:
            frappe.log_error(
                title=f'Auto-complete Work Order {wo.name} failed',
                message=frappe.get_traceback(),
            )
            frappe.msgprint(
                _("Could not complete Work Order {0}. Check Error Log for details.").format(wo.name),
                indicator='orange',
            )

    if completed:
        frappe.msgprint(
            _("{0} Work Order(s) completed.").format(completed),
            indicator='green',
            alert=True,
        )


def _create_and_submit_stock_entry(wo_name, purpose, qty):
    from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

    # Remove orphaned draft SEs for the same WO + purpose — ERPNext blocks new entries
    # while any non-cancelled SE for the same WO exists with docstatus=0.
    orphans = frappe.get_all(
        'Stock Entry',
        filters={'work_order': wo_name, 'stock_entry_type': purpose, 'docstatus': 0},
        pluck='name',
    )
    for orphan in orphans:
        frappe.delete_doc('Stock Entry', orphan, force=True, ignore_permissions=True)

    se_data = make_stock_entry(wo_name, purpose, qty)
    se_data.pop('name', None)
    se = frappe.get_doc(se_data)
    se.insert(ignore_permissions=True)
    # Submit directly, bypassing any active workflow on Stock Entry (e.g. BSP Material Transfer Receipt)
    # which would otherwise block submission of manufacturing-related entries.
    se.flags.ignore_permissions = True
    se.flags.ignore_workflow = True
    se.submit()
