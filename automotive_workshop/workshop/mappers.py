"""Prefilled document creation from a Workshop Job Card (the Create menu).

Each method is called through frappe.model.open_mapped_doc, so it receives the
Job Card name as `source_name` and any extra arguments in `frappe.flags.args`.
Each re-checks the menu rules before returning an unsaved, prefilled document.
"""

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_days, flt, nowdate

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle as L
from automotive_workshop.workshop import menus
from automotive_workshop.workshop.settings import get_company, get_settings, require_setting


def _args():
	return frappe.flags.args or frappe._dict()


def _load(source_name, key):
	job = frappe.get_doc("Workshop Job Card", source_name)
	job.check_permission("read")
	menus.assert_can_create(key)
	facts = L.get_facts(job)
	available = menus.build(job, facts, get_settings())
	if key not in {c.key for c in available.create}:
		frappe.throw(
			_("{0} cannot be created from Job Card {1} while it is {2}.").format(
				_(menus.CREATE_DOCTYPES[key]), job.name, _(job.status)),
			L.WorkflowError, title=_("Not Available at This Stage"),
		)
	return job, facts


# get_mapped_doc copies same-named fields across, which would carry the Job Card's
# own naming series (JC-.YYYY.-) onto the new document and name inspections JC-...
NEVER_MAP = ["naming_series", "status", "amended_from", "company", "currency", "priority", "title"]


def _from_job(job, doctype, field_map, postprocess=None):
	return get_mapped_doc(
		"Workshop Job Card", job.name,
		{"Workshop Job Card": {
			"doctype": doctype, "field_map": field_map, "field_no_map": NEVER_MAP, "validation": {},
		}},
		postprocess=postprocess, ignore_permissions=True,
	)


def _checklist_points(inspection_type):
	return [p.check_point for p in get_settings().checklist_points if p.inspection_type == inspection_type]


@frappe.whitelist()
def make_vehicle_inspection(source_name, target_doc=None):
	args = _args()
	qc = args.get("inspection_type") == C.QC_TYPE or args.get("qc_result")
	job, facts = _load(source_name, "quality_check" if qc else "inspection")

	def postprocess(source, target):
		target.inspection_type = C.QC_TYPE if qc else (args.get("inspection_type") or _default_trade())
		target.technician = args.get("technician") or frappe.session.user
		target.inspection_datetime = frappe.utils.now_datetime()
		points = _checklist_points(target.inspection_type)
		if qc:
			target.qc_result = args.get("qc_result")
			points = [_("Verify repair: {0}").format(t.subject) for t in facts.tasks] + points
		for point in points:
			target.append("checklist", {"check_point": point})

	return _from_job(job, "Vehicle Inspection", {"name": "job_card"}, postprocess)


def _default_trade():
	roles = frappe.get_roles()
	return next((r for r in C.TRADES if r in roles), C.MECHANIC)


@frappe.whitelist()
def make_damage_assessment(source_name, target_doc=None):
	job, facts = _load(source_name, "damage_assessment")
	labour_rate = flt(get_settings().labour_rate)

	def postprocess(source, target):
		target.assessed_by = frappe.session.user
		target.priority = job.priority
		for insp in facts.trade_inspections:
			if insp.docstatus != 1:
				continue
			doc = frappe.get_doc("Vehicle Inspection", insp.name)
			for row in doc.checklist:
				if row.damage_found or row.condition == "Faulty":
					target.append("damage_items", {
						"damage_area": "Other", "trade": doc.inspection_type, "severity": "Moderate",
						"description": f"{row.check_point}: {row.remarks or ''}".strip(": "),
						"recommendation": doc.recommendations, "photo": row.photo, "source_inspection": doc.name,
					})
			if flt(doc.estimated_labour_hours):
				target.append("labour", {
					"trade": doc.inspection_type, "hours": doc.estimated_labour_hours, "rate": labour_rate,
					"description": (doc.recommendations or doc.findings or _("{0} work").format(_(doc.inspection_type)))[:140],
				})

	return _from_job(job, "Damage Assessment", {"name": "job_card"}, postprocess)


