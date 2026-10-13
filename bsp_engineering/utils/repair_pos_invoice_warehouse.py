"""Repair submitted POS Sales Invoices whose lines used the wrong warehouse.

Background: until the invoice_warehouse fix, a warehouse-switching user's sale
could post stock from the POS Profile's default warehouse ("Store Room - BSP")
instead of the warehouse they selected, the invoice's own set_warehouse could
be blanked, and non-stock lines carried the profile's warehouse.

For each affected invoice the intended warehouse is taken from the evidence
the invoice itself recorded at sale time, and only used when every signal
agrees:

* ``set_warehouse`` (when not blanked),
* ``territory`` -- set from the selected warehouse on every save,
* the one non-default warehouse among its stock lines (lines added after the
  switch kept the right warehouse),
* the warehouse whose Cash / Bank Account received the payment (Payment
  Entries are never changed by this tool -- if the money went to a different
  warehouse than the evidence above, the invoice is left for manual review).

A warehouse decided by a person can be applied to specific invoices with
``invoices=[...]`` plus ``warehouse='...'``; it is still refused when the
payment was booked to another warehouse's account.

Anything ambiguous is reported for manual review and never touched.

Fixing an invoice:

* stock lines in the wrong warehouse -> its stock postings are reversed with
  ERPNext's own logic, the lines are corrected, the stock is posted again,
  and a standard Repost Item Valuation recalculates valuation and GL for both
  warehouses from the invoice date onward;
* non-stock lines -> warehouse cleared (no ledger impact);
* blank set_warehouse -> restored.

Each fixed invoice gets a Comment listing exactly what changed.

Usage (always dry-run first):

	bench --site <site> execute bsp_engineering.utils.repair_pos_invoice_warehouse.report
	bench --site <site> execute bsp_engineering.utils.repair_pos_invoice_warehouse.repair \
		--kwargs "{'dry_run': 0}"

Optional kwargs for both: from_date, to_date, invoices (list of names).
"""

import json

import frappe
from frappe.utils import cint, flt

REPAIR_TAG = 'POS warehouse repair'


def _territory_warehouse_map(company):
	"""{territory: warehouse} for territories that map to exactly one warehouse."""
	from posawesome.posawesome.api.invoice_processing.creation import (
		_resolve_territory_for_warehouse,
	)

	by_territory = {}
	for warehouse in frappe.get_all(
		'Warehouse', filters={'company': company, 'is_group': 0}, pluck='name'
	):
		territory = _resolve_territory_for_warehouse(warehouse)
		if territory:
			by_territory.setdefault(territory, set()).add(warehouse)
	return {t: w.pop() for t, w in by_territory.items() if len(w) == 1}


def _payment_cash_accounts(invoice):
	"""The company-side cash/bank account of every submitted Payment Entry
	against this invoice (paid_to on a receipt, paid_from on a refund)."""
	return frappe.db.sql(
		"""
		SELECT DISTINCT IF(pe.payment_type = 'Receive', pe.paid_to, pe.paid_from)
		FROM `tabPayment Entry` pe
		JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
		WHERE per.reference_doctype = 'Sales Invoice' AND per.reference_name = %s
			AND pe.docstatus = 1
		""",
		invoice,
		pluck=True,
	)


