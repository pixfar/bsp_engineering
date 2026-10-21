"""ERPNext's standard Stock Balance report, with rows in BSP's official
item-category order -- the same order every BSP custom report uses
(bsp_engineering.utils.item_category_sort). ERPNext's own files stay
untouched: Frappe resolves a report's `execute` by dotted path on every run
(frappe.get_attr), so the module attribute is wrapped instead. Installed from
the before_request / before_job hooks (Stock Balance is a prepared report,
so it usually runs in a background job)."""

from bsp_engineering.utils.item_category_sort import get_item_sort_map, sort_rows_by_item_category


def install():
	from erpnext.stock.report.stock_balance import stock_balance

	if getattr(stock_balance.execute, "_bsp_item_category_sorted", False):
		return

	original_execute = stock_balance.execute

	def execute(filters=None):
		result = original_execute(filters)
		if not isinstance(result, (list, tuple)) or len(result) < 2 or not result[1]:
			return result
		data = sort_rows_by_item_category(list(result[1]), get_item_sort_map())
		return (result[0], data, *result[2:])

	execute._bsp_item_category_sorted = True
	stock_balance.execute = execute
