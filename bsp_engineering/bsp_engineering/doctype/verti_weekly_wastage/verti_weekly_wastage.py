# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Criterion
from frappe.query_builder.functions import Sum
from frappe.utils import flt, getdate

from bsp_engineering.bsp_engineering.utils.verti_salary import (
	cancel_additional_salaries,
	create_additional_salaries_or_rollback,
)

ALLOWED_WASTAGE_RATE = 0.01  # 1%
PENALTY_PER_KG = 20  # BDT per excess KG
SALARY_COMPONENT = "Verti Wastage Deduction"


class VertiWeeklyWastage(Document):
	def validate(self):
		self.validate_dates()
		self.calculate_wastage_figures()

	def validate_dates(self):
		# Deliberately no Thursday/Wednesday or fixed-length constraint --
		# the period covered is up to whoever fills this in (a day, a few
		# days, a full week, whatever), only the ordering has to make sense.
		if not (self.start_date and self.end_date):
			return
		if getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_('End Date cannot be before Start Date.'))

	def calculate_wastage_figures(self):
		self.allowed_wastage_kg = flt(self.total_weekly_work_kg) * ALLOWED_WASTAGE_RATE
		excess = flt(self.actual_wastage_kg) - flt(self.allowed_wastage_kg)
		self.excess_wastage_kg = excess if excess > 0 else 0
		self.penalty_amount = flt(self.excess_wastage_kg) * PENALTY_PER_KG

	def on_submit(self):
		self._distribute_penalty()

	def on_cancel(self):
		cancel_additional_salaries(self.doctype, self.name)

	def _distribute_penalty(self):
		if flt(self.penalty_amount) <= 0:
			return

		points_by_employee = get_weekly_points(self.start_date, self.end_date)
		total_points = sum(points_by_employee.values())
		if total_points <= 0:
			frappe.throw(
				_(
					'No worker points found between {0} and {1} '
					'(submitted Verti Daily Production records) to distribute the penalty against.'
				).format(self.start_date, self.end_date)
			)

		rows = []
		for employee, points in points_by_employee.items():
			share = flt(self.penalty_amount) * (points / total_points)
			if share <= 0:
				continue
			rows.append(
				{
					'employee': employee,
					'salary_component': SALARY_COMPONENT,
					'amount': share,
					'payroll_date': self.end_date,
				}
			)
		create_additional_salaries_or_rollback(rows, self.doctype, self.name)


def get_weekly_points(start_date, end_date):
	"""{employee: total point} across every submitted Verti Daily Production
	whose date falls within [start_date, end_date] -- each worker's share of
	that week's total is what the wastage penalty gets split by."""
	Production = frappe.qb.DocType('Verti Daily Production')
	Detail = frappe.qb.DocType('Verti Daily Production Detail')

	rows = (
		frappe.qb.from_(Detail)
		.inner_join(Production)
		.on(Production.name == Detail.parent)
		.select(Detail.employee, Sum(Detail.point).as_('total_points'))
		.where(
			Criterion.all(
				[
					Production.docstatus == 1,
					Production.date.between(getdate(start_date), getdate(end_date)),
				]
			)
		)
		.groupby(Detail.employee)
	).run(as_dict=True)

	return {row.employee: flt(row.total_points) for row in rows}


@frappe.whitelist()
def fetch_weekly_data(start_date, end_date):
	"""Sum total_work_kg across every submitted Verti Daily Production
	between start_date and end_date, for the "Fetch Weekly Data" button."""
	if not (start_date and end_date):
		frappe.throw(_('Both Start Date and End Date are required.'))

	Production = frappe.qb.DocType('Verti Daily Production')
	result = (
		frappe.qb.from_(Production)
		.select(Sum(Production.total_work_kg).as_('total'))
		.where(
			Criterion.all(
				[
					Production.docstatus == 1,
					Production.date.between(getdate(start_date), getdate(end_date)),
				]
			)
		)
	).run(as_dict=True)

	total = flt(result[0].total) if result and result[0].total else 0
	return {'total_weekly_work_kg': total}
