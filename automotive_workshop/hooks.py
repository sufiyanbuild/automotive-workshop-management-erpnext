app_name = "automotive_workshop"
app_title = "Automotive Workshop Management"
app_publisher = "Sufiyan Shaikh"
app_description = "Automotive workshop management on ERPNext: job cards, inspections, parts, repair, quality and billing"
app_email = "sufiyanshaikh1414@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

after_install = "automotive_workshop.setup.install.after_install"
after_migrate = "automotive_workshop.setup.install.after_migrate"

app_include_js = "workshop.bundle.js"
app_include_css = "workshop.bundle.css"

doctype_js = {
	"Quotation": "public/js/quotation.js",
	"Sales Invoice": "public/js/workshop_reference.js",
	"Material Request": "public/js/workshop_reference.js",
	"Stock Entry": "public/js/workshop_reference.js",
	"Payment Entry": "public/js/workshop_reference.js",
	"Task": "public/js/task.js",
}

WORKSHOP_ROLES = [
	"Reception", "Workshop Manager", "Denter", "Mechanic", "Electrician",
	"Quality Inspector", "Purchase Department", "Store Keeper", "Accounts Department",
]

fixtures = [
	{"dt": "Role", "filters": [["name", "in", WORKSHOP_ROLES]]},
	{"dt": "Custom Field", "filters": [["fieldname", "like", "aw_%"]]},
	{"dt": "Role Profile", "filters": [["name", "like", "Workshop %"]]},
]

doc_events = {
	"Quotation": {
		"validate": "automotive_workshop.events.quotation.validate",
		"before_submit": "automotive_workshop.events.quotation.before_submit",
		"on_submit": "automotive_workshop.events.quotation.on_submit",
		"before_update_after_submit": "automotive_workshop.events.quotation.before_update_after_submit",
		"before_cancel": "automotive_workshop.events.quotation.before_cancel",
		"on_cancel": "automotive_workshop.events.quotation.on_cancel",
	},
	"Sales Invoice": {
		"validate": "automotive_workshop.events.sales_invoice.validate",
		"before_submit": "automotive_workshop.events.sales_invoice.before_submit",
		"on_submit": "automotive_workshop.events.sales_invoice.on_submit",
		"before_cancel": "automotive_workshop.events.sales_invoice.before_cancel",
		"on_cancel": "automotive_workshop.events.sales_invoice.on_cancel",
		"on_update_after_submit": "automotive_workshop.events.sales_invoice.on_update_after_submit",
	},
	"Payment Entry": {
		"validate": "automotive_workshop.events.payment_entry.validate",
		"on_change": "automotive_workshop.events.payment_entry.on_change",
	},
	"Task": {
		"validate": "automotive_workshop.events.task.validate",
		"on_update": "automotive_workshop.events.task.on_update",
	},
	"Material Request": {"validate": "automotive_workshop.events.buying.validate_material_request"},
	"Request for Quotation": {"validate": "automotive_workshop.events.buying.trace_items"},
	"Supplier Quotation": {"validate": "automotive_workshop.events.buying.trace_items"},
	"Purchase Order": {"validate": "automotive_workshop.events.buying.trace_items"},
	"Purchase Receipt": {"validate": "automotive_workshop.events.buying.trace_items"},
	"Stock Entry": {
		"validate": "automotive_workshop.events.stock_entry.validate",
		"before_submit": "automotive_workshop.events.stock_entry.before_submit",
	},
	"Communication": {"after_insert": "automotive_workshop.events.communication.after_insert"},
}

permission_query_conditions = {
	"Workshop Job Card": "automotive_workshop.workshop.permissions.job_card_query",
	"Vehicle Inspection": "automotive_workshop.workshop.permissions.inspection_query",
	"Damage Assessment": "automotive_workshop.workshop.permissions.assessment_query",
	"Task": "automotive_workshop.workshop.permissions.task_query",
}

has_permission = {
	"Workshop Job Card": "automotive_workshop.workshop.permissions.job_card_has_permission",
	"Vehicle Inspection": "automotive_workshop.workshop.permissions.inspection_has_permission",
	"Damage Assessment": "automotive_workshop.workshop.permissions.assessment_has_permission",
	"Task": "automotive_workshop.workshop.permissions.task_has_permission",
}

override_doctype_dashboards = {
	"Customer": "automotive_workshop.events.customer.get_dashboard_data",
}
