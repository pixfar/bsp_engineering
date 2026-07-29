import frappe


def execute():
	"""custom_warehouse on Account: explicitly links a Cash In Hand leaf
	account (e.g. a showroom's own cash account) to the Warehouse it belongs
	to, for the Warehouse Wise Owner Fund Transfer reports. Direct and
	authoritative, unlike inferring the warehouse via whichever POS Profile
	happens to have that account set as its account_for_change_amount --
	not every warehouse has one of those configured.
	"""
	_create_custom_field(
		{
			'dt': 'Account',
			'fieldname': 'custom_warehouse',
			'fieldtype': 'Link',
			'options': 'Warehouse',
			'label': 'Warehouse',
			'insert_after': 'account_name',
		}
	)
	_seed_exact_name_matches()


def _create_custom_field(field):
	name = f"{field['dt']}-{field['fieldname']}"
	if frappe.db.exists('Custom Field', name):
		return
	frappe.get_doc({'doctype': 'Custom Field', **field}).insert(ignore_permissions=True)


def _seed_exact_name_matches():
	"""Best-effort seed: only link an account to a warehouse when their
	names match exactly (e.g. account "বি.এস.পি ঢাকা শোরুম - BSP" and
	warehouse "বি.এস.পি ঢাকা শোরুম - BSP"). Anything less certain (e.g.
	"Petty Cash Chadpur - BSP" vs a differently-spelled warehouse name) is
	left for a human to set via Customize Form on Account.
	"""
	warehouse_names = set(frappe.get_all('Warehouse', pluck='name'))
	if not warehouse_names:
		return

	accounts = frappe.get_all(
		'Account',
		filters={'is_group': 0, 'name': ['in', list(warehouse_names)]},
		fields=['name', 'custom_warehouse'],
	)
	for acc in accounts:
		if acc.custom_warehouse:
			continue
		frappe.db.set_value('Account', acc.name, 'custom_warehouse', acc.name, update_modified=False)
