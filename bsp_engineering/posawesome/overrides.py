import json

import frappe
from frappe.utils import flt

from bsp_engineering.utils.pos_warehouse import (
	can_change_pos_warehouse,
	get_default_company,
	get_permitted_warehouse_names,
	resolve_pos_warehouse,
	validate_warehouse_permission,
)


def _load_pos_profile(pos_profile=None):
	if isinstance(pos_profile, dict):
		return pos_profile
	if isinstance(pos_profile, str) and pos_profile.strip():
		try:
			decoded = json.loads(pos_profile)
			if isinstance(decoded, dict):
				return decoded
		except Exception:
			pass
	try:
		from bsp_engineering.posawesome.profile import get_active_pos_profile

		return get_active_pos_profile() or {}
	except Exception:
		return {}


def _inject_warehouse_into_profile(pos_profile, warehouse):
	if isinstance(pos_profile, str):
		try:
			profile = json.loads(pos_profile)
		except Exception:
			profile = {}
		profile['warehouse'] = warehouse
		return json.dumps(profile)

	if isinstance(pos_profile, dict):
		profile = dict(pos_profile)
		profile['warehouse'] = warehouse
		return profile

	return pos_profile


def _sync_payload_warehouse(payload):
	if not isinstance(payload, dict):
		return

	profile = None
	if payload.get('pos_profile'):
		profile = _load_pos_profile(payload.get('pos_profile'))
	company = payload.get('company') or (profile or {}).get('company')

	if not can_change_pos_warehouse():
		source = resolve_pos_warehouse(company=company, pos_profile=profile)
		if not source:
			return
		payload['set_warehouse'] = source
		for row in payload.get('items') or []:
			row['warehouse'] = source
		for row in payload.get('packed_items') or []:
			row['warehouse'] = source
		return

	source = payload.get('set_warehouse')
	if not source:
		return
	for row in payload.get('items') or []:
		row['warehouse'] = source
	for row in payload.get('packed_items') or []:
		row['warehouse'] = source


def _sync_result_warehouse(result):
	if not isinstance(result, dict):
		return result

	if not can_change_pos_warehouse():
		profile = _load_pos_profile(result.get('pos_profile'))
		source = resolve_pos_warehouse(
			company=result.get('company') or profile.get('company'),
			pos_profile=profile,
		)
		if source:
			result['set_warehouse'] = source
	else:
		source = result.get('set_warehouse')

	if not source:
		return result
	for row in result.get('items') or []:
		if row.get('is_stock_item'):
			row['warehouse'] = source
	for row in result.get('packed_items') or []:
		row['warehouse'] = source
	return result


@frappe.whitelist()
def update_invoice(data):
	import json

	from posawesome.posawesome.api.invoice_processing.creation import (
		update_invoice as _update_invoice,
	)

	payload = json.loads(data) if isinstance(data, str) else (data or {})
	_sync_payload_warehouse(payload)
	result = _update_invoice(
		json.dumps(payload) if isinstance(data, str) else payload
	)
	return _sync_result_warehouse(result)


@frappe.whitelist()
def get_items(
	pos_profile,
	warehouse=None,
	price_list=None,
	item_group='',
	search_value='',
	customer=None,
	limit=None,
	offset=None,
	start_after=None,
	modified_after=None,
	include_description=False,
	include_image=False,
	item_groups=None,
):
	from posawesome.posawesome.api.item_processing.search import (
		get_items as _get_items,
	)

	profile = _load_pos_profile(pos_profile)
	company = profile.get('company') or get_default_company()
	if not can_change_pos_warehouse():
		warehouse = None
	target = warehouse or resolve_pos_warehouse(
		company=company,
		pos_profile=profile,
	)
	if target:
		validate_warehouse_permission(
			target, company=company, pos_profile=profile
		)
		pos_profile = _inject_warehouse_into_profile(pos_profile, target)

	return _get_items(
		pos_profile,
		price_list=price_list,
		item_group=item_group,
		search_value=search_value,
		customer=customer,
		limit=limit,
		offset=offset,
		start_after=start_after,
		modified_after=modified_after,
		include_description=include_description,
		include_image=include_image,
		item_groups=item_groups,
	)


