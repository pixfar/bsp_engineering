"""Ensure the Weekly Molding Employee Salary Structure exists.

Earlier molding setup only created Salary Components. Payroll still needs a
submitted Weekly Salary Structure (and later a Salary Structure Assignment
per employee). Re-runs the idempotent molding setup so new and existing
sites get the structure on migrate.
"""


def execute():
	from bsp_engineering.patches.v1_0.setup_molding_salary_system import execute as setup

	setup()
