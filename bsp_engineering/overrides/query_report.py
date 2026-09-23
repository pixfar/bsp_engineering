import frappe
import json
import frappe.desk.query_report
from frappe.desk.query_report import export_query as original_export_query, run as original_run

@frappe.whitelist()
def export_query():
    """
    Override of frappe.desk.query_report.export_query to inject user-specific 
    column visibility preferences into the report data before generating the export file.
    """
    def wrapped_run(*args, **kwargs):
        # Call original run to get report data
        res = original_run(*args, **kwargs)
        
        # Determine report_name
        report_name = kwargs.get("report_name") or (args[0] if args else None)
        
        if report_name and res and res.get("columns"):
            # Check for user column preferences
            prefs = frappe.db.get_value(
                "Report Column Visibility", 
                {"user": frappe.session.user, "report_name": report_name}, 
                "visible_columns"
            )
            
            if prefs:
                try:
                    visible_columns = json.loads(prefs)
                    # Mark columns as hidden if they are not in visible_columns
                    for col in res.get("columns"):
                        col_id = col.get("id") or col.get("fieldname")
                        if col_id not in visible_columns:
                            col["hidden"] = 1
                except Exception as e:
                    frappe.log_error(f"Error applying column visibility for export: {e}")
                    
        return res
        
    try:
        # Temporarily monkey-patch the run method so _export_query uses our wrapper
        frappe.desk.query_report.run = wrapped_run
        return original_export_query()
    finally:
        # Ensure we restore the original method
        frappe.desk.query_report.run = original_run
