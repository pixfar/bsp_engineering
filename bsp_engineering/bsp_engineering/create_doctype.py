import frappe

def create():
    if frappe.db.exists("DocType", "Report Column Visibility"):
        return
    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": "Report Column Visibility",
        "module": "Bsp Engineering",
        "custom": 1,
        "is_submittable": 0,
        "fields": [
            {"label": "User", "fieldname": "user", "fieldtype": "Link", "options": "User", "reqd": 1, "in_list_view": 1},
            {"label": "Report Name", "fieldname": "report_name", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
            {"label": "Visible Columns", "fieldname": "visible_columns", "fieldtype": "Long Text"}
        ],
        "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
                        {"role": "All", "read": 1, "write": 1, "create": 1, "delete": 1}],
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    print("DocType created")
