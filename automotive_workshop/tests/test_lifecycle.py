"""The Job Card lifecycle, positive and negative."""

import frappe
from frappe.utils import flt

from automotive_workshop.workshop import actions
from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import lifecycle as L
from automotive_workshop.workshop import mappers
from automotive_workshop.workshop.context import get_job_card_context
from automotive_workshop.tests.base import PART_IN_STOCK, PART_OUT_OF_STOCK, WorkshopTestCase, make_vehicle


class TestLifecycle(WorkshopTestCase):
	def test_complete_lifecycle_reception_to_delivery(self):
		job = self.new_job()
		self.assertEqual(job.status, C.OPEN)
		self.assertEqual(job.customer, self.customer, "customer is taken from the vehicle, not typed again")

		self.inspect(job)
		self.assertEqual(job.reload().status, C.INSPECTION_COMPLETED)
		self.assertTrue(job.inspection_completed_on)

		assessment = self.assess(job)
		job.reload()
		self.assertEqual(job.damage_assessment, assessment.name)
		self.assertEqual(flt(job.assessment_total), flt(assessment.estimated_total))

		quotation = self.quote(job)
		job.reload()
		self.assertEqual(job.status, C.AWAITING_APPROVAL)
		self.assertEqual(job.customer_approval, C.APPROVAL_PENDING)
		self.assertTrue(quotation.total_taxes_and_charges, "VAT must be applied from the tax template")
		self.assertAlmostEqual(flt(quotation.total_taxes_and_charges), flt(quotation.net_total) * 0.15, places=2)

		self.approve(job)
		self.assertEqual(job.status, C.PARTS_PENDING)
		self.assertEqual(job.customer_approval, C.APPROVAL_APPROVED)

		self.issue_parts(job)
		task = self.assign_task(job)
		self.complete_repair(job, task)
		self.assertEqual(job.reload().status, C.QUALITY_CHECK)

		self.quality_check(job)
		job.reload()
		self.assertEqual(job.status, C.COMPLETED)
		self.assertEqual(job.qc_result, C.QC_PASSED)

		invoice = self.invoice(job)
		job.reload()
		self.assertEqual(job.status, C.INVOICED)
		self.assertEqual(job.sales_invoice, invoice.name)
		self.assertGreater(flt(job.outstanding_amount), 0)

		self.pay(job)
		job.reload()
		self.assertEqual(flt(job.outstanding_amount), 0)
		self.assertEqual(job.payment_status, "Paid")

		frappe.set_user(self.users["reception"])
		actions.release_vehicle(job.name, notes="Handed over")
		frappe.set_user("Administrator")
		job.reload()
		self.assertTrue(job.released)
		self.assertEqual(frappe.db.get_value("Vehicle Master", job.vehicle, "status"), "Active")

	def test_status_cannot_be_changed_by_hand(self):
		job = self.run_to(C.OPEN)
		job.status = C.COMPLETED
		self.assertRaises(frappe.ValidationError, job.save)

	def test_repair_cannot_start_before_customer_approval(self):
		job = self.run_to(C.AWAITING_APPROVAL)
		frappe.set_user(self.users["manager"])
		with self.assertRaises(L.WorkflowError) as caught:
			actions.start_repair(job.name)
		self.assertIn("Parts Pending", str(caught.exception))

	def test_repair_task_cannot_be_worked_before_repair_starts(self):
		job = self.run_to(C.PARTS_PENDING)
		self.issue_parts(job)
		task = self.assign_task(job)
		task.status = "Working"
		with self.assertRaises(L.WorkflowError) as caught:
			task.save()
		self.assertIn("Repair cannot start", str(caught.exception))

	def test_repair_cannot_start_while_parts_are_missing(self):
		job = self.run_to(C.PARTS_PENDING, parts=((PART_OUT_OF_STOCK, 2),))
		self.assign_task(job)
		frappe.set_user(self.users["manager"])
		with self.assertRaises(L.WorkflowError) as caught:
			actions.start_repair(job.name)
		self.assertIn(PART_OUT_OF_STOCK, str(caught.exception))

	def test_quality_check_cannot_be_requested_while_tasks_are_open(self):
		job = self.run_to(C.WORK_IN_PROGRESS)
		frappe.set_user(self.users["manager"])
		with self.assertRaises(L.WorkflowError) as caught:
			actions.request_quality_check(job.name)
		self.assertIn("completed", str(caught.exception).lower())

	def test_invoice_requires_a_passed_quality_check(self):
		job = self.run_to(C.QUALITY_CHECK)
		# The Create menu does not offer it, and the mapper refuses it.
		with self.assertRaises(L.WorkflowError):
			mappers.make_sales_invoice(job.name)

		# Even an invoice built by hand is refused on submit.
		invoice = frappe.get_doc({
			"doctype": "Sales Invoice", "customer": job.customer, "company": self.settings.company,
			"aw_job_card": job.name, "due_date": frappe.utils.nowdate(),
			"items": [{"item_code": self.settings.labour_item, "qty": 1, "rate": 100}],
		}).insert(ignore_permissions=True)
		with self.assertRaises(L.WorkflowError) as caught:
			invoice.submit()
		self.assertIn("Quality Check", str(caught.exception))

	def test_failed_quality_check_returns_the_job_to_repair(self):
		job = self.run_to(C.QUALITY_CHECK)
		self.quality_check(job, result=C.QC_FAILED, remarks="Paint finish not acceptable")
		job.reload()
		self.assertEqual(job.status, C.WORK_IN_PROGRESS)
		self.assertEqual(job.qc_result, C.QC_FAILED)
		self.assertEqual(job.rework_count, 1)
		self.assertEqual(frappe.db.get_value("Task", self.task.name, "status"), "Working",
			"the completed repair task is reopened for rework")

	def test_vehicle_cannot_be_released_before_payment(self):
		job = self.run_to(C.INVOICED)
		frappe.set_user(self.users["reception"])
		with self.assertRaises(L.WorkflowError) as caught:
			actions.release_vehicle(job.name, notes="Customer collecting")
		self.assertIn("outstanding", str(caught.exception).lower())

	def test_vehicle_cannot_be_released_before_invoicing(self):
		job = self.run_to(C.COMPLETED)
		frappe.set_user(self.users["reception"])
		self.assertRaises(L.WorkflowError, actions.release_vehicle, job.name)

	def test_release_on_credit_needs_the_setting_and_a_manager(self):
		job = self.run_to(C.INVOICED)
		with self.change_settings("Workshop Settings", {"require_full_payment": 0}):
			frappe.set_user(self.users["reception"])
			self.assertRaises(frappe.PermissionError, actions.release_vehicle, job.name, "On account", 1)
			frappe.set_user(self.users["manager"])
			actions.release_vehicle(job.name, notes="Fleet customer, billed monthly", release_on_credit=1)
		job.reload()
		self.assertTrue(job.released)
		self.assertIn("outstanding", (job.release_payment_status or "").lower())

	def test_quotation_revision_returns_the_job_and_keeps_the_history(self):
		job = self.run_to(C.AWAITING_APPROVAL)
		first_quotation = job.quotation
		self.approve(job, decision=C.APPROVAL_REVISION, remarks="Please quote a used bumper")
		job.reload()
		self.assertEqual(job.status, C.AWAITING_APPROVAL)
		self.assertEqual(job.customer_approval, C.APPROVAL_REVISION)

		frappe.set_user(self.users["manager"])
		actions.revise_quotation(job.name)
		job.reload()
		self.assertEqual(job.status, C.INSPECTION_COMPLETED)
		self.assertEqual(frappe.db.get_value("Quotation", first_quotation, "docstatus"), 2)

		self.quote(job)
		job.reload()
		self.assertEqual(job.status, C.AWAITING_APPROVAL)
		self.assertNotEqual(job.quotation, first_quotation)

	def test_approved_quotation_cannot_be_cancelled(self):
		job = self.run_to(C.PARTS_PENDING)
		quotation = frappe.get_doc("Quotation", job.quotation)
		with self.assertRaises(L.WorkflowError) as caught:
			quotation.cancel()
		self.assertIn("approved", str(caught.exception).lower())

	def test_second_job_card_for_a_vehicle_already_in_the_workshop_is_refused(self):
		job = self.run_to(C.OPEN)
		vehicle = frappe.get_doc("Vehicle Master", job.vehicle)
		with self.assertRaises(frappe.ValidationError) as caught:
			self.new_job(vehicle=vehicle)
		self.assertIn("already has an open Job Card", str(caught.exception))

	def test_parts_issue_cannot_exceed_what_the_assessment_requires(self):
		job = self.run_to(C.PARTS_PENDING)
		frappe.set_user(self.users["store"])
		entry = mappers.make_parts_issue(job.name)
		entry.items[0].qty = 5
		entry.insert()
		with self.assertRaises(frappe.ValidationError) as caught:
			entry.submit()
		self.assertIn("exceeds", str(caught.exception))

	def test_service_history_is_built_from_the_job_cards(self):
		job = self.run_to(C.INVOICED)
		self.pay(job)
		frappe.set_user(self.users["reception"])
		actions.release_vehicle(job.name, notes="Delivered")
		frappe.set_user("Administrator")

		vehicle = frappe.get_doc("Vehicle Master", job.vehicle)
		second = self.new_job(vehicle=vehicle, complaint="Service due")
		context = get_job_card_context(second.name)
		history = [row["name"] for row in context["history"]]
		self.assertIn(job.name, history)
		self.assertNotIn(second.name, history)


