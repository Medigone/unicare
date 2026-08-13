app_name = "unicare"
app_title = "Unicare"
app_publisher = "Intrapro"
app_description = "Unicare"
app_email = "admin@medigo.one"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "unicare",
# 		"logo": "/assets/unicare/logo.png",
# 		"title": "Unicare",
# 		"route": "/unicare",
# 		"has_permission": "unicare.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/unicare/css/ordre_conditionnement.css"
# app_include_js = "/assets/unicare/js/unicare.js"

# include js, css files in header of web template
# web_include_css = "/assets/unicare/css/unicare.css"
# web_include_js = "/assets/unicare/js/unicare.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "unicare/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Customer": "public/js/customer_contacts.js",
	"Supplier": "public/js/supplier_contacts.js",
	"Item": "public/js/item.js",
	"Purchase Receipt": "conditionnement/purchase_receipt.js",
}
doctype_list_js = {
	"Supplier": "public/js/supplier_list.js",
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "unicare/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
home_page = "unicare"

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
# 	"methods": "unicare.utils.jinja_methods",
# 	"filters": "unicare.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "unicare.install.before_install"
# after_install = "unicare.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "unicare.uninstall.before_uninstall"
# after_uninstall = "unicare.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "unicare.utils.before_app_install"
# after_app_install = "unicare.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "unicare.utils.before_app_uninstall"
# after_app_uninstall = "unicare.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "unicare.notifications.get_notification_config"

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
	"Customer": "unicare.customer_hooks.CustomCustomer",
	"Supplier": "unicare.supplier_hooks.CustomSupplier",
	"Item": "unicare.conditionnement.item_hooks.CustomItem",
}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"unicare.tasks.all"
# 	],
# 	"daily": [
# 		"unicare.tasks.daily"
# 	],
# 	"hourly": [
# 		"unicare.tasks.hourly"
# 	],
# 	"weekly": [
# 		"unicare.tasks.weekly"
# 	],
# 	"monthly": [
# 		"unicare.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "unicare.install.before_tests"

# Overriding Methods
# ------------------------------

override_whitelisted_methods = {
	"erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts.get_charts_for_country": (
		"unicare.chart_of_accounts.patch.get_charts_for_country"
	),
	"erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts.get_chart": (
		"unicare.chart_of_accounts.patch.get_chart"
	),
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "unicare.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["unicare.utils.before_request"]
# after_request = ["unicare.utils.after_request"]

# Job Events
# ----------
# before_job = ["unicare.utils.before_job"]
# after_job = ["unicare.utils.after_job"]

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
# 	"unicare.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

doc_events = {
	"Item": {
		"validate": "unicare.conditionnement.item_hooks.validate_item",
	},
	"Purchase Receipt": {
		"before_submit": "unicare.conditionnement.purchase_receipt_hooks.before_submit",
	},
}

fixtures = [
	"Wilaya",
	"Commune",
	"Custom HTML Block",
	{
		"dt": "Role",
		"filters": [
			[
				"name",
				"in",
				[
					"Magasinier Conditionnement",
					"Opérateur Conditionnement",
					"Responsable Conditionnement",
				],
			]
		],
	},
	{
		"dt": "Workflow State",
		"filters": [
			["name", "in", ["Brouillon", "Préparé", "En production", "Terminé", "Annulé"]]
		],
	},
	{
		"dt": "Workflow Action Master",
		"filters": [
			[
				"name",
				"in",
				["Préparer", "Démarrer la production", "Clôturer", "Annuler"],
			]
		],
	},
	{
		"dt": "Workflow",
		"filters": [["name", "=", "Ordre de Conditionnement"]],
	},
]

