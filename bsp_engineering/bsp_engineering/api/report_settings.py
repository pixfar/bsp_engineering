# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _

@frappe.whitelist()
def get_user_report_settings(report_name):
    """
    Fetches persisted column settings for the current user and a specific report.
    """
    user = frappe.session.user

    doc_name = frappe.db.get_value("BSP Report User Setting",
        {"user": user, "report_name": report_name}, "name")

    if not doc_name:
        return {
            "hidden_columns": [],
            "column_order": []
        }

    doc = frappe.get_doc("BSP Report User Setting", doc_name)

    return {
        "hidden_columns": json.loads(doc.hidden_columns) if doc.hidden_columns else [],
        "column_order": json.loads(doc.column_order) if doc.column_order else []
    }

@frappe.whitelist()
def save_user_report_settings(report_name, hidden_columns, column_order):
    """
    Saves or updates column settings for the current user and a specific report.
    """
    user = frappe.session.user

    # Ensure inputs are stored as JSON strings
    hidden_json = json.dumps(hidden_columns)
    order_json = json.dumps(column_order)

    doc_name = frappe.db.get_value("BSP Report User Setting",
        {"user": user, "report_name": report_name}, "name")

    if doc_name:
        doc = frappe.get_doc("BSP Report User Setting", doc_name)
        doc.hidden_columns = hidden_json
        doc.column_order = order_json
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "BSP Report User Setting",
            "user": user,
            "report_name": report_name,
            "hidden_columns": hidden_json,
            "column_order": order_json
        })
        doc.insert(ignore_permissions=True)
        doc.save(ignore_permissions=True)

    return True
