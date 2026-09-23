"""Role-based access: who may do what, and what each role can see."""

import frappe

from automotive_workshop.workshop import actions
from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import mappers
from automotive_workshop.tests.base import WorkshopTestCase


class TestActionPermissions(WorkshopTestCase):
	def test_only_a_manager_can_start_the_repair(self):
		job = self.run_to(C.PARTS_PENDING)
		self.issue_parts(job)
		self.assign_task(job)
		frappe.set_user(self.users["mechanic"])
		self.assertRaises(frappe.PermissionError, actions.start_repair, job.name)
		frappe.set_user(self.users["reception"])
		self.assertRaises(frappe.PermissionError, actions.start_repair, job.name)
		frappe.set_user(self.users["manager"])
		actions.start_repair(job.name)
		frappe.set_user("Administrator")
		self.assertEqual(job.reload().status, C.WORK_IN_PROGRESS)

	def test_only_reception_or_a_manager_records_the_customer_decision(self):
		job = self.run_to(C.AWAITING_APPROVAL)
		frappe.set_user(self.users["reception"])
		actions.mark_quotation_sent(job.name, channel="In person")
		frappe.set_user(self.users["mechanic"])
		self.assertRaises(frappe.PermissionError, actions.record_customer_approval, job.name, C.APPROVAL_APPROVED)

	def test_quality_check_can_only_be_recorded_by_a_quality_inspector(self):
		job = self.run_to(C.QUALITY_CHECK)
		frappe.set_user(self.users["mechanic"])
		frappe.flags.args = frappe._dict(inspection_type=C.QC_TYPE, qc_result=C.QC_PASSED,
			technician=self.users["mechanic"])
		with self.assertRaises(frappe.PermissionError):
			mappers.make_vehicle_inspection(job.name)
		frappe.flags.args = None
		frappe.set_user("Administrator")

	def test_an_inspection_cannot_be_assigned_to_the_wrong_trade(self):
		job = self.run_to(C.OPEN)
		frappe.set_user(self.users["manager"])
		frappe.flags.args = frappe._dict(inspection_type="Denter", technician=self.users["mechanic"])
		inspection = mappers.make_vehicle_inspection(job.name)
		frappe.flags.args = None
		with self.assertRaises(frappe.ValidationError) as caught:
			inspection.insert()
		self.assertIn("Denter", str(caught.exception))
		frappe.set_user("Administrator")

	def test_a_repair_task_cannot_be_given_to_the_wrong_trade(self):
		job = self.run_to(C.PARTS_PENDING)
		frappe.set_user(self.users["manager"])
		with self.assertRaises(frappe.ValidationError) as caught:
			actions.create_repair_task(job.name, "Denter", self.users["mechanic"], "Panel work", 2)
		self.assertIn("Denter", str(caught.exception))
		frappe.set_user("Administrator")

	def test_a_technician_cannot_submit_another_technicians_inspection(self):
		job = self.run_to(C.OPEN)
		inspection = self.inspect(job, trade="Mechanic", user_key="mechanic", submit=False)
		frappe.set_user(self.users["denter"])
		# Another technician's inspection is not even visible to them, so the row-level
		# permission refuses the submit before the controller's own check is reached.
		self.assertRaises(frappe.PermissionError, inspection.submit)
		frappe.set_user("Administrator")


class TestVisibility(WorkshopTestCase):
	def test_a_technician_sees_only_their_own_repair_tasks(self):
		job = self.run_to(C.PARTS_PENDING)
		self.issue_parts(job)
		mine = self.assign_task(job, trade="Mechanic", user_key="mechanic", subject="Mechanical work")
		theirs = self.assign_task(job, trade="Denter", user_key="denter", subject="Panel work")

		frappe.set_user(self.users["mechanic"])
		visible = frappe.get_list("Task", filters={"aw_job_card": job.name}, pluck="name")
		frappe.set_user("Administrator")
		self.assertIn(mine.name, visible)
		self.assertNotIn(theirs.name, visible)

	def test_a_technician_sees_live_job_cards_but_not_closed_ones_they_did_not_work_on(self):
		job = self.run_to(C.INVOICED)
		self.pay(job)
		frappe.set_user(self.users["reception"])
		actions.release_vehicle(job.name, notes="Delivered")
		frappe.set_user("Administrator")

		live = self.run_to(C.OPEN)
		frappe.set_user(self.users["denter"])
		visible = frappe.get_list("Workshop Job Card", pluck="name")
		frappe.set_user("Administrator")
		self.assertIn(live.name, visible, "work in the shop is visible to the floor")
		self.assertNotIn(job.name, visible, "a delivered vehicle's history is not")

	def test_a_manager_sees_every_job_card(self):
		job = self.run_to(C.OPEN)
		frappe.set_user(self.users["manager"])
		visible = frappe.get_list("Workshop Job Card", pluck="name")
		frappe.set_user("Administrator")
		self.assertIn(job.name, visible)

	def test_reception_can_create_a_customer_a_vehicle_and_a_job_card(self):
		frappe.set_user(self.users["reception"])
		for doctype in ("Customer", "Vehicle Master", "Workshop Job Card"):
			self.assertTrue(frappe.has_permission(doctype, "create"), doctype)
		self.assertFalse(frappe.has_permission("Sales Invoice", "create"), "reception does not invoice")
		frappe.set_user("Administrator")

	def test_store_keeper_can_issue_stock_but_not_invoice(self):
		frappe.set_user(self.users["store"])
		self.assertTrue(frappe.has_permission("Stock Entry", "create"))
		self.assertTrue(frappe.has_permission("Purchase Receipt", "create"))
		self.assertFalse(frappe.has_permission("Sales Invoice", "create"))
		frappe.set_user("Administrator")

	def test_accounts_can_invoice_and_take_payment(self):
		frappe.set_user(self.users["accounts"])
		self.assertTrue(frappe.has_permission("Sales Invoice", "create"))
		self.assertTrue(frappe.has_permission("Payment Entry", "create"))
		self.assertFalse(frappe.has_permission("Stock Entry", "create"))
		frappe.set_user("Administrator")
