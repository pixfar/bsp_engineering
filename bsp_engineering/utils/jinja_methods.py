def get_account_balance_on(account, date=None, company=None):
	"""Account balance as of a date -- used by print formats (e.g. BSP
	Fundtransfer) to show a showroom's Cash In Hand balance before/after a
	voucher, without duplicating ERPNext's GL balance logic."""
	from erpnext.accounts.utils import get_balance_on

	return get_balance_on(account=account, date=date, company=company)


def can_view_all_warehouse_stock():
	"""Whether the current user may see every warehouse's stock (System
	Manager, BSP Admin, BSP Viewer) -- print formats use it to show the
	other warehouse's stock only to them. Same rule as the POS screens
	(posawesome's get_expanded_permitted_warehouses returns None for them)."""
	from posawesome.posawesome.utils.warehouse_doc_permissions import (
		get_expanded_permitted_warehouses,
	)

	return get_expanded_permitted_warehouses() is None
