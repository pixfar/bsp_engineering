from io import BytesIO

import frappe
from barcode import Code128, EAN13
from barcode.writer import ImageWriter
from frappe import _
from frappe.utils.file_manager import save_file
from stdnum import ean as stdnum_ean


def _iter_barcode_rows(doc_like):
    if doc_like is None:
        return []
    if isinstance(doc_like, dict):
        return doc_like.get('barcodes') or []
    return doc_like.get('barcodes') or []


def row_barcode(row):
    if isinstance(row, dict):
        return (row.get('barcode') or '').strip()
    return (getattr(row, 'barcode', None) or '').strip()


def _first_barcode(doc_like):
    for r in _iter_barcode_rows(doc_like):
        b = row_barcode(r)
        if b:
            return b
    return None


def _barcode_value_and_type(doc):
    raw = (doc.get('item_code') or doc.get('name') or '').strip()
    if not raw:
        frappe.throw(_('Item Code is required to generate a barcode.'))
    dup = frappe.db.sql(
        'SELECT parent FROM `tabItem Barcode` WHERE barcode = %s AND '
        'parent != %s LIMIT 1',
        (raw, doc.name),
    )
    if dup:
        frappe.throw(
            _('Item Code {0} is already stored as a barcode on Item {1}.').format(
                frappe.bold(raw),
                dup[0][0],
            ),
        )
    if len(raw) == 13 and raw.isdigit() and stdnum_ean.is_valid(raw):
        return raw, 'EAN'
    return raw, ''


def ensure_auto_barcode(doc, method=None):
    if not doc.get('custom_auto_generate_barcode'):
        return
    if not doc.get('stock_uom'):
        return
    if any(row_barcode(r) for r in _iter_barcode_rows(doc)):
        return
    value, barcode_type = _barcode_value_and_type(doc)
    row = {'barcode': value, 'uom': doc.stock_uom}
    if barcode_type:
        row['barcode_type'] = barcode_type
    doc.append('barcodes', row)


def _render_barcode_png(code: str) -> bytes:
    buf = BytesIO()
    writer = ImageWriter()
    if len(code) == 13 and code.isdigit() and stdnum_ean.is_valid(code):
        EAN13(code[:12], writer=writer).write(buf)
    else:
        Code128(code, writer=writer).write(buf)
    return buf.getvalue()


def _remove_barcode_image_files(item_name: str) -> None:
    for name in frappe.get_all(
        'File',
        filters={
            'attached_to_doctype': 'Item',
            'attached_to_name': item_name,
            'attached_to_field': 'custom_barcode_image',
        },
        pluck='name',
    ):
        frappe.delete_doc('File', name, force=True, ignore_permissions=True)


def sync_item_barcode_image(doc, method=None):
    if not doc.get('custom_auto_generate_barcode'):
        return
    if not frappe.get_meta('Item').get_field('custom_barcode_image'):
        return
    code = _first_barcode(doc)
    if not code:
        if doc.get('custom_barcode_image'):
            _remove_barcode_image_files(doc.name)
            frappe.db.set_value(
                'Item',
                doc.name,
                'custom_barcode_image',
                None,
                update_modified=False,
            )
            doc.set('custom_barcode_image', None)
        return
    prev = None
    if getattr(doc, '_doc_before_save', None):
        prev = _first_barcode(doc._doc_before_save)
    if code == prev and doc.get('custom_barcode_image'):
        return
    png = _render_barcode_png(code)
    fname = f'item-barcode-{frappe.generate_hash(length=8)}.png'
    _remove_barcode_image_files(doc.name)
    file_doc = save_file(
        fname,
        png,
        'Item',
        doc.name,
        is_private=0,
        df='custom_barcode_image',
    )
    frappe.db.set_value(
        'Item',
        doc.name,
        'custom_barcode_image',
        file_doc.file_url,
        update_modified=False,
    )
    doc.set('custom_barcode_image', file_doc.file_url)
