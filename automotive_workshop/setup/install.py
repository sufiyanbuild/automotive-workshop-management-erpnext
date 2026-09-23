"""Installation and migration.

Creates configuration only: roles, role profiles, custom fields, permissions,
the KSA VAT templates, the labour service item and Workshop Settings defaults.
No demo data is created here (see automotive_workshop.demo). Existing values are
never overwritten, so a site's own configuration survives every migrate.
"""

import frappe
from frappe import _

from automotive_workshop.setup.custom_fields import setup_custom_fields
from automotive_workshop.setup.dashboard import setup_dashboard
from automotive_workshop.setup.permissions import setup_permissions
from automotive_workshop.setup.roles import create_role_profiles, create_roles

# Proposal requirement: Saudi VAT at 15%. Used only to seed the tax templates;
# after that the templates are the single source of the rate.
KSA_VAT_RATE = 15
VAT_ACCOUNT_NAME = "VAT 15%"
VAT_TEMPLATE_TITLE = "KSA VAT 15%"
LABOUR_ITEM = "WORKSHOP-LABOUR"

DEFAULT_CHECKLISTS = {
	"Denter": ["Front bumper and grille", "Rear bumper", "Bonnet", "Boot lid / tailgate", "Left side panels and doors",
			   "Right side panels and doors", "Roof and pillars", "Paint condition", "Glass and mirrors"],
	"Mechanic": ["Engine oil level and leaks", "Coolant level and hoses", "Belts", "Brakes and brake fluid",
				 "Suspension and steering", "Tyres and wheels", "Exhaust system", "Transmission and clutch",
				 "Road test"],
	"Electrician": ["Battery and charging system", "Starter motor", "Headlamps and tail lamps", "Indicators and hazard lights",
					"Dashboard warning lights", "AC system and blower", "Wipers and washers", "Power windows and locks",
					"Diagnostic scan (fault codes)"],
	"Quality Check": ["Exterior finish and panel gaps", "No warning lights on dashboard", "Fluids topped up",
					  "Road test completed", "Vehicle cleaned", "Customer belongings returned", "Old parts handed over or disposed"],
}


def after_install():
	configure()
	print("Automotive Workshop installed. Review Workshop Settings before use.")


def after_migrate():
	configure()


def configure():
	create_roles()
	create_role_profiles()
	setup_custom_fields()
	setup_permissions()
	company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	if company:
		setup_company_defaults(company)
	setup_dashboard()
	frappe.db.commit()


def setup_company_defaults(company):
	abbr = frappe.get_cached_value("Company", company, "abbr")
	vat_account = ensure_vat_account(company, abbr)
	sales_template = ensure_tax_template("Sales Taxes and Charges Template", company, vat_account)
	ensure_tax_template("Purchase Taxes and Charges Template", company, vat_account)
	labour_item = ensure_labour_item()

	settings = frappe.get_single("Workshop Settings")
	defaults = {
		"company": company,
		"workshop_warehouse": frappe.db.get_value("Warehouse", {"company": company, "warehouse_name": "Stores"}, "name"),
		"labour_item": labour_item,
		"sales_taxes_template": sales_template,
		"selling_price_list": "Standard Selling" if frappe.db.exists("Price List", "Standard Selling") else None,
		"quotation_validity_days": settings.quotation_validity_days or 15,
	}
	for field, value in defaults.items():
		if value and not settings.get(field):
			settings.set(field, value)
	if not settings.checklist_points:
		for inspection_type, points in DEFAULT_CHECKLISTS.items():
			for point in points:
				settings.append("checklist_points", {"inspection_type": inspection_type, "check_point": point})
	settings.flags.ignore_permissions = True
	settings.save()


def ensure_vat_account(company, abbr):
	name = frappe.db.get_value("Account", {"company": company, "account_name": VAT_ACCOUNT_NAME}, "name")
	if name:
		return name
	parent = frappe.db.get_value("Account", {"company": company, "account_name": "Duties and Taxes", "is_group": 1}, "name")
	if not parent:
		return None
	account = frappe.get_doc({
		"doctype": "Account", "account_name": VAT_ACCOUNT_NAME, "company": company, "parent_account": parent,
		"account_type": "Tax", "tax_rate": KSA_VAT_RATE, "root_type": "Liability",
	})
	account.insert(ignore_permissions=True)
	return account.name


def ensure_tax_template(doctype, company, vat_account):
	name = frappe.db.get_value(doctype, {"company": company, "title": VAT_TEMPLATE_TITLE}, "name")
	if name or not vat_account:
		return name
	cost_center = frappe.get_cached_value("Company", company, "cost_center")
	row = {"charge_type": "On Net Total", "account_head": vat_account, "rate": KSA_VAT_RATE,
		   "description": _("VAT {0}%").format(KSA_VAT_RATE), "cost_center": cost_center}
	if doctype.startswith("Purchase"):
		row.update({"category": "Total", "add_deduct_tax": "Add"})
	template = frappe.get_doc({
		"doctype": doctype, "title": VAT_TEMPLATE_TITLE, "company": company,
		"is_default": 1, "taxes": [row],
	})
	template.insert(ignore_permissions=True)
	return template.name


def ensure_labour_item():
	if frappe.db.exists("Item", LABOUR_ITEM):
		return LABOUR_ITEM
	uom = "Hour" if frappe.db.exists("UOM", "Hour") else "Nos"
	group = "Services" if frappe.db.exists("Item Group", "Services") else frappe.db.get_value("Item Group", {"is_group": 0}, "name")
	item = frappe.get_doc({
		"doctype": "Item", "item_code": LABOUR_ITEM, "item_name": "Workshop Labour", "item_group": group,
		"stock_uom": uom, "is_stock_item": 0, "is_sales_item": 1, "is_purchase_item": 0,
		"description": "Workshop labour, billed per hour.",
	})
	item.insert(ignore_permissions=True)
	return item.name
