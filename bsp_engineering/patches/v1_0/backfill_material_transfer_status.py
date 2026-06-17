import frappe

from bsp_engineering.bsp_engineering.doctype.material_transfer.material_transfer import (
	STATUS_FULL,
	STATUS_IN_TRANSIT,
)


def execute():
	"""Normalize legacy Material Transfer statuses after workflow simplification."""
	if not frappe.db.table_exists('tabMaterial Transfer'):
		return

	frappe.db.sql(
		"""
		UPDATE `tabMaterial Transfer`
		SET transfer_status = %s
		WHERE docstatus = 1 AND transfer_status = 'Pending'
		""",
		STATUS_IN_TRANSIT,
	)

	frappe.db.sql(
		"""
		UPDATE `tabMaterial Transfer`
		SET transfer_status = %s
		WHERE docstatus = 1 AND transfer_status = 'Received'
		""",
		STATUS_FULL,
	)
