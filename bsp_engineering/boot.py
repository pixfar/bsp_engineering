# Copyright (c) 2026, Pixfar and contributors
# For license information, please see license.txt

from bsp_engineering.utils.pos_warehouse import can_change_pos_warehouse


def boot_session(bootinfo):
	"""Expose POS warehouse-switcher eligibility to the desk / POS frontend."""
	try:
		bootinfo.can_switch_pos_warehouse = bool(can_change_pos_warehouse())
	except Exception:
		bootinfo.can_switch_pos_warehouse = False
