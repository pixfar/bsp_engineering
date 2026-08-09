# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Criterion
from frappe.utils import add_days, flt, getdate

from bsp_engineering.bsp_engineering.utils.verti_salary import (
	cancel_additional_salaries,
	create_additional_salaries_or_rollback,
)

WEDNESDAY = 2  # Python's date.weekday(): Monday=0 ... Sunday=6
SALARY_COMPONENT = "Verti Daily Wage"


class VertiDailyProduction(Document):
	def validate(self):
		self.calculate_total_wage()
		self.distribute_wage()

	def calculate_total_wage(self):
		self.total_wage = flt(self.total_work_kg) * flt(self.rate_per_kg)

	def distribute_wage(self):
		"""Per Point Rate = Total Wage / Sum of Points; daily_salary = point *
		Per Point Rate for every row. Recomputed server-side on every save --
		never trust the client's copy of a financial figure, the .js does the
		same calculation only so the form doesn't need a round trip to show
		it live."""
		if not self.present_employees:
			return

		total_points = sum(flt(row.point) for row in self.present_employees)
		if total_points <= 0:
			frappe.throw(
				_("Total points of present employees must be greater than zero to distribute wages.")
			)

		per_point_rate = flt(self.total_wage) / total_points
		for row in self.present_employees:
			row.daily_salary = flt(row.point) * per_point_rate

	def on_submit(self):
		self._create_additional_salaries()

	def on_cancel(self):
		cancel_additional_salaries(self.doctype, self.name)

	def _create_additional_salaries(self):
		if not self.present_employees:
			return

		payroll_date = get_upcoming_weekday(self.date, WEDNESDAY)
		rows = [
			{
				"employee": row.employee,
				"salary_component": SALARY_COMPONENT,
				"amount": row.daily_salary,
				"payroll_date": payroll_date,
			}
			for row in self.present_employees
		]
		create_additional_salaries_or_rollback(rows, self.doctype, self.name)


def get_upcoming_weekday(from_date, weekday):
	"""The next date on or after `from_date` that falls on `weekday`
	(Monday=0 ... Sunday=6). If `from_date` itself is already that weekday,
	returns `from_date` unchanged -- production logged on a Wednesday is
	paid that same Wednesday rather than waiting a full week."""
	d = getdate(from_date)
	days_ahead = (weekday - d.weekday()) % 7
	return add_days(d, days_ahead)


@frappe.whitelist()
def fetch_attendance(date):
	"""Employees marked Present in standard Attendance for `date`, each with
	their current Verti Point, for the "Fetch Attendance" button to populate
	the child table with."""
	if not date:
		frappe.throw(_("Date is required to fetch attendance."))

	Attendance = frappe.qb.DocType("Attendance")
	Employee = frappe.qb.DocType("Employee")

	rows = (
		frappe.qb.from_(Attendance)
		.inner_join(Employee)
		.on(Employee.name == Attendance.employee)
		.select(
			Attendance.employee,
			Employee.employee_name,
			Employee.custom_verti_point,
		)
		.where(
			Criterion.all(
				[
					Attendance.attendance_date == getdate(date),
					Attendance.status == "Present",
					Attendance.docstatus == 1,
					Employee.status == "Active",
				]
			)
		)
		.orderby(Employee.employee_name)
	).run(as_dict=True)

	if not rows:
		frappe.msgprint(_("No employees found marked Present for {0}.").format(date))

	return [
		{
			"employee": row.employee,
			"employee_name": row.employee_name,
			"point": flt(row.custom_verti_point),
		}
		for row in rows
	]
