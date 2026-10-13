# Regression tests: a POS sale must post stock from the warehouse the cashier
# selected, and non-stock lines must carry no warehouse.
#
# Reported live: invoices created by a warehouse-switching user (System
# Manager / BSP Admin on the "BSP Store Room" profile) for another warehouse
# showed up in the Stock Ledger under "Store Room - BSP", and service/labour
# lines showed the POS Profile's default warehouse.
#
# These tests run against this site's real POS Profiles, users, warehouses
# and items, and roll every change back.
#
#   bench --site <site> run-tests --module bsp_engineering.tests.test_pos_invoice_warehouse

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

COMPANY = 'BSP Engineering Works'
SWITCHER = 'jabed@bspengineeringworks.com'  # System Manager on "BSP Store Room"
SWITCHER_PROFILE = 'BSP Store Room'
LOCKED_USER = 'dhaka@bspengineeringworks.com'  # no warehouse-switch role
LOCKED_PROFILE = 'BSP Dhaka Showroom'

STORE_ROOM = 'Store Room - BSP'
NARSINGDI = 'Narsingdi Showroom - BSP'
DHAKA = 'Dhaka Showroom - BSP'


def _pick_stock_items(count=2):
	rows = frappe.db.sql(
		"""
		SELECT b.item_code
		FROM `tabBin` b JOIN `tabItem` i ON i.name = b.item_code
		WHERE i.is_stock_item = 1 AND i.disabled = 0 AND i.has_variants = 0
			AND i.has_batch_no = 0 AND i.has_serial_no = 0
			AND b.warehouse IN %(warehouses)s AND b.actual_qty >= 10
		GROUP BY b.item_code
		HAVING COUNT(*) = %(n)s
		ORDER BY b.item_code
		LIMIT %(count)s
		""",
		{'warehouses': (STORE_ROOM, NARSINGDI, DHAKA), 'n': 3, 'count': count},
		pluck=True,
	)
	return rows


def _pick_non_stock_item():
	return frappe.db.get_value(
		'Item', {'is_stock_item': 0, 'disabled': 0, 'has_variants': 0}, 'name'
	)


