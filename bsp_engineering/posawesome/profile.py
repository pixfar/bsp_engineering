import frappe


@frappe.whitelist()
def get_active_pos_profile(user=None):
	"""Return the POS profile currently assigned to the user."""
	user = user or frappe.session.user

	rows = frappe.get_all(
		'POS Profile User',
		filters={'user': user},
		fields=['parent', 'modified'],
		order_by='modified desc',
		limit=1,
	)
	profile_name = rows[0].parent if rows else None

	if not profile_name:
		profile_name = frappe.db.get_single_value('POS Settings', 'pos_profile')

	if not profile_name:
		return None

	return frappe.get_doc('POS Profile', profile_name).as_dict()


@frappe.whitelist()
def check_opening_shift(user=None):
	"""Return open shift data using the user's current POS Profile assignment."""
	user = user or frappe.session.user

	from posawesome.posawesome.api.shifts import update_opening_shift_data

	open_vouchers = frappe.db.get_all(
		'POS Opening Shift',
		filters={
			'user': user,
			'pos_closing_shift': ['is', 'not set'],
			'docstatus': 1,
			'status': 'Open',
		},
		fields=['name', 'pos_profile'],
		order_by='period_start_date desc',
	)

	if not open_vouchers:
		return ''

	data = {
		'pos_opening_shift': frappe.get_doc(
			'POS Opening Shift', open_vouchers[0]['name']
		),
	}
	active_profile = get_active_pos_profile(user)
	profile_name = (
		active_profile.get('name')
		if active_profile
		else open_vouchers[0]['pos_profile']
	)
	update_opening_shift_data(data, profile_name)
	return data
