from bsp_engineering.utils.party_statement import execute as execute_party_statement


def execute(filters=None):
	return execute_party_statement("Customer", filters)
