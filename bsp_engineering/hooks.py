app_name = "bsp_engineering"
app_title = "Bsp Engineering"
app_publisher = "Pixfar"
app_description = "A app for BSP Engineering Works"
app_email = "query@pixfar.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Custom CSS

app_include_css = "/assets/bsp_engineering/css/theme.css"

# Fixtures 

fixtures = [
	{
        "dt": "Workspace",
        "filters": [
            [
                "name",
                "in",
                [
                    "BSP",
                    "My Workspace",
                ],
            ]
        ],
    },
    { "dt": "Custom Field" },
    { "dt": "Property Setter" },
    { "dt": "Client Script" },
    { "dt": "Print Format" },
    { "dt": "Workflow State" },
    { "dt": "Workflow" },
]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "bsp_engineering",
# 		"logo": "/assets/bsp_engineering/logo.png",
# 		"title": "Bsp Engineering",
# 		"route": "/bsp_engineering",
# 		"has_permission": "bsp_engineering.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/bsp_engineering/css/bsp_engineering.css"
# app_include_js = "/assets/bsp_engineering/js/bsp_engineering.js"

# include js, css files in header of web template
# web_include_css = "/assets/bsp_engineering/css/bsp_engineering.css"
# web_include_js = "/assets/bsp_engineering/js/bsp_engineering.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "bsp_engineering/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
page_js = {
	'print': 'public/js/bsp_print.js',
}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {
	"Purchase Invoice": "public/js/purchase_invoice.js",
	"Sales Invoice": "public/js/sales_invoice.js",
	"Material Request": "public/js/material_request.js",
	"Delivery Note": "public/js/delivery_note.js",
	"Requisition": "bsp_engineering/doctype/requisition/requisition.js",
	"Material Transfer": "bsp_engineering/doctype/material_transfer/material_transfer.js",
}
doctype_list_js = {
	"Purchase Invoice": "public/js/purchase_invoice_list.js",
	"Sales Invoice": "public/js/sales_invoice_list.js",
	"Requisition": "public/js/requisition_list.js",
	"Material Transfer": "public/js/material_transfer_list.js",
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "bsp_engineering/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "bsp_engineering.utils.jinja_methods",
# 	"filters": "bsp_engineering.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "bsp_engineering.install.before_install"
# after_install = "bsp_engineering.install.after_install"
before_migrate = [
	'bsp_engineering.compat.erpnext_party.apply_compat_patches',
]

# Uninstallation
# ------------

# before_uninstall = "bsp_engineering.uninstall.before_uninstall"
# after_uninstall = "bsp_engineering.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "bsp_engineering.utils.before_app_install"
# after_app_install = "bsp_engineering.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "bsp_engineering.utils.before_app_uninstall"
# after_app_uninstall = "bsp_engineering.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bsp_engineering.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	'Production Plan': 'bsp_engineering.overrides.production_plan.ProductionPlan',
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	'*': {
		'on_update': 'bsp_engineering.doc_events.auto_submit.auto_submit_after_save',
	},
	'Item': {
		'before_validate': (
			'bsp_engineering.doc_events.item.auto_barcode.ensure_auto_barcode'
		),
		'after_insert': (
			'bsp_engineering.doc_events.item.auto_barcode.sync_item_barcode_image'
		),
		'on_update': (
			'bsp_engineering.doc_events.item.auto_barcode.sync_item_barcode_image'
		),
	},
	'Sales Invoice': {
		'validate': [
			'bsp_engineering.doc_events.sales_invoice.return_naming_series.enforce_return_naming_series',
			'bsp_engineering.doc_events.invoice.sync_line_warehouse.sync_line_warehouse_from_source',
		],
		'on_submit': (
			'bsp_engineering.doc_events.sales_invoice.create_payment.create_payment_entry_from_sales_invoice'
		),
		'before_cancel': (
			'bsp_engineering.doc_events.invoice.cancel_linked_payments.cancel_linked_payment_entries'
		),
		'on_cancel': (
			'bsp_engineering.doc_events.sales_invoice.sync_workflow_on_cancel.sync_workflow_state_on_cancel'
		),
	},
	'POS Invoice': {
		'validate': (
			'bsp_engineering.doc_events.invoice.sync_line_warehouse'
			'.sync_line_warehouse_from_source'
		),
	},
	'Purchase Invoice': {
		'validate': (
			'bsp_engineering.doc_events.invoice.sync_line_warehouse'
			'.sync_line_warehouse_from_source'
		),
		'on_submit': [
			'bsp_engineering.doc_events.purchase_invoice.create_payment.create_payment_entry_from_purchase_invoice',
			'bsp_engineering.doc_events.purchase_invoice.update_delivery_status.update_delivery_status',
		],
		'on_update_after_submit': (
			'bsp_engineering.doc_events.purchase_invoice.update_delivery_status.update_delivery_status'
		),
		'before_cancel': (
			'bsp_engineering.doc_events.invoice.cancel_linked_payments.cancel_linked_payment_entries'
		),
	},
	# 'Delivery Note': {
	# 	'on_submit': (
	# 		'bsp_engineering.doc_events.delivery_note.send_stock_notification.send_stock_notification_on_submit'
	# 	),
	# },
	'Stock Entry': {
		'after_insert': [
			'bsp_engineering.doc_events.stock_entry.update_requisition_status.sync_requisition_transfer_status',
		],
		'on_submit': [
			'bsp_engineering.doc_events.stock_entry.workflow_manufacture.apply_manufacture_workflow_state',
			'bsp_engineering.doc_events.stock_entry.update_requisition_status.sync_requisition_transfer_status',
		],
		'on_cancel': [
			'bsp_engineering.doc_events.stock_entry.update_requisition_status.sync_requisition_transfer_status',
		],
		'before_workflow_action': (
			'bsp_engineering.doc_events.stock_entry.workflow_guard.guard_confirm_receipt'
		),
	},
	'Production Plan': {
		'on_update': (
			'bsp_engineering.doc_events.production_plan.auto_workflow.on_update'
		),
		'on_submit': (
			'bsp_engineering.doc_events.production_plan.auto_workflow.on_submit'
		),
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	'cron': {
		'*/15 * * * *': [
			'bsp_engineering.utils.schedule_task.send_low_stock_alert_report'
		]
	}
}

# Testing
# -------

# before_tests = "bsp_engineering.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	'posawesome.posawesome.api.items.get_items': (
		'bsp_engineering.posawesome.overrides.get_items'
	),
	'posawesome.posawesome.api.items.get_items_details': (
		'bsp_engineering.posawesome.overrides.get_items_details'
	),
	'posawesome.posawesome.api.items.get_item_detail': (
		'bsp_engineering.posawesome.overrides.get_item_detail'
	),
	'posawesome.posawesome.api.items.get_delta_items': (
		'bsp_engineering.posawesome.overrides.get_delta_items'
	),
	'posawesome.posawesome.api.purchase_invoices.search_items': (
		'bsp_engineering.posawesome.overrides.search_items'
	),
	'posawesome.posawesome.api.utils.get_default_warehouse': (
		'bsp_engineering.posawesome.overrides.get_default_warehouse'
	),
	'posawesome.posawesome.api.utils.get_active_pos_profile': (
		'bsp_engineering.posawesome.profile.get_active_pos_profile'
	),
	'posawesome.posawesome.api.shifts.check_opening_shift': (
		'bsp_engineering.posawesome.profile.check_opening_shift'
	),
	'posawesome.posawesome.api.purchase_invoices.create_purchase_invoice': (
		'bsp_engineering.posawesome.overrides.create_purchase_invoice'
	),
	'posawesome.posawesome.api.invoice_processing.creation.update_invoice': (
		'bsp_engineering.posawesome.overrides.update_invoice'
	),
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	'Requisition': (
		'bsp_engineering.bsp_engineering.doctype.requisition'
		'.requisition_dashboard.get_data'
	),
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["bsp_engineering.utils.before_request"]
# after_request = ["bsp_engineering.utils.after_request"]

# Job Events
# ----------
# before_job = ["bsp_engineering.utils.before_job"]
# after_job = ["bsp_engineering.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"bsp_engineering.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

