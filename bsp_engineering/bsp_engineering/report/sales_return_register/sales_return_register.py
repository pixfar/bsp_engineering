import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": _("Invoice"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 160,
        },
        {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("Customer"),
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 140,
        },
        {
            "label": _("Customer Name"),
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": _("Customer Group"),
            "fieldname": "customer_group",
            "fieldtype": "Link",
            "options": "Customer Group",
            "width": 120,
        },
        {
            "label": _("Territory"),
            "fieldname": "territory",
            "fieldtype": "Link",
            "options": "Territory",
            "width": 100,
        },
        {
            "label": _("Return Against"),
            "fieldname": "return_against",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 160,
        },
        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 140,
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "label": _("Item Group"),
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 120,
        },
        {
            "label": _("Qty"),
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 80,
        },
        {
            "label": _("Rate"),
            "fieldname": "rate",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 100,
        },
        {
            "label": _("Net Amount"),
            "fieldname": "net_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": _("Tax Amount"),
            "fieldname": "tax_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": _("Grand Total"),
            "fieldname": "grand_total",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": _("Currency"),
            "fieldname": "currency",
            "fieldtype": "Data",
            "width": 60,
            "hidden": 1,
        },
        {
            "label": _("Remarks"),
            "fieldname": "remarks",
            "fieldtype": "Data",
            "width": 200,
        },
    ]


def get_data(filters):
    conditions = _build_conditions(filters)

    rows = frappe.db.sql(
        """
        SELECT
            si.name,
            si.posting_date,
            si.customer,
            si.customer_name,
            si.customer_group,
            si.territory,
            si.return_against,
            si.base_grand_total  AS grand_total,
            si.remarks,
            si.currency,
            sii.item_code,
            sii.item_name,
            sii.item_group,
            sii.qty,
            sii.rate,
            sii.base_net_amount  AS net_amount
        FROM
            `tabSales Invoice` si
            INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE
            si.docstatus = 1
            AND si.is_return = 1
            {conditions}
        ORDER BY
            si.posting_date DESC, si.name DESC, sii.idx ASC
        """.format(conditions=conditions),
        filters,
        as_dict=True,
    )

    if not rows:
        print(_("No data found for the given filters."))
        return []

    # Fetch per-invoice tax totals in one query
    invoice_names = list({r.name for r in rows})
    tax_map = _get_tax_map(invoice_names)

    seen = set()
    for row in rows:
        row["tax_amount"] = tax_map.get(row["name"], 0.0) if row["name"] not in seen else 0.0
        if row["name"] not in seen:
            seen.add(row["name"])

    return rows


def _build_conditions(filters):
    parts = []

    if filters.get("company"):
        parts.append("AND si.company = %(company)s")

    if filters.get("from_date"):
        parts.append("AND si.posting_date >= %(from_date)s")

    if filters.get("to_date"):
        parts.append("AND si.posting_date <= %(to_date)s")

    if filters.get("customer"):
        parts.append("AND si.customer = %(customer)s")

    if filters.get("customer_group"):
        parts.append("AND si.customer_group = %(customer_group)s")

    if filters.get("territory"):
        parts.append("AND si.territory = %(territory)s")

    if filters.get("item_group"):
        parts.append("AND sii.item_group = %(item_group)s")

    if filters.get("item_code"):
        parts.append("AND sii.item_code = %(item_code)s")

    return " ".join(parts)


def _get_tax_map(invoice_names):
    if not invoice_names:
        return {}

    rows = frappe.db.sql(
        """
        SELECT parent, SUM(base_tax_amount_after_discount_amount) AS tax_amount
        FROM `tabSales Taxes and Charges`
        WHERE parenttype = 'Sales Invoice'
          AND parent IN ({placeholders})
        GROUP BY parent
        """.format(placeholders=", ".join(["%s"] * len(invoice_names))),
        invoice_names,
        as_dict=True,
    )

    return {r.parent: flt(r.tax_amount) for r in rows}