def _candidate_invoices(from_date=None, to_date=None, invoices=None):
	conditions = ['si.docstatus = 1', "IFNULL(si.pos_profile, '') != ''", 'si.is_return = 0']
	values = {}
	if from_date:
		conditions.append('si.posting_date >= %(from_date)s')
		values['from_date'] = from_date
	if to_date:
		conditions.append('si.posting_date <= %(to_date)s')
		values['to_date'] = to_date
	if invoices:
		if isinstance(invoices, str):
			invoices = json.loads(invoices) if invoices.startswith('[') else [invoices]
		conditions.append('si.name IN %(invoices)s')
		values['invoices'] = tuple(invoices)

	return frappe.db.sql(
		f"""
		SELECT DISTINCT si.name
		FROM `tabSales Invoice` si
		JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		JOIN `tabItem` i ON i.name = sii.item_code
		WHERE {' AND '.join(conditions)}
			AND (
				IFNULL(si.set_warehouse, '') = ''
				OR (i.is_stock_item = 1 AND sii.warehouse != si.set_warehouse)
				OR (i.is_stock_item = 0 AND IFNULL(sii.warehouse, '') != '')
				OR EXISTS (
					SELECT 1 FROM `tabPayment Entry` pe
					JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
					WHERE per.reference_doctype = 'Sales Invoice' AND per.reference_name = si.name
						AND pe.docstatus = 1
						AND NOT EXISTS (
							SELECT 1 FROM `tabWarehouse Cash Account` wca
							WHERE wca.parenttype = 'Warehouse' AND wca.parent = si.set_warehouse
								AND wca.account = IF(pe.payment_type = 'Receive', pe.paid_to, pe.paid_from)
						)
				)
			)
		ORDER BY si.posting_date, si.name
		""",
		values,
		pluck=True,
	)


def plan_invoice(name, territory_map=None, account_map=None, warehouse=None):
	"""Work out what needs to change on one invoice. Never writes.

	``warehouse``: a warehouse decided by a person for this invoice.
	"""
	from bsp_engineering.utils.warehouse_accounts import get_warehouse_by_account_map

	doc = frappe.get_doc('Sales Invoice', name)
	territory_map = territory_map if territory_map is not None else _territory_warehouse_map(doc.company)
	account_map = account_map if account_map is not None else get_warehouse_by_account_map(doc.company)
	profile_default = frappe.db.get_value('POS Profile', doc.pos_profile, 'warehouse')
	stock_flags = {
		row.name: cint(row.is_stock_item)
		for row in frappe.get_all(
			'Item',
			filters={'name': ['in', list({r.item_code for r in doc.items})]},
			fields=['name', 'is_stock_item'],
		)
	}

	stock_rows = [r for r in doc.items if stock_flags.get(r.item_code)]
	non_stock_rows = [r for r in doc.items if not stock_flags.get(r.item_code)]
	other_warehouses = {r.warehouse for r in stock_rows if r.warehouse and r.warehouse != profile_default}

	signals = {}
	if doc.set_warehouse:
		signals['set_warehouse'] = doc.set_warehouse
	if territory_map.get(doc.territory):
		signals['territory'] = territory_map[doc.territory]
	if len(other_warehouses) == 1:
		signals['other stock line'] = next(iter(other_warehouses))
	elif len(other_warehouses) > 1:
		signals['other stock lines'] = ', '.join(sorted(other_warehouses))
	cash_accounts = _payment_cash_accounts(name)
	cash_warehouses = {account_map.get(account) or f'(unmapped account {account})' for account in cash_accounts}
	if len(cash_warehouses) == 1:
		signals['payment account'] = next(iter(cash_warehouses))
	elif len(cash_warehouses) > 1:
		signals['payment accounts'] = ', '.join(sorted(cash_warehouses))

	plan = frappe._dict(
		name=name,
		posting_date=str(doc.posting_date),
		owner=doc.owner,
		pos_profile=doc.pos_profile,
		signals=signals,
		intended=None,
		stock_moves=[],
		clear_non_stock=[r.item_code for r in non_stock_rows if r.warehouse],
		restore_set_warehouse=False,
		set_account=None,
		# "Update Stock" off: the invoice posted no stock, lines are only labels
		repost=bool(cint(doc.update_stock)),
		status='ok',
		reason='',
	)

	if warehouse:
		plan.signals = {**signals, 'decided by user': warehouse}
		cash = {v for k, v in signals.items() if k.startswith('payment account')}
		if cash and cash != {warehouse}:
			plan.status = 'manual'
			plan.reason = 'payment was booked to another warehouse account; fix the Payment Entry first'
			return plan
		intended = warehouse
	else:
		distinct = set(signals.values())
		if len(distinct) != 1:
			plan.status = 'manual'
			plan.reason = 'warehouse evidence missing or conflicting'
			return plan
		intended = distinct.pop()
	plan.intended = intended
	plan.restore_set_warehouse = doc.set_warehouse != intended
	# Payment account labels on the invoice itself must name the account the
	# Payment Entry actually used (Payment Entries are not touched).
	if len(cash_accounts) == 1:
		account = cash_accounts[0]
		if doc.get('payment_account') != account or any(
			row.account != account for row in doc.get('custom_payment_method_split') or []
		):
			plan.set_account = account
	plan.stock_moves = [
		{'row': r.name, 'item_code': r.item_code, 'qty': flt(r.qty), 'from': r.warehouse, 'to': intended}
		for r in stock_rows
		if r.warehouse != intended
	]

	if plan.stock_moves and plan.repost:
		# Only repost when the existing stock postings match the lines exactly,
		# so reversing them with the document's own logic is exact.
		posted = {}
		for sle in frappe.get_all(
			'Stock Ledger Entry',
			filters={'voucher_type': 'Sales Invoice', 'voucher_no': name, 'is_cancelled': 0},
			fields=['item_code', 'warehouse', 'actual_qty'],
		):
			key = (sle.item_code, sle.warehouse)
			posted[key] = posted.get(key, 0) + flt(sle.actual_qty)
		expected = {}
		for r in stock_rows:
			key = (r.item_code, r.warehouse)
			expected[key] = expected.get(key, 0) - flt(r.stock_qty)
		if {k: round(v, 6) for k, v in posted.items()} != {k: round(v, 6) for k, v in expected.items()}:
			plan.status = 'manual'
			plan.reason = 'existing stock ledger entries do not match the invoice lines'

	if not (plan.stock_moves or plan.clear_non_stock or plan.restore_set_warehouse or plan.set_account):
		plan.status = 'nothing to do'
	return plan


