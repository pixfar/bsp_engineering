import frappe


def execute():
	frappe.db.sql(
		"""
		UPDATE `tabSales Invoice`
		SET custom_is_paid = 0
		WHERE is_return = 1
			AND IFNULL(custom_is_paid, 0) = 1
		"""
	)
	_disable_legacy_client_script()


def _disable_legacy_client_script():
	script_name = 'Hide Is Paid on Return Invoice'
	if frappe.db.exists('Client Script', script_name):
		frappe.db.set_value('Client Script', script_name, 'enabled', 0)
