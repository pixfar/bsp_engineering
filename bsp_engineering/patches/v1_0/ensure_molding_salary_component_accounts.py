"""Backfill Accounts on Molding salary components.

`setup_molding_salary_system` originally created Molding Daily Wage /
Molding Wastage Deduction without a per-company Accounts row. Payroll Entry
then throws "Please set account in Salary Component …" when booking. This
patch re-runs the (now fixed) setup so existing sites pick up the accounts
on migrate without manual form edits.
"""


def execute():
	from bsp_engineering.patches.v1_0.setup_molding_salary_system import execute as setup

	setup()