def _print_plan(plan):
	head = f"{plan.name} {plan.posting_date} [{plan.status}]"
	if plan.reason:
		head += f' - {plan.reason}'
	print(head)
	print(f"    evidence: {plan.signals}")
	if plan.intended:
		print(f"    intended warehouse: {plan.intended}")
	for move in plan.stock_moves:
		label = 'stock' if plan.repost else 'line label (Update Stock off, no stock posted)'
		print(f"    {label}: {move['item_code']} x{move['qty']:g}  {move['from']} -> {move['to']}")
	if plan.clear_non_stock:
		print(f"    clear warehouse on non-stock lines: {', '.join(plan.clear_non_stock)}")
	if plan.restore_set_warehouse:
		print(f"    restore invoice warehouse -> {plan.intended}")
	if plan.set_account:
		print(f"    invoice payment account labels -> {plan.set_account} (as on its Payment Entry)")


def report(from_date=None, to_date=None, invoices=None, warehouse=None):
	"""Dry run: print the plan for every affected invoice. Writes nothing."""
	return _summary(_report(from_date, to_date, invoices, warehouse))


def _report(from_date=None, to_date=None, invoices=None, warehouse=None):
	from bsp_engineering.utils.warehouse_accounts import get_warehouse_by_account_map

	if warehouse and not invoices:
		frappe.throw('warehouse can only be given together with specific invoices')
	names = _candidate_invoices(from_date, to_date, invoices)
	company = frappe.db.get_value('Sales Invoice', names[0], 'company') if names else None
	territory_map = _territory_warehouse_map(company)
	account_map = get_warehouse_by_account_map(company)
	plans = [plan_invoice(name, territory_map, account_map, warehouse) for name in names]
	for plan in plans:
		_print_plan(plan)
	_print_summary(plans)
	return plans


def _summary(plans):
	counts = {}
	for plan in plans:
		key = plan.status
		if plan.status == 'ok':
			key = 'ok (stock repost)' if plan.stock_moves and plan.repost else 'ok (no ledger impact)'
		counts[key] = counts.get(key, 0) + 1
	return counts


