def get_account_balance_on(account, date=None, company=None):
	"""Account balance as of a date -- used by print formats (e.g. BSP
	Fundtransfer) to show a showroom's Cash In Hand balance before/after a
	voucher, without duplicating ERPNext's GL balance logic."""
	from erpnext.accounts.utils import get_balance_on

	return get_balance_on(account=account, date=date, company=company)
