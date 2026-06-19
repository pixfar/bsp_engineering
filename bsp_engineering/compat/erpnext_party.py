import erpnext.accounts.party as party_module


def apply_compat_patches():
	"""Backfill party helpers removed or moved in some ERPNext builds."""
	if hasattr(party_module, 'get_party_bank_account'):
		return

	try:
		from erpnext.accounts.doctype.bank_account.bank_account import (
			get_party_bank_account,
		)
	except ImportError:
		return

	party_module.get_party_bank_account = get_party_bank_account