def _print_summary(plans):
	print('\nSummary:', json.dumps(_summary(plans), indent=1))


def _apply(plan):
	doc = frappe.get_doc('Sales Invoice', plan.name)
	repost = bool(plan.stock_moves) and plan.repost

	if repost:
		# 1. reverse the existing stock postings (exactly what cancel does)
		doc.docstatus = 2
		doc.update_stock_ledger(allow_negative_stock=True)

	# 2. correct the lines
	moved = {m['row']: m['to'] for m in plan.stock_moves}
	for row in doc.items:
		if row.name in moved:
			frappe.db.set_value('Sales Invoice Item', row.name, 'warehouse', moved[row.name], update_modified=False)
		elif row.item_code in plan.clear_non_stock:
			frappe.db.set_value('Sales Invoice Item', row.name, 'warehouse', None, update_modified=False)
	if plan.restore_set_warehouse:
		frappe.db.set_value('Sales Invoice', plan.name, 'set_warehouse', plan.intended, update_modified=False)
	if plan.set_account:
		frappe.db.set_value('Sales Invoice', plan.name, 'payment_account', plan.set_account, update_modified=False)
		for row in doc.get('custom_payment_method_split') or []:
			frappe.db.set_value('Sales Invoice Payment Split', row.name, 'account', plan.set_account, update_modified=False)

	if repost:
		# 3. post stock again from the corrected lines
		doc = frappe.get_doc('Sales Invoice', plan.name)
		doc.update_stock_ledger(allow_negative_stock=True)

		# 4. standard ERPNext revaluation of both warehouses from this date,
		#    which also regenerates the GL (COGS / stock) of every affected voucher
		from erpnext.controllers.stock_controller import create_repost_item_valuation_entry

		create_repost_item_valuation_entry(
			{
				'based_on': 'Transaction',
				'voucher_type': 'Sales Invoice',
				'voucher_no': plan.name,
				'posting_date': doc.posting_date,
				'posting_time': doc.posting_time,
				'company': doc.company,
				'allow_zero_rate': 0,
			}
		)

	lines = [f'{REPAIR_TAG}: intended warehouse {plan.intended} (evidence: {plan.signals}).']
	lines += [f"Stock line {m['item_code']} x{m['qty']:g}: {m['from']} -> {m['to']}" for m in plan.stock_moves]
	if plan.clear_non_stock:
		lines.append('Warehouse cleared on non-stock lines: ' + ', '.join(plan.clear_non_stock))
	if plan.restore_set_warehouse:
		lines.append(f'Invoice warehouse restored to {plan.intended}')
	if plan.set_account:
		lines.append(f'Invoice payment account labels set to {plan.set_account} (as on its Payment Entry)')
	doc.add_comment('Comment', '<br>'.join(frappe.utils.escape_html(line) for line in lines))


def repair(from_date=None, to_date=None, invoices=None, dry_run=1, warehouse=None):
	"""Fix every invoice whose plan is 'ok'. dry_run=1 (default) only reports.

	Each invoice is committed on its own; a failure rolls back that invoice
	only and is reported.
	"""
	plans = _report(from_date, to_date, invoices, warehouse)
	if cint(dry_run):
		print('\nDry run only -- nothing changed. Re-run with dry_run=0 to apply.')
		return _summary(plans)

	results = {'fixed': [], 'failed': [], 'skipped': []}
	for plan in plans:
		if plan.status != 'ok':
			results['skipped'].append(plan.name)
			continue
		try:
			_apply(plan)
			frappe.db.commit()
			results['fixed'].append(plan.name)
		except Exception:
			frappe.db.rollback()
			results['failed'].append(plan.name)
			frappe.log_error(title=f'{REPAIR_TAG} failed: {plan.name}')
			print(f'FAILED {plan.name}:\n{frappe.get_traceback()}')

	print('\nResult:', json.dumps({k: len(v) for k, v in results.items()}))
	if results['failed']:
		print('Failed:', ', '.join(results['failed']))
	return {k: len(v) for k, v in results.items()}
