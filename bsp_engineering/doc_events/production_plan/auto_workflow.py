import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


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
    """Raises on the first Work Order that can't be completed (e.g. insufficient
    stock) instead of swallowing it — letting the Production Plan's own submit
    fail too, so its workflow_state never gets set to Production Complete while a
    linked Work Order is actually still unfinished. Frappe rolls back the whole
    request on an unhandled exception, so no half-applied state is left behind."""
    work_orders = frappe.get_all(
        'Work Order',
        filters={
            'production_plan': doc.name,
            'docstatus': 1,
            'status': ['not in', ['Completed', 'Closed']],
        },
        fields=['name', 'skip_transfer', 'qty', 'produced_qty'],
    )

    _ensure_raw_materials_in_stock(work_orders)

    completed = 0
    for wo in work_orders:
        remaining_qty = flt(wo.qty) - flt(wo.produced_qty)
        if remaining_qty <= 0:
            completed += 1
            continue

        try:
            wo_doc = frappe.get_doc('Work Order', wo.name)

            if not wo_doc.skip_transfer:
                _create_and_submit_stock_entry(
                    wo.name, 'Material Transfer for Manufacture', remaining_qty, doc.posting_date
                )

            _create_and_submit_stock_entry(wo.name, 'Manufacture', remaining_qty, doc.posting_date)
            completed += 1

        except Exception as e:
            frappe.log_error(
                title=f'Auto-complete Work Order {wo.name} failed',
                message=frappe.get_traceback(),
            )
            frappe.throw(
                _("Could not complete Work Order {0}: {1}").format(wo.name, str(e)),
                title=_('Production Not Complete'),
            )

    if completed:
        frappe.msgprint(
            _("{0} Work Order(s) completed.").format(completed),
            indicator='green',
            alert=True,
        )


def _ensure_raw_materials_in_stock(work_orders):
    """Raise once with every raw material that is short, before any Stock
    Entry is made. Without this, ERPNext's own stock check stops at the first
    short item of the first Work Order, so the user had to fix shortages one
    at a time, resubmitting after each.

    Needs are summed per item and source warehouse across all Work Orders, in
    the same quantities _create_and_submit_stock_entry() will move: the
    pending transfer qty when material is transferred to WIP first, otherwise
    the remaining share of each required item. Items allowed to go negative
    (Stock Settings or the Item) are skipped, as ERPNext would."""
    needed = {}  # (item_code, warehouse) -> qty
    item_names = {}
    for wo in work_orders:
        remaining_qty = flt(wo.qty) - flt(wo.produced_qty)
        if remaining_qty <= 0:
            continue
        wo_doc = frappe.get_doc('Work Order', wo.name)
        ratio = remaining_qty / flt(wo_doc.qty) if flt(wo_doc.qty) else 0
        for row in wo_doc.required_items:
            if not row.include_item_in_manufacturing:
                continue
            if wo_doc.skip_transfer:
                qty = flt(row.required_qty) * ratio
                warehouse = (
                    wo_doc.wip_warehouse
                    if wo_doc.from_wip_warehouse
                    else row.source_warehouse or wo_doc.source_warehouse
                )
            else:
                qty = flt(row.required_qty) - flt(row.transferred_qty)
                warehouse = row.source_warehouse or wo_doc.source_warehouse
            if qty <= 0 or not warehouse:
                continue
            key = (row.item_code, warehouse)
            needed[key] = needed.get(key, 0) + qty
            item_names[row.item_code] = row.item_name

    if not needed or frappe.db.get_single_value('Stock Settings', 'allow_negative_stock'):
        return

    item_codes = list({code for code, _wh in needed})
    negative_ok = set(
        frappe.get_all(
            'Item',
            filters={'name': ['in', item_codes], 'allow_negative_stock': 1},
            pluck='name',
        )
    )
    available = {
        (b.item_code, b.warehouse): flt(b.actual_qty)
        for b in frappe.get_all(
            'Bin',
            filters={
                'item_code': ['in', item_codes],
                'warehouse': ['in', list({wh for _code, wh in needed})],
            },
            fields=['item_code', 'warehouse', 'actual_qty'],
        )
    }

    shortages = []
    for (item_code, warehouse), qty in sorted(needed.items()):
        if item_code in negative_ok:
            continue
        in_stock = available.get((item_code, warehouse), 0)
        if in_stock + 1e-9 < qty:
            shortages.append((item_code, warehouse, qty, in_stock))
    if not shortages:
        return

    esc = frappe.utils.escape_html
    rows = ''.join(
        '<tr><td>{0}</td><td>{1}</td><td>{2}</td>'
        '<td class="text-right">{3}</td><td class="text-right">{4}</td>'
        '<td class="text-right"><b>{5}</b></td></tr>'.format(
            esc(item_code),
            esc(item_names.get(item_code) or ''),
            esc(warehouse),
            frappe.format(qty, 'Float'),
            frappe.format(in_stock, 'Float'),
            frappe.format(qty - in_stock, 'Float'),
        )
        for item_code, warehouse, qty, in_stock in shortages
    )
    frappe.throw(
        _('{0} raw material(s) are short. Add stock for all of them, then mark the plan complete again.').format(
            len(shortages)
        )
        + '<table class="table table-bordered table-sm mt-3"><thead><tr>'
        + ''.join(
            f'<th{cls}>{_(label)}</th>'
            for label, cls in [
                ('Item Code', ''),
                ('Item Name', ''),
                ('Warehouse', ''),
                ('Required', ' class="text-right"'),
                ('In Stock', ' class="text-right"'),
                ('Short', ' class="text-right"'),
            ]
        )
        + f'</tr></thead><tbody>{rows}</tbody></table>',
        title=_('Insufficient Stock'),
        exc=frappe.ValidationError,
    )