@frappe.whitelist()
def get_default_warehouse(company=None, pos_profile=None):
	profile = _load_pos_profile(pos_profile)
	resolved = resolve_pos_warehouse(
		company=company or profile.get('company'),
		pos_profile=profile,
	)
	if resolved:
		return resolved

	from posawesome.posawesome.api.utils import (
		get_default_warehouse as _orig,
	)

	return _orig(company)


@frappe.whitelist()
def search_items(search_text=None, limit=20, warehouse=None):
	profile = {}
	try:
		from bsp_engineering.posawesome.profile import get_active_pos_profile

		profile = get_active_pos_profile() or {}
	except Exception:
		pass

	company = profile.get('company') or get_default_company()
	warehouse = resolve_pos_warehouse(
		warehouse=warehouse,
		company=company,
		pos_profile=profile,
	)

	permitted = set(
		get_permitted_warehouse_names(company=company, pos_profile=profile)
	)
	if warehouse and warehouse not in permitted:
		frappe.throw(
			frappe._('You do not have permission to use warehouse {0}').format(
				warehouse
			),
			frappe.PermissionError,
		)

	filters = {'disabled': 0}
	or_filters = None
	if search_text:
		like_value = f'%{search_text}%'
		or_filters = {
			'name': ['like', like_value],
			'item_name': ['like', like_value],
		}

	items = frappe.get_all(
		'Item',
		filters=filters,
		or_filters=or_filters,
		fields=['name', 'item_name', 'stock_uom', 'standard_rate'],
		limit_page_length=limit,
		order_by='name asc',
	)
	item_codes = [it.get('name') for it in items if it.get('name')]
	uom_rows = []
	bin_rows = []
	if item_codes:
		uom_rows = frappe.get_all(
			'UOM Conversion Detail',
			filters={'parent': ['in', item_codes]},
			fields=['parent', 'uom', 'conversion_factor'],
		)
		bin_filters = {'item_code': ['in', item_codes]}
		if warehouse:
			bin_filters['warehouse'] = warehouse
		elif permitted:
			bin_filters['warehouse'] = ['in', list(permitted)]

		bin_rows = frappe.get_all(
			'Bin',
			filters=bin_filters,
			fields=['item_code', 'actual_qty'],
		)

	uom_map = {}
	for row in uom_rows:
		uom_map.setdefault(row.parent, []).append(
			{'uom': row.uom, 'conversion_factor': row.conversion_factor}
		)

	qty_map = {}
	for row in bin_rows:
		qty_map[row.item_code] = qty_map.get(row.item_code, 0) + flt(
			row.actual_qty
		)

	results = []
	for it in items:
		item_code = it.get('name')
		stock_uom = it.get('stock_uom')
		uoms = uom_map.get(item_code, [])
		if stock_uom and not any(u.get('uom') == stock_uom for u in uoms):
			uoms.append({'uom': stock_uom, 'conversion_factor': 1})
		results.append(
			{
				'item_code': item_code,
				'item_name': it.get('item_name'),
				'stock_uom': stock_uom,
				'item_uoms': uoms,
				'standard_rate': it.get('standard_rate'),
				'actual_qty': qty_map.get(item_code, 0),
			}
		)
	return results


@frappe.whitelist()
def create_purchase_invoice(data):
	from posawesome.posawesome.api import purchase_orders as po
	from posawesome.posawesome.api.utils import _resolve_pos_profile

	payload = json.loads(data) if isinstance(data, str) else (data or {})
	profile = _resolve_pos_profile(payload.get('pos_profile')) or {}
	company = (
		payload.get('company')
		or profile.get('company')
		or get_default_company()
	)
	warehouse = payload.get('warehouse')
	if not can_change_pos_warehouse():
		warehouse = None
	if warehouse:
		validate_warehouse_permission(
			warehouse, company=company, pos_profile=profile
		)
	else:
		warehouse = resolve_pos_warehouse(
			company=company,
			pos_profile=profile,
		)
		if warehouse:
			payload = dict(payload)
			payload['warehouse'] = warehouse

	if warehouse:
		payload = dict(payload)
		payload['warehouse'] = warehouse
		for row in payload.get('items') or []:
			row['warehouse'] = warehouse

	return po._create_purchase_invoice_from_pos(payload)