class TestPosInvoiceWarehouse(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.stock_items = _pick_stock_items()
		cls.service_item = _pick_non_stock_item()
		cls.customer = frappe.db.get_value('Customer', {'disabled': 0}, 'name')
		missing = [
			name
			for name, ok in (
				('2 stock items with stock in all 3 warehouses', len(cls.stock_items) == 2),
				('a non-stock item', bool(cls.service_item)),
				('a customer', bool(cls.customer)),
				('switcher user', frappe.db.exists('User', SWITCHER)),
				('locked user', frappe.db.exists('User', LOCKED_USER)),
			)
			if not ok
		]
		if missing:
			raise cls.failureException('Test data missing: ' + ', '.join(missing))

	def setUp(self):
		frappe.db.savepoint('pos_invoice_warehouse_test')

	def tearDown(self):
		frappe.set_user('Administrator')
		frappe.db.rollback(save_point='pos_invoice_warehouse_test')

	# ------------------------------------------------------------------ helpers

	def _payload(self, profile, set_warehouse, row_warehouse, with_flags=False):
		items = []
		for code in self.stock_items + [self.service_item]:
			row = {
				'item_code': code,
				'qty': 1,
				'rate': 100,
				'price_list_rate': 100,
				'uom': frappe.db.get_value('Item', code, 'stock_uom'),
				'conversion_factor': 1,
				'warehouse': row_warehouse,
			}
			if with_flags:
				row['is_stock_item'] = 1 if code != self.service_item else 0
			items.append(row)
		return {
			'doctype': 'Sales Invoice',
			'company': COMPANY,
			'pos_profile': profile,
			'is_pos': 1,
			'update_stock': 1,
			'customer': self.customer,
			'posting_date': nowdate(),
			'set_warehouse': set_warehouse,
			'items': items,
			'payments': [{'mode_of_payment': 'Cash', 'amount': 0}],
		}

	def _update(self, payload):
		from bsp_engineering.posawesome.overrides import update_invoice

		return update_invoice(json.dumps(payload))

	def _submit(self, invoice):
		from bsp_engineering.posawesome.overrides import submit_invoice

		total = flt(invoice.get('rounded_total') or invoice.get('grand_total'))
		if total:  # a saved draft; a raw payload keeps its own payments
			invoice['payments'] = [
				{'mode_of_payment': 'Cash', 'amount': total, 'base_amount': total}
			]
		return submit_invoice(json.dumps(invoice, default=str), json.dumps({}))

	def _reloaded(self, name):
		"""The doc exactly as the POS reloads it before Pay (frappe.client.get)
		-- no is_stock_item on any row."""
		doc = json.loads(frappe.as_json(frappe.get_doc('Sales Invoice', name).as_dict()))
		for row in doc['items']:
			self.assertNotIn('is_stock_item', row)
		return doc

	def _line_warehouses(self, name):
		return dict(
			frappe.get_all(
				'Sales Invoice Item',
				filters={'parent': name},
				fields=['item_code', 'warehouse'],
				as_list=True,
			)
		)

	def _sle_warehouses(self, name):
		return {
			(row.item_code, row.warehouse)
			for row in frappe.get_all(
				'Stock Ledger Entry',
				filters={'voucher_no': name, 'is_cancelled': 0},
				fields=['item_code', 'warehouse'],
			)
		}

	def assertSaleOn(self, name, warehouse):
		lines = self._line_warehouses(name)
		for code in self.stock_items:
			self.assertEqual(lines[code], warehouse, f'stock line {code}')
		self.assertIsNone(lines[self.service_item], 'non-stock line must have no warehouse')
		self.assertEqual(
			frappe.db.get_value('Sales Invoice', name, 'set_warehouse'),
			warehouse,
			'invoice warehouse must not be blanked',
		)

	def assertCashTo(self, name, warehouse):
		"""The sale's money must land in one of the warehouse's own
		Cash / Bank Accounts -- on the invoice and on its Payment Entries."""
		from posawesome.posawesome.utils.invoice_warehouse import get_warehouse_cash_accounts

		accounts = get_warehouse_cash_accounts(warehouse)
		self.assertTrue(accounts, f'{warehouse} has no Cash / Bank Accounts configured')
		self.assertIn(frappe.db.get_value('Sales Invoice', name, 'payment_account'), accounts)
		for account in frappe.get_all(
			'Sales Invoice Payment Split', filters={'parent': name}, pluck='account'
		):
			self.assertIn(account, accounts, 'payment split account')
		paid_to = frappe.db.sql(
			"""SELECT pe.paid_to FROM `tabPayment Entry` pe
			JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
			WHERE per.reference_name = %s AND pe.docstatus = 1""",
			name,
			pluck=True,
		)
		self.assertTrue(paid_to, 'a Payment Entry must be created')
		for account in paid_to:
			self.assertIn(account, accounts, 'Payment Entry paid_to')

	def assertStockPostedFrom(self, name, warehouse):
		self.assertEqual(
			self._sle_warehouses(name),
			{(code, warehouse) for code in self.stock_items},
		)

	# -------------------------------------------------------------------- tests

	def test_switcher_draft_with_stale_rows_and_no_flags(self):
		"""Rows still on the profile default and no is_stock_item flag (the
		shape of a reloaded doc) must follow the selected warehouse."""
		frappe.set_user(SWITCHER)
		res = self._update(self._payload(SWITCHER_PROFILE, NARSINGDI, STORE_ROOM))
		self.assertSaleOn(res['name'], NARSINGDI)
		# the response carries correct flags back to the browser
		flags = {row['item_code']: row.get('is_stock_item') for row in res['items']}
		self.assertEqual(flags[self.service_item], 0)
		self.assertTrue(all(flags[code] == 1 for code in self.stock_items))

	def test_switcher_draft_with_flags(self):
		"""Flags present: non-stock line used to keep the profile warehouse and
		blank the invoice warehouse via ERPNext's reset_default_field_value."""
		frappe.set_user(SWITCHER)
		res = self._update(
			self._payload(SWITCHER_PROFILE, NARSINGDI, NARSINGDI, with_flags=True)
		)
		self.assertSaleOn(res['name'], NARSINGDI)

	def test_switcher_pay_submits_reloaded_doc(self):
		"""Exact production flow: save draft, reload it from the server
		(rows lose is_stock_item), submit. Stock must leave Narsingdi."""
		frappe.set_user(SWITCHER)
		res = self._update(self._payload(SWITCHER_PROFILE, NARSINGDI, NARSINGDI, True))
		self._submit(self._reloaded(res['name']))
		self.assertEqual(frappe.db.get_value('Sales Invoice', res['name'], 'docstatus'), 1)
		self.assertSaleOn(res['name'], NARSINGDI)
		self.assertStockPostedFrom(res['name'], NARSINGDI)
		self.assertCashTo(res['name'], NARSINGDI)

	def test_switch_warehouse_after_draft_was_saved(self):
		"""Draft saved under Store Room, cashier switches to Narsingdi and pays
		without editing the cart: the cached doc's rows still say Store Room."""
		frappe.set_user(SWITCHER)
		res = self._update(self._payload(SWITCHER_PROFILE, STORE_ROOM, STORE_ROOM))
		self.assertSaleOn(res['name'], STORE_ROOM)
		cached = self._reloaded(res['name'])
		cached['set_warehouse'] = NARSINGDI  # what syncCartWarehouse changes
		self._submit(cached)
		self.assertSaleOn(res['name'], NARSINGDI)
		self.assertStockPostedFrom(res['name'], NARSINGDI)
		# the draft's Store Room account must not survive the switch
		self.assertCashTo(res['name'], NARSINGDI)

	def test_submit_without_prior_draft(self):
		frappe.set_user(SWITCHER)
		payload = self._payload(SWITCHER_PROFILE, NARSINGDI, STORE_ROOM)
		payload['payments'] = [{'mode_of_payment': 'Cash', 'amount': 300}]
		res = self._submit(payload)
		self.assertSaleOn(res['name'], NARSINGDI)
		self.assertStockPostedFrom(res['name'], NARSINGDI)
		self.assertCashTo(res['name'], NARSINGDI)

	def test_selling_from_profile_default_still_works(self):
		frappe.set_user(SWITCHER)
		res = self._update(self._payload(SWITCHER_PROFILE, STORE_ROOM, STORE_ROOM))
		self._submit(self._reloaded(res['name']))
		self.assertSaleOn(res['name'], STORE_ROOM)
		self.assertStockPostedFrom(res['name'], STORE_ROOM)
		self.assertCashTo(res['name'], STORE_ROOM)

	def test_account_of_another_warehouse_is_corrected(self):
		"""Reported live (ACC-SINV-2026-24467): warehouse left on Store Room
		but the "Accounts" picker set to Bhairab -- stock and money ended up
		in different warehouses. The account now follows the sale warehouse."""
		frappe.set_user(SWITCHER)
		payload = self._payload(SWITCHER_PROFILE, STORE_ROOM, STORE_ROOM)
		payload['payment_account'] = 'Bhairab Showroom - BSP'
		res = self._update(payload)
		reloaded = self._reloaded(res['name'])
		reloaded['payment_account'] = 'Bhairab Showroom - BSP'
		self._submit(reloaded)
		self.assertStockPostedFrom(res['name'], STORE_ROOM)
		self.assertCashTo(res['name'], STORE_ROOM)

	def test_warehouse_switch_api_returns_that_warehouses_account(self):
		from posawesome.posawesome.utils.invoice_warehouse import (
			get_sale_cash_account,
			get_warehouse_cash_accounts,
		)

		narsingdi_accounts = get_warehouse_cash_accounts(NARSINGDI)
		self.assertEqual(get_sale_cash_account(NARSINGDI, 'Store Room - BSP'), narsingdi_accounts[0])
		self.assertEqual(get_sale_cash_account(NARSINGDI, narsingdi_accounts[0]), narsingdi_accounts[0])
		self.assertEqual(get_sale_cash_account(NARSINGDI, None), narsingdi_accounts[0])

	def test_locked_user_cannot_post_to_another_warehouse(self):
		"""A showroom user without switch rights is always forced to their own
		warehouse, even if the payload names another one."""
		frappe.set_user(LOCKED_USER)
		res = self._update(self._payload(LOCKED_PROFILE, NARSINGDI, NARSINGDI))
		self._submit(self._reloaded(res['name']))
		self.assertSaleOn(res['name'], DHAKA)
		self.assertStockPostedFrom(res['name'], DHAKA)
		self.assertCashTo(res['name'], DHAKA)

	def test_direct_document_submit_is_enforced_by_doc_events(self):
		"""Any path that bypasses the POS endpoints (offline outbox replay,
		desk, scripts) is still corrected by the Sales Invoice hooks."""
		frappe.set_user(SWITCHER)
		payload = self._payload(SWITCHER_PROFILE, NARSINGDI, STORE_ROOM)
		payload['is_pos'] = 0
		payload.pop('payments')
		doc = frappe.get_doc(payload)
		doc.insert()
		self.assertSaleOn(doc.name, NARSINGDI)
		doc.submit()
		self.assertSaleOn(doc.name, NARSINGDI)
		self.assertStockPostedFrom(doc.name, NARSINGDI)
		self.assertIn(
			frappe.db.get_value('Sales Invoice', doc.name, 'payment_account'),
			frappe.get_attr('posawesome.posawesome.utils.invoice_warehouse.get_warehouse_cash_accounts')(NARSINGDI),
		)

	def test_invoice_without_pos_profile_is_left_alone(self):
		"""Desk invoices with deliberately different warehouses per line are
		not touched (enforcement only applies to POS sales)."""
		doc = frappe.get_doc(
			{
				'doctype': 'Sales Invoice',
				'company': COMPANY,
				'customer': self.customer,
				'update_stock': 1,
				'items': [
					{'item_code': self.stock_items[0], 'qty': 1, 'rate': 100, 'warehouse': NARSINGDI},
					{'item_code': self.stock_items[1], 'qty': 1, 'rate': 100, 'warehouse': STORE_ROOM},
				],
			}
		)
		doc.insert()
		lines = self._line_warehouses(doc.name)
		self.assertEqual(lines[self.stock_items[0]], NARSINGDI)
		self.assertEqual(lines[self.stock_items[1]], STORE_ROOM)

	def test_invoice_detail_hides_non_stock_warehouse(self):
		from posawesome.posawesome.api.invoices import get_sales_invoice_detail

		frappe.set_user(SWITCHER)
		res = self._update(self._payload(SWITCHER_PROFILE, NARSINGDI, NARSINGDI))
		# simulate an old invoice that still has the profile default on its
		# non-stock line
		frappe.db.set_value(
			'Sales Invoice Item',
			{'parent': res['name'], 'item_code': self.service_item},
			'warehouse',
			STORE_ROOM,
		)
		frappe.db.set_value('Sales Invoice', res['name'], 'set_warehouse', None)
		detail = get_sales_invoice_detail(res['name'])
		lines = {row['item_code']: row['warehouse'] for row in detail['items']}
		self.assertIsNone(lines[self.service_item])
		self.assertEqual(lines[self.stock_items[0]], NARSINGDI)
		self.assertEqual(detail['warehouse'], NARSINGDI)


class TestApplySaleWarehouse(FrappeTestCase):
	"""Pure rule checks on payload dicts (no documents saved)."""

	def setUp(self):
		self.stock = _pick_stock_items(1)[0]
		self.service = _pick_non_stock_item()

	def _apply(self, doc, warehouse=None):
		from posawesome.posawesome.utils.invoice_warehouse import apply_sale_warehouse

		apply_sale_warehouse(doc, warehouse)
		return {row['item_code']: row['warehouse'] for row in doc['items']}

	def test_flag_on_row_is_ignored_in_favour_of_item_master(self):
		doc = {
			'set_warehouse': NARSINGDI,
			'items': [
				{'item_code': self.stock, 'warehouse': STORE_ROOM, 'is_stock_item': 0},
				{'item_code': self.service, 'warehouse': STORE_ROOM, 'is_stock_item': 1},
			],
		}
		self.assertEqual(self._apply(doc), {self.stock: NARSINGDI, self.service: None})

	def test_no_sale_warehouse_keeps_stock_lines(self):
		"""e.g. a return keeping its original lines' warehouses."""
		doc = {
			'set_warehouse': None,
			'items': [
				{'item_code': self.stock, 'warehouse': DHAKA},
				{'item_code': self.service, 'warehouse': STORE_ROOM},
			],
		}
		self.assertEqual(self._apply(doc), {self.stock: DHAKA, self.service: None})
		self.assertIsNone(doc['set_warehouse'])

	def test_explicit_warehouse_overrides_doc(self):
		doc = {'set_warehouse': STORE_ROOM, 'items': [{'item_code': self.stock, 'warehouse': STORE_ROOM}]}
		self.assertEqual(self._apply(doc, NARSINGDI), {self.stock: NARSINGDI})
		self.assertEqual(doc['set_warehouse'], NARSINGDI)
