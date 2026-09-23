# Copyright (c) 2026, Sufiyan Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, get_link_to_form

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle
from automotive_workshop.workshop.settings import get_company

# Fields only the lifecycle may write. A user posting them directly is refused.
SYSTEM_FIELDS = (
	"status", "inspection_completed_on", "damage_assessment", "assessment_total",
	"quotation", "quotation_total", "quotation_sent_on", "customer_approval", "approval_on", "approval_remarks",
	"repair_started_on", "repair_completed_on",
	"qc_inspection", "qc_result", "qc_on", "rework_count",
	"sales_invoice", "invoice_total", "outstanding_amount", "payment_status",
	"released", "released_on", "released_by", "release_payment_status", "delivery_notes",
)
# Intake fields reception may still correct after the job has started.
EDITABLE_WHILE_OPEN = ("vehicle", "current_mileage", "intake_datetime")


class WorkshopJobCard(Document):
	def validate(self):
		by_lifecycle = self.flags.lifecycle_transition
		if self.is_new():
			self.initialise()
		elif not by_lifecycle:
			self.guard_system_fields()
			self.guard_intake_fields()

		self.set_vehicle_details()
		self.validate_vehicle()
		self.currency = frappe.get_cached_value("Company", get_company(), "default_currency") or self.currency
		if not self.is_new():
			self.current_stage = lifecycle.current_stage_label(lifecycle.compute_stages(self, lifecycle.get_facts(self)))

	def initialise(self):
		for field in SYSTEM_FIELDS:
			self.set(field, None if field not in ("rework_count", "released") else 0)
		self.status = C.OPEN
		self.current_stage = _("Reception")

	def guard_system_fields(self):
		before = self.get_doc_before_save()
		if not before:
			return
		if before.released:
			frappe.throw(
				_("Job Card {0} is closed because the vehicle was released. It can no longer be edited.").format(self.name),
				title=_("Job Card Closed"),
			)
		changed = [f for f in SYSTEM_FIELDS if not self.same_value(f, self.get(f), before.get(f))]
		if changed:
			labels = ", ".join(_(self.meta.get_label(f)) for f in changed)
			frappe.throw(
				_("{0} cannot be changed directly. Use the Actions menu on the Job Card so the workflow rules are applied.").format(labels),
				title=_("Workflow Controlled Field"),
			)

	def same_value(self, fieldname, new, old):
		fieldtype = self.meta.get_field(fieldname).fieldtype
		if fieldtype in ("Currency", "Float", "Int", "Check"):
			return flt(new) == flt(old)
		if fieldtype in ("Datetime", "Date"):
			return (get_datetime(new) if new else None) == (get_datetime(old) if old else None)
		return (new or "") == (old or "")

	def guard_intake_fields(self):
		before = self.get_doc_before_save()
		if self.status == C.OPEN or not before:
			return
		for field in EDITABLE_WHILE_OPEN:
			if not self.same_value(field, self.get(field), before.get(field)):
				frappe.throw(
					_("{0} can only be changed while the Job Card is Open.").format(_(self.meta.get_label(field))),
					title=_("Intake Locked"),
				)

	def set_vehicle_details(self):
		vehicle = frappe.db.get_value(
			"Vehicle Master", self.vehicle,
			["customer", "vehicle_title", "registration_number", "vin", "status", "current_mileage"], as_dict=True,
		)
		if not vehicle:
			frappe.throw(_("Vehicle {0} does not exist.").format(self.vehicle))
		self.customer = vehicle.customer
		self.vehicle_title = vehicle.vehicle_title
		self.registration_number = vehicle.registration_number
		self.vin = vehicle.vin
		self.customer_name = frappe.db.get_value("Customer", self.customer, "customer_name")
		self.flags.vehicle = vehicle

	def validate_vehicle(self):
		vehicle = self.flags.vehicle
		if self.released:
			# A closed Job Card keeps its record as it was. The checks below apply to
			# the vehicle's current visit, and the vehicle may since have returned.
			return
		if vehicle.status == "Inactive":
			frappe.throw(_("Vehicle {0} is marked Inactive and cannot be booked in.").format(self.registration_number))
		if frappe.db.get_value("Customer", self.customer, "disabled"):
			frappe.throw(_("Customer {0} is disabled.").format(self.customer_name))
		other = frappe.db.get_value(
			"Workshop Job Card", {"vehicle": self.vehicle, "released": 0, "name": ["!=", self.name]}, "name"
		)
		if other:
			frappe.throw(
				_("Vehicle {0} already has an open Job Card {1}. Close it before booking the vehicle in again.").format(
					frappe.bold(self.registration_number), get_link_to_form("Workshop Job Card", other)),
				title=_("Vehicle Already in Workshop"),
			)
		if self.is_new() and cint(vehicle.current_mileage) and cint(self.current_mileage) < cint(vehicle.current_mileage):
			frappe.msgprint(
				_("Mileage {0} km is lower than the {1} km last recorded for this vehicle. Please confirm the odometer reading.").format(
					self.current_mileage, vehicle.current_mileage),
				indicator="orange", alert=True,
			)

	def on_update(self):
		if self.flags.lifecycle_transition:
			return
		values = {}
		if cint(self.current_mileage) > cint(self.flags.vehicle.current_mileage):
			values["current_mileage"] = cint(self.current_mileage)
		if not self.released and self.flags.vehicle.status != "In Workshop":
			values["status"] = "In Workshop"
		if values:
			frappe.db.set_value("Vehicle Master", self.vehicle, values)

	def on_trash(self):
		if self.status != C.OPEN:
			frappe.throw(_("Only an Open Job Card can be deleted. {0} is {1}.").format(self.name, _(self.status)))

	def after_delete(self):
		if not frappe.db.exists("Workshop Job Card", {"vehicle": self.vehicle, "released": 0}):
			frappe.db.set_value("Vehicle Master", self.vehicle, "status", "Active")