def _create_and_submit_stock_entry(wo_name, purpose, qty, posting_date=None):
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
    if purpose == 'Manufacture':
        _use_work_order_raw_materials(se, wo_name, qty)
    # A backdated Production Plan must post its stock movements on the plan's
    # own date, not today. Without set_posting_time, Stock Entry.validate()
    # resets posting_date to now.
    if posting_date and getdate(posting_date) != getdate(nowdate()):
        se.set_posting_time = 1
        se.posting_date = posting_date
    se.insert(ignore_permissions=True)
    # Submit directly, bypassing any active workflow on Stock Entry (e.g. BSP Material Transfer Receipt)
    # which would otherwise block submission of manufacturing-related entries.
    se.flags.ignore_permissions = True
    se.flags.ignore_workflow = True
    se.submit()


def _use_work_order_raw_materials(se, wo_name, qty):
    """With backflush_raw_materials_based_on = "BOM", ERPNext builds the
    Manufacture entry's raw material rows from the BOM, ignoring the Work
    Order's own required_items. A plan created with edited raw materials
    (see overrides/production_plan.apply_raw_material_overrides) has a Work
    Order whose required_items differ from the BOM -- consume those instead.
    Leaves the entry untouched when they already match (the normal case)."""
    wo = frappe.get_doc('Work Order', wo_name)
    if not flt(wo.qty):
        return

    ratio = flt(qty) / flt(wo.qty)
    expected = {}
    for row in wo.required_items:
        # Same filter ERPNext's get_bom_items_as_dict applies.
        if row.include_item_in_manufacturing:
            expected[row.item_code] = expected.get(row.item_code, 0) + flt(row.required_qty) * ratio

    raw_rows = [row for row in se.items if row.s_warehouse and not row.t_warehouse]
    current = {}
    for row in raw_rows:
        current[row.item_code] = current.get(row.item_code, 0) + flt(row.qty)
    if set(current) == set(expected) and all(
        abs(current[code] - expected[code]) < 1e-6 for code in expected
    ):
        return

    from_warehouse = (
        wo.wip_warehouse
        if not wo.skip_transfer or wo.from_wip_warehouse
        else None
    )
    template = raw_rows[0].as_dict() if raw_rows else {}
    se.items = [row for row in se.items if row not in raw_rows]
    required_by_code = {row.item_code: row for row in wo.required_items}
    for item_code, required_qty in expected.items():
        if required_qty <= 0:
            continue
        wo_row = required_by_code[item_code]
        se.append(
            'items',
            {
                'item_code': item_code,
                'item_name': wo_row.item_name,
                'description': wo_row.description,
                'qty': required_qty,
                'transfer_qty': required_qty,
                'uom': wo_row.stock_uom,
                'stock_uom': wo_row.stock_uom,
                'conversion_factor': 1,
                's_warehouse': from_warehouse or wo_row.source_warehouse or template.get('s_warehouse'),
                'expense_account': template.get('expense_account'),
                'cost_center': template.get('cost_center'),
            },
        )
    # Raw materials first, finished good last -- same order ERPNext uses.
    se.items = sorted(se.items, key=lambda row: 1 if row.t_warehouse else 0)
    for idx, row in enumerate(se.items, start=1):
        row.idx = idx
