"""The visual tracker, the Create menu and the Actions menu.

All three are computed on the server from the real state, so they can be
asserted without a browser.
"""

import frappe

from automotive_workshop.workshop import actions
from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import mappers
from automotive_workshop.workshop.context import get_job_card_context
from automotive_workshop.tests.base import PART_OUT_OF_STOCK, WorkshopTestCase

STAGES = ["reception", "inspection", "assessment", "quotation", "approval", "parts", "repair", "qc", "invoice", "delivery"]


class TestTracker(WorkshopTestCase):
	def states(self, job):
		return {s["key"]: s["state"] for s in get_job_card_context(job.name)["stages"]}

	def test_new_job_card_is_at_reception(self):
		job = self.run_to(C.OPEN)
		states = self.states(job)
		self.assertEqual(states["reception"], "current")
		self.assertTrue(all(states[k] == "pending" for k in STAGES[1:]))

	def test_tracker_follows_the_job_through_every_stage(self):
		expected = {
			C.INSPECTION_COMPLETED: "assessment",
			C.AWAITING_APPROVAL: "quotation",
			C.PARTS_PENDING: "parts",
			C.WORK_IN_PROGRESS: "repair",
			C.QUALITY_CHECK: "qc",
			C.COMPLETED: "invoice",
			C.INVOICED: "delivery",
		}
		for status, current in expected.items():
			job = self.run_to(status)
			states = self.states(job)
			self.assertEqual(states[current], "current", f"{status} should sit at {current}: {states}")
			index = STAGES.index(current)
			for key in STAGES[:index]:
				self.assertEqual(states[key], "done", f"{key} should be done at {status}")
			for key in STAGES[index + 1:]:
				self.assertEqual(states[key], "pending", f"{key} should be pending at {status}")

	def test_quotation_stage_completes_only_once_the_quotation_is_sent(self):
		job = self.run_to(C.AWAITING_APPROVAL)
		self.assertEqual(self.states(job)["quotation"], "current")
		frappe.set_user(self.users["reception"])
		actions.mark_quotation_sent(job.name, channel="In person")
		frappe.set_user("Administrator")
		job.reload()
		states = self.states(job)
		self.assertEqual(states["quotation"], "done")
		self.assertEqual(states["approval"], "current")

	def test_delivered_job_shows_every_stage_complete(self):
		job = self.run_to(C.INVOICED)
		self.pay(job)
		frappe.set_user(self.users["reception"])
		actions.release_vehicle(job.name, notes="Delivered")
		frappe.set_user("Administrator")
		states = self.states(job.reload())
		self.assertTrue(all(state == "done" for state in states.values()), states)

	def test_pending_parts_stage_explains_itself(self):
		job = self.run_to(C.PARTS_PENDING, parts=((PART_OUT_OF_STOCK, 3),))
		context = get_job_card_context(job.name)
		parts_stage = next(s for s in context["stages"] if s["key"] == "parts")
		self.assertIn("1 items", parts_stage["detail"])
		self.assertTrue(parts_stage["attention"])
		self.assertEqual(context["next_step"]["key"], "request_parts")
		self.assertEqual(context["next_step"]["owner"], C.STORE_KEEPER)


