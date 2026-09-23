# Copyright (c) 2026, Sufiyan Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle
from automotive_workshop.workshop.pricing import get_part_rate
from automotive_workshop.workshop.settings import get_company, get_settings


class DamageAssessment(Document):
	def validate(self):
		job = lifecycle.get_job(self.job_card)
		lifecycle.assert_not_released(job)
		lifecycle.assert_status(job, C.OPEN, C.INSPECTION_COMPLETED, action=_("Preparing a Damage Assessment"))
		self.vehicle, self.customer = job.vehicle, job.customer
		self.currency = frappe.get_cached_value("Company", get_company(), "default_currency")
		self.validate_parts()
		self.calculate_totals()

	def validate_parts(self):
		for row in self.parts:
			item = frappe.get_cached_value("Item", row.item_code, ["is_stock_item", "disabled"], as_dict=True)
			if item.disabled:
				frappe.throw(_("Row {0}: part {1} is disabled.").format(row.idx, row.item_code))
			if not item.is_stock_item:
				frappe.throw(_("Row {0}: {1} is not a stock item. Required parts must be stock items so availability can be checked; put services in the Labour table.").format(
					row.idx, row.item_code))
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: quantity for {1} must be greater than zero.").format(row.idx, row.item_code))
			if not flt(row.rate):
				row.rate = get_part_rate(row.item_code)

	def calculate_totals(self):
		labour_rate = flt(get_settings().labour_rate)
		for row in self.parts:
			row.amount = flt(row.qty) * flt(row.rate)
		for row in self.labour:
			if not flt(row.rate):
				row.rate = labour_rate
			row.amount = flt(row.hours) * flt(row.rate)
		self.parts_total = sum(flt(r.amount) for r in self.parts)
		self.labour_total = sum(flt(r.amount) for r in self.labour)
		self.estimated_labour_hours = sum(flt(r.hours) for r in self.labour)
		self.estimated_total = self.parts_total + self.labour_total

	def before_submit(self):
		job = lifecycle.get_job(self.job_card)
		if job.status != C.INSPECTION_COMPLETED:
			frappe.throw(
				_("The Damage Assessment can only be submitted after the inspections are completed. Job Card {0} is {1}.").format(
					job.name, _(job.status)),
				title=_("Inspection Not Completed"),
			)
		if job.damage_assessment:
			frappe.throw(_("Job Card {0} already has submitted Damage Assessment {1}. Cancel and amend it instead.").format(
				job.name, job.damage_assessment))
		if not self.parts and not self.labour:
			frappe.throw(_("Add at least one required part or labour line so the repair can be quoted."))

	def on_submit(self):
		lifecycle.update_fields(self.job_card, damage_assessment=self.name, assessment_total=self.estimated_total)

	def before_cancel(self):
		job = lifecycle.get_job(self.job_card)
		if job.status != C.INSPECTION_COMPLETED:
			frappe.throw(
				_("This Damage Assessment cannot be cancelled while Job Card {0} is {1}. Cancel the quotation first if the customer asked for a revision.").format(
					job.name, _(job.status)),
				title=_("Assessment Locked"),
			)

	def on_cancel(self):
		job = lifecycle.get_job(self.job_card)
		if job.damage_assessment == self.name:
			lifecycle.update_fields(job, damage_assessment=None, assessment_total=0)
