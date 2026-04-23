import frappe
from frappe import _
from frappe.utils import get_time, now_datetime, today


def send_low_stock_alert_report():
	settings = frappe.get_single('BSP System Settings')
	threshold = _get_threshold(settings.low_stock_alert_qtq)
	role = settings.low_stock_alert_role
	alert_time = settings.low_stock_alert_time

	if threshold is None or not role or not alert_time:
		return

	if not _is_right_time(alert_time):
		return

	if _already_sent_today(alert_time):
		return

	low_stock_items = _get_low_stock_items(threshold)
	if not low_stock_items:
		_mark_sent(alert_time)
		return

	recipients = _get_role_users(role)
	if not recipients:
		_mark_sent(alert_time)
		return

	subject = _('Low Stock Alert - {0}').format(today())
	body = _build_low_stock_email(low_stock_items, threshold)
	frappe.sendmail(recipients=recipients, subject=subject, message=body)
	_mark_sent(alert_time)


def _get_threshold(value):
	if value is None or value == '':
		return None

	try:
		return float(value)
	except (TypeError, ValueError):
		frappe.log_error(
			f'Invalid low_stock_alert_qtq value: {value}',
			'BSP Low Stock Alert',
		)
		return None


def _is_right_time(alert_time):
	current_time = get_time(now_datetime())
	set_time = get_time(alert_time)
	return (
		current_time.hour == set_time.hour
		and current_time.minute == set_time.minute
	)


def _already_sent_today(alert_time):
	time_key = get_time(alert_time).strftime('%H:%M')
	cache_key = f'bsp_low_stock_alert_sent::{today()}::{time_key}'
	return bool(frappe.cache().get_value(cache_key))


def _mark_sent(alert_time):
	time_key = get_time(alert_time).strftime('%H:%M')
	cache_key = f'bsp_low_stock_alert_sent::{today()}::{time_key}'
	frappe.cache().set_value(cache_key, 1, expires_in_sec=86400)


def _get_low_stock_items(threshold):
	return frappe.db.sql(
		"""
		SELECT
			item_code,
			SUM(actual_qty) AS qty
		FROM `tabBin`
		GROUP BY item_code
		HAVING SUM(actual_qty) <= %(threshold)s
		ORDER BY qty ASC
		""",
		{'threshold': threshold},
		as_dict=True,
	)


def _get_role_users(role):
	users = frappe.get_all(
		'Has Role',
		filters={'role': role, 'parenttype': 'User'},
		pluck='parent',
	)
	if not users:
		return []

	enabled_users = frappe.get_all(
		'User',
		filters={'name': ['in', users], 'enabled': 1},
		pluck='name',
	)
	return enabled_users


def _build_low_stock_email(low_stock_items, threshold):
	lines = [
		_('Items at or below configured stock level ({0}):').format(threshold),
		'',
	]
	for item in low_stock_items:
		lines.append(f"- {item.item_code}: {item.qty or 0}")

	return '<br>'.join(lines)