class TestMenus(WorkshopTestCase):
	def menus(self, job, user=None):
		frappe.set_user(user or self.users["manager"])
		context = get_job_card_context(job.name)
		frappe.set_user("Administrator")
		return {c["key"] for c in context["create"]}, {a["key"] for a in context["actions"]}

	def test_open_job_offers_inspection_and_assessment_only(self):
		job = self.run_to(C.OPEN)
		create, action = self.menus(job)
		self.assertEqual(create, {"inspection", "damage_assessment"})
		self.assertIn("start_inspection", action)
		for invalid in ("start_repair", "request_qc", "generate_invoice", "release_vehicle", "record_approval"):
			self.assertNotIn(invalid, action)

	def test_awaiting_approval_offers_sending_and_recording_the_decision(self):
		job = self.run_to(C.AWAITING_APPROVAL)
		create, action = self.menus(job)
		self.assertIn("send_quotation", action)
		self.assertNotIn("record_approval", action, "the decision cannot be recorded before the quotation is sent")
		self.assertNotIn("quotation", create, "a second quotation is not offered while one is out with the customer")

		frappe.set_user(self.users["reception"])
		actions.mark_quotation_sent(job.name, channel="In person")
		frappe.set_user("Administrator")
		_create, action = self.menus(job.reload())
		self.assertIn("record_approval", action)

	def test_rejected_quotation_offers_a_revision(self):
		job = self.run_to(C.AWAITING_APPROVAL)
		self.approve(job, decision=C.APPROVAL_REJECTED, remarks="Too expensive")
		create, action = self.menus(job.reload())
		self.assertIn("revise_quotation", action)
		self.assertIn("quotation", create)
		self.assertNotIn("record_approval", action)

	def test_parts_pending_offers_parts_work_and_hides_start_repair_until_ready(self):
		job = self.run_to(C.PARTS_PENDING)
		create, action = self.menus(job)
		self.assertIn("issue_parts", action)
		self.assertIn("assign_task", action)
		self.assertNotIn("start_repair", action, "no repair task is assigned yet")
		self.assertIn("repair_task", create)

		self.issue_parts(job)
		self.assign_task(job)
		_create, action = self.menus(job.reload())
		self.assertIn("start_repair", action)

	def test_work_in_progress_offers_quality_check_only_when_tasks_are_done(self):
		job = self.run_to(C.WORK_IN_PROGRESS)
		create, action = self.menus(job)
		self.assertIn("update_repair_progress", action)
		self.assertNotIn("request_qc", action)
		self.assertNotIn("quality_check", create)

		frappe.set_user(self.users["mechanic"])
		actions.update_repair_progress(job.name, [{"task": self.task.name, "status": "Completed", "progress": 100,
			"labour_hours": 3}])
		frappe.set_user("Administrator")
		job.reload()
		_create, action = self.menus(job)
		self.assertIn("request_qc", action)

		# Recording the Quality Check itself belongs to the Quality Inspector.
		qc_create, _action = self.menus(job, user=self.users["qc"])
		self.assertIn("quality_check", qc_create)
		manager_create, _action = self.menus(job, user=self.users["manager"])
		self.assertNotIn("quality_check", manager_create)

	def test_completed_offers_the_invoice_to_accounts_but_not_to_the_manager(self):
		job = self.run_to(C.COMPLETED)
		create, action = self.menus(job, user=self.users["accounts"])
		self.assertEqual(create, {"sales_invoice"})
		self.assertIn("generate_invoice", action)
		self.assertNotIn("release_vehicle", action)

		create, action = self.menus(job, user=self.users["manager"])
		self.assertEqual(create, set(), "the manager does not raise invoices")
		self.assertNotIn("generate_invoice", action)

	def test_invoiced_offers_payment_then_release(self):
		job = self.run_to(C.COMPLETED)
		self.invoice(job)
		create, action = self.menus(job.reload(), user=self.users["accounts"])
		self.assertIn("payment_entry", create)
		self.assertIn("record_payment", action)
		_create, action = self.menus(job, user=self.users["reception"])
		self.assertNotIn("release_vehicle", action, "not while the invoice is unpaid")

		self.pay(job)
		_create, action = self.menus(job.reload(), user=self.users["reception"])
		self.assertIn("release_vehicle", action)

	def test_released_job_offers_nothing_but_viewing(self):
		job = self.run_to(C.INVOICED)
		self.pay(job)
		frappe.set_user(self.users["reception"])
		actions.release_vehicle(job.name, notes="Delivered")
		frappe.set_user("Administrator")
		create, action = self.menus(job.reload())
		self.assertEqual(create, set())
		self.assertTrue(all(key.startswith("view_") for key in action), action)


class TestPrefill(WorkshopTestCase):
	def test_inspection_is_prefilled_from_the_job_card(self):
		job = self.run_to(C.OPEN)
		frappe.set_user(self.users["mechanic"])
		frappe.flags.args = frappe._dict(inspection_type="Mechanic", technician=self.users["mechanic"])
		inspection = mappers.make_vehicle_inspection(job.name)
		frappe.flags.args = None
		frappe.set_user("Administrator")
		self.assertEqual(inspection.job_card, job.name)
		self.assertEqual(inspection.vehicle, job.vehicle)
		self.assertEqual(inspection.customer, job.customer)
		self.assertEqual(inspection.inspection_type, "Mechanic")
		self.assertTrue(inspection.checklist, "the checklist is prefilled from Workshop Settings")
		self.assertNotEqual(inspection.naming_series, "JC-.YYYY.-",
			"the inspection must not inherit the Job Card's naming series")

	def test_assessment_is_prefilled_from_the_submitted_inspections(self):
		job = self.run_to(C.INSPECTION_COMPLETED)
		frappe.set_user(self.users["manager"])
		assessment = mappers.make_damage_assessment(job.name)
		frappe.set_user("Administrator")
		self.assertEqual(assessment.job_card, job.name)
		self.assertEqual(assessment.vehicle, job.vehicle)
		self.assertTrue(assessment.damage_items, "faulty checklist rows become damage items")
		self.assertTrue(assessment.labour, "the inspector's estimated hours become a labour line")

	def test_quotation_is_prefilled_with_parts_labour_and_vat(self):
		job = self.run_to(C.INSPECTION_COMPLETED)
		self.assess(job)
		frappe.set_user(self.users["manager"])
		quotation = mappers.make_quotation(job.name)
		frappe.set_user("Administrator")
		self.assertEqual(quotation.aw_job_card, job.name)
		self.assertEqual(quotation.party_name, job.customer)
		self.assertEqual(quotation.aw_vehicle, job.vehicle)
		item_codes = {row.item_code for row in quotation.items}
		self.assertIn(self.settings.labour_item, item_codes)
		self.assertTrue(quotation.taxes, "the VAT template is applied")
		self.assertEqual(quotation.taxes[0].rate, 15)

	def test_invoice_is_prefilled_from_the_approved_quotation(self):
		job = self.run_to(C.COMPLETED)
		frappe.set_user(self.users["accounts"])
		invoice = mappers.make_sales_invoice(job.name)
		frappe.set_user("Administrator")
		self.assertEqual(invoice.aw_job_card, job.name)
		self.assertEqual(invoice.aw_quotation, job.quotation)
		self.assertEqual(invoice.customer, job.customer)
		self.assertEqual(len(invoice.items), len(frappe.get_doc("Quotation", job.quotation).items))
