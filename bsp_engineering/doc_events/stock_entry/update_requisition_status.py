from bsp_engineering.bsp_engineering.doctype.requisition.transfer_status import (
	update_requisition_transfer_status,
)


def sync_requisition_transfer_status(doc, method=None):
	requisition = doc.get('custom_requisition')
	if not requisition:
		return
	update_requisition_transfer_status(requisition)
