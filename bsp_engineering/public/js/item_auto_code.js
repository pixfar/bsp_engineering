// Automatic Item Code: prefill new Items with the next code in BSP's running
// 8-digit sequence (see doc_events/item/auto_item_code.py). The code stays
// editable; `__bsp_auto_code` records what was filled in so the server can
// move it on to the next free code if someone else saved it first.

frappe.provide("bsp_engineering.item_code");

bsp_engineering.item_code.fill = async function (doc, set_value) {
	if (!doc || doc.item_code || doc.variant_of) return;
	try {
		const { message: code } = await frappe.call({
			method: "bsp_engineering.doc_events.item.auto_item_code.get_next_item_code",
		});
		// The user may have typed a code while the request was in flight.
		if (!code || doc.item_code) return;
		doc.__bsp_auto_code = code;
		await set_value(code);
	} catch (e) {
		console.error("Could not fetch next Item Code", e);
	}
};

// Picked up automatically by frappe.ui.form.make_quick_entry for Item
// ("<DocType>QuickEntryForm"), so the "New Item" dialog gets the code too.
if (frappe.ui?.form?.QuickEntryForm && !frappe.ui.form.ItemQuickEntryForm) {
	frappe.ui.form.ItemQuickEntryForm = class ItemQuickEntryForm extends frappe.ui.form.QuickEntryForm {
		render_dialog() {
			super.render_dialog();
			if (this.dialog.fields_dict.item_code) {
				bsp_engineering.item_code.fill(this.dialog.doc, (code) =>
					this.dialog.set_value("item_code", code)
				);
			}
		}
	};
}
