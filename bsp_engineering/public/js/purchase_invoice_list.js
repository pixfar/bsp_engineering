frappe.listview_settings["Purchase Invoice"] = frappe.listview_settings["Purchase Invoice"] || {};

(function () {
    const settings = frappe.listview_settings["Purchase Invoice"];

    // 1. Fetch BOTH per_received and update_stock from the database
    settings.add_fields = ["per_received", "update_stock"];

    // Define columns explicitly
    settings.columns = [
        "status",
        "grand_total",
        "posting_date",
        "name",
        "custom_delivery_status",
    ];

    const color_map = {
        "Not Received": "red",
        "Partially Received": "orange",
        "Fully Received": "green",
    };

    settings.formatters = settings.formatters || {};
    
    settings.formatters["custom_delivery_status"] = function (value, df, doc) {
        let actual_status = value;

        // 2. HIGHEST PRIORITY: If "Update Stock" is checked, it is always Fully Received
        if (doc.update_stock === 1) {
            actual_status = "Fully Received";
        } 
        // 3. Otherwise, fall back to the percentage calculation
        else if (doc.per_received >= 100) {
            actual_status = "Fully Received";
        } else if (doc.per_received > 0 && doc.per_received < 100) {
            actual_status = "Partially Received";
        } else if (doc.per_received === 0 || !doc.per_received) {
            actual_status = "Not Received";
        }

        if (!actual_status) return "";
        
        const color = color_map[actual_status] || "grey";
        return `<span class="indicator-pill ${color}">${__(actual_status)}</span>`;
    };
})();