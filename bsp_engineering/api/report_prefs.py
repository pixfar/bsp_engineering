import frappe

@frappe.whitelist()
def save_column_visibility(report_name, visible_columns):
    user = frappe.session.user
    
    # Check if a record already exists for this user and report
    existing_docs = frappe.get_all(
        "Report Column Visibility", 
        filters={"user": user, "report_name": report_name},
        pluck="name",
        order_by="creation asc"
    )
    
    if existing_docs:
        # Update the first one
        primary_doc = existing_docs[0]
        frappe.db.set_value("Report Column Visibility", primary_doc, "visible_columns", visible_columns)
        
        # If there are accidental duplicates, delete them
        if len(existing_docs) > 1:
            for duplicate in existing_docs[1:]:
                frappe.delete_doc("Report Column Visibility", duplicate, ignore_permissions=True)
                
        return primary_doc
    else:
        # Create a new record
        doc = frappe.new_doc("Report Column Visibility")
        doc.user = user
        doc.report_name = report_name
        doc.visible_columns = visible_columns
        doc.insert(ignore_permissions=True)
        return doc.name