@frappe.whitelist()
def make_quotation(source_name, target_doc=None):
	job, facts = _load(source_name, "quotation")
	settings = get_settings()
	labour_item = require_setting("labour_item")
	assessment = frappe.get_doc("Damage Assessment", job.damage_assessment)

	def postprocess(source, target):
		target.quotation_to = "Customer"
		target.party_name = job.customer
		target.company = get_company()
		target.order_type = "Maintenance"
		target.transaction_date = nowdate()
		target.valid_till = add_days(nowdate(), settings.quotation_validity_days or 15)
		if settings.selling_price_list:
			target.selling_price_list = settings.selling_price_list
		for part in assessment.parts:
			target.append("items", {"item_code": part.item_code, "qty": part.qty, "rate": part.rate,
				"description": f"{part.item_name} ({_(part.damage_area)})" if part.damage_area else part.item_name})
		for line in assessment.labour:
			target.append("items", {"item_code": labour_item, "qty": line.hours, "rate": line.rate,
				"description": f"{_(line.trade)}: {line.description}", "uom": frappe.db.get_value("Item", labour_item, "stock_uom")})
		if settings.sales_taxes_template:
			target.taxes_and_charges = settings.sales_taxes_template
		target.run_method("set_missing_values")
		if settings.sales_taxes_template:
			target.set("taxes", [])
			from erpnext.controllers.accounts_controller import get_taxes_and_charges
			for tax in get_taxes_and_charges("Sales Taxes and Charges Template", settings.sales_taxes_template):
				target.append("taxes", tax)
		target.run_method("calculate_taxes_and_totals")

	return _from_job(job, "Quotation", {"name": "aw_job_card", "vehicle": "aw_vehicle"}, postprocess)


@frappe.whitelist()
def make_material_request(source_name, target_doc=None):
	job, facts = _load(source_name, "material_request")
	warehouse = require_setting("workshop_warehouse")

	def postprocess(source, target):
		target.material_request_type = "Purchase"
		target.company = get_company()
		target.schedule_date = add_days(nowdate(), 2)
		target.set_warehouse = warehouse
		for row in facts.parts.to_request:
			target.append("items", {"item_code": row.item_code, "qty": row.to_request, "warehouse": warehouse,
				"schedule_date": target.schedule_date, "uom": row.uom, "conversion_factor": 1})
		target.run_method("set_missing_values")

	return _from_job(job, "Material Request", {"name": "aw_job_card", "vehicle": "aw_vehicle"}, postprocess)


@frappe.whitelist()
def make_parts_issue(source_name, target_doc=None):
	job, facts = _load(source_name, "parts_issue")
	warehouse = require_setting("workshop_warehouse")

	def postprocess(source, target):
		target.stock_entry_type = "Material Issue"
		target.purpose = "Material Issue"
		target.company = get_company()
		target.from_warehouse = warehouse
		target.remarks = _("Parts issued to Job Card {0} ({1})").format(job.name, job.registration_number)
		for row in facts.parts.issuable:
			target.append("items", {"item_code": row.item_code, "qty": min(row.to_issue, row.in_stock),
				"s_warehouse": warehouse, "uom": row.uom, "stock_uom": row.uom, "conversion_factor": 1})
		target.run_method("set_missing_values")

	return _from_job(job, "Stock Entry", {"name": "aw_job_card"}, postprocess)


@frappe.whitelist()
def make_repair_task(source_name, target_doc=None):
	args = _args()
	job, facts = _load(source_name, "repair_task")

	def postprocess(source, target):
		target.subject = args.get("subject") or _("{0} repair - {1}").format(_(args.get("trade") or C.MECHANIC), job.registration_number)
		target.aw_trade = args.get("trade")
		target.aw_technician = args.get("technician")
		target.expected_time = flt(args.get("expected_time"))
		target.exp_start_date = nowdate()
		target.exp_end_date = job.expected_delivery_date
		target.company = get_company()
		target.priority = job.priority
		target.description = job.complaint

	return _from_job(job, "Task", {"name": "aw_job_card", "vehicle": "aw_vehicle", "customer": "aw_customer"}, postprocess)


@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None):
	job, facts = _load(source_name, "sales_invoice")
	from erpnext.selling.doctype.quotation.quotation import _make_sales_invoice

	invoice = _make_sales_invoice(job.quotation, ignore_permissions=True)
	invoice.aw_job_card = job.name
	invoice.aw_vehicle = job.vehicle
	invoice.aw_quotation = job.quotation
	invoice.due_date = invoice.due_date or nowdate()
	invoice.remarks = _("Job Card {0} - {1} {2}").format(job.name, job.vehicle_title, job.registration_number)
	return invoice


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
	job, facts = _load(source_name, "payment_entry")
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	payment = get_payment_entry("Sales Invoice", job.sales_invoice)
	payment.aw_job_card = job.name
	return payment
