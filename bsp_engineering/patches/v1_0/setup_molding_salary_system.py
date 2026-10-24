import frappe


# Canonical name for new sites. Existing BSP installs used the typo'd name;
# `_find_molding_structure` accepts either so we never create a duplicate.
MOLDING_STRUCTURE_NAME = "Molding Employee Salary Structure"
MOLDING_STRUCTURE_LEGACY_NAME = "Molding Employee Salary Stracture"

# Zero-amount placeholders so Salary Structure Assignment / Payroll Entry have
# a valid Weekly structure. Real molding pay arrives via Additional Salary
# (Molding Daily Wage / Molding Wastage Deduction), not these base lines.
MOLDING_STRUCTURE_EARNINGS = ("Employee Salary", "Employee Rewards")
MOLDING_STRUCTURE_DEDUCTIONS = ("Penalty Deduction",)


def execute():
	"""Prerequisite data for the Molding (piece-rate) Salary System:

	- Employee.custom_molding_point: each worker's share-point used to split a
	  day's production wage and a week's wastage penalty across everyone who
	  worked.
	- Two Salary Components (Molding Daily Wage / Molding Wastage Deduction)
	  that Molding Daily Production / Molding Weekly Wastage create Additional
	  Salary entries against, on submit — including the per-company Accounts
	  row Payroll Entry needs when booking the journal.
	- Weekly Salary Structure "Molding Employee Salary Structure" (zero base
	  lines) so employees can receive a Salary Structure Assignment.

	Idempotent -- safe to run again (e.g. after a fixtures re-sync) since
	both parts check for the record before creating it, and account rows are
	only appended when a company is still missing. Also safe on a bench that
	already had the old "Verti"-named field/components renamed in place
	(bsp_engineering.patches.v1_0.setup_verti_salary_system, superseded by
	this patch) -- the exists() checks below just no-op in that case.
	"""
	_ensure_molding_point_field()
	_ensure_salary_component("Molding Daily Wage", "MDW", "Earning")
	_ensure_salary_component("Molding Wastage Deduction", "MWD", "Deduction")
	_ensure_molding_salary_structures()


def _ensure_molding_point_field():
	name = "Employee-custom_molding_point"
	if frappe.db.exists("Custom Field", name):
		return
	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "Employee",
			"fieldname": "custom_molding_point",
			"fieldtype": "Float",
			"label": "Molding Point",
			"insert_after": "designation",
			"description": "Share point used to split Molding piece-rate wages and wastage penalties across present workers.",
			"non_negative": 1,
		}
	).insert(ignore_permissions=True)


def _ensure_salary_component(component_name, abbr, component_type):
	if frappe.db.exists("Salary Component", component_name):
		doc = frappe.get_doc("Salary Component", component_name)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Salary Component",
				"salary_component": component_name,
				"salary_component_abbr": abbr,
				"type": component_type,
				# Absolute Additional Salary amounts — do not prorate by attendance days.
				"depends_on_payment_days": 0,
				"description": f"Auto-created by the Molding Salary System ({component_type}).",
			}
		)
		doc.insert(ignore_permissions=True)

	# Existing installs may still have HRMS' default (depends_on_payment_days=1).
	if doc.depends_on_payment_days:
		doc.depends_on_payment_days = 0
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)

	_ensure_component_accounts(doc)


def _ensure_component_accounts(doc):
	"""Payroll Entry refuses to book salary when the component has no Accounts
	row for the company. Match the rest of BSP payroll (Employee Salary /
	Penalty Deduction) and use the company's Salary expense account.
	"""
	existing = {row.company for row in doc.accounts}
	changed = False
	for company in frappe.get_all("Company", pluck="name"):
		if company in existing:
			continue
		account = _resolve_salary_account(company)
		if not account:
			frappe.log_error(
				title="Molding Salary Component account missing",
				message=f"No Salary expense account found for company {company}; "
				f"skipped Accounts row on {doc.name}.",
			)
			continue
		doc.append("accounts", {"company": company, "account": account})
		changed = True
	if changed:
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)


def _resolve_salary_account(company):
	abbr = frappe.get_cached_value("Company", company, "abbr")
	salary_account = f"Salary - {abbr}"
	if frappe.db.exists("Account", salary_account):
		return salary_account
	return frappe.get_cached_value("Company", company, "default_expense_account")


def _ensure_molding_salary_structures():
	"""One Weekly active Salary Structure per company for molding workers."""
	for company in frappe.get_all("Company", fields=["name", "default_currency", "default_payroll_payable_account"]):
		if _find_molding_structure(company.name):
			continue
		_create_molding_structure(company)


def _find_molding_structure(company):
	for name in (MOLDING_STRUCTURE_NAME, MOLDING_STRUCTURE_LEGACY_NAME):
		if frappe.db.exists("Salary Structure", {"name": name, "company": company}):
			return name
		# Name is unique globally; if the structure exists for this company under
		# either spelling, treat it as already set up even when company filter
		# on name lookup is redundant.
		if frappe.db.exists("Salary Structure", name):
			existing_company = frappe.db.get_value("Salary Structure", name, "company")
			if existing_company == company:
				return name
	return None


def _create_molding_structure(company):
	earnings = [
		{"salary_component": component, "amount": 0}
		for component in MOLDING_STRUCTURE_EARNINGS
		if frappe.db.exists("Salary Component", component)
	]
	deductions = [
		{"salary_component": component, "amount": 0}
		for component in MOLDING_STRUCTURE_DEDUCTIONS
		if frappe.db.exists("Salary Component", component)
	]
	# Fresh site with no shared components yet — still need a non-empty structure.
	if not earnings:
		earnings = [{"salary_component": "Molding Daily Wage", "amount": 0}]
	if not deductions:
		deductions = [{"salary_component": "Molding Wastage Deduction", "amount": 0}]

	currency = company.default_currency or frappe.db.get_value("Company", company.name, "default_currency")
	payment_account = company.default_payroll_payable_account
	if not payment_account:
		abbr = frappe.get_cached_value("Company", company.name, "abbr")
		candidate = f"Payroll Payable - {abbr}"
		if frappe.db.exists("Account", candidate):
			payment_account = candidate

	doc = frappe.get_doc(
		{
			"doctype": "Salary Structure",
			"name": MOLDING_STRUCTURE_NAME,
			"company": company.name,
			"currency": currency,
			"payroll_frequency": "Weekly",
			"is_active": "Yes",
			"is_default": "No",
			"payment_account": payment_account,
			"earnings": earnings,
			"deductions": deductions,
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	frappe.logger("bsp_engineering").info(
		f"Created Salary Structure {doc.name} for company {company.name}"
	)