class TestParts(WorkshopTestCase):
	def test_shortage_flows_through_request_order_and_receipt(self):
		job = self.run_to(C.PARTS_PENDING, parts=((PART_OUT_OF_STOCK, 2),))
		summary = get_job_card_context(job.name)["parts"]
		self.assertEqual(summary["lines"][0]["state"], "Shortage")

		frappe.set_user(self.users["store"])
		request = mappers.make_material_request(job.name)
		request.insert()
		request.submit()
		self.assertEqual(request.aw_job_card, job.name)
		self.assertEqual(flt(request.items[0].qty), 2)

		self.assertEqual(get_job_card_context(job.name)["parts"]["lines"][0]["state"], "Requested")

		from erpnext.stock.doctype.material_request.material_request import make_purchase_order

		frappe.set_user("Administrator")
		order = make_purchase_order(request.name)
		order.supplier = self._supplier()
		order.items[0].rate = 200
		order.insert()
		order.submit()
		self.assertEqual(order.items[0].aw_job_card, job.name, "the Job Card follows the part onto the order")
		self.assertEqual(get_job_card_context(job.name)["parts"]["lines"][0]["state"], "On Order")

		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

		receipt = make_purchase_receipt(order.name)
		receipt.insert()
		receipt.submit()
		self.assertEqual(receipt.items[0].aw_job_card, job.name)

		summary = get_job_card_context(job.name)["parts"]
		self.assertEqual(summary["lines"][0]["state"], "Available")
		self.issue_parts(job)
		self.assertEqual(get_job_card_context(job.name)["parts"]["lines"][0]["state"], "Issued")

	def _supplier(self):
		name = "AWT Supplier"
		if not frappe.db.exists("Supplier", name):
			frappe.get_doc({"doctype": "Supplier", "supplier_name": name,
				"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")}).insert(ignore_permissions=True)
		return name
