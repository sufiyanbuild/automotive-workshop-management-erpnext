"""Shared set-up for the workshop tests.

Everything the tests need is created under the AWT- prefix so it cannot be
confused with demo or real data. The tests drive the same service functions the
user interface calls, so they exercise the real rules rather than a copy.
"""

import random
import string

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from automotive_workshop.workshop import actions
from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import mappers
from automotive_workshop.workshop.settings import get_settings

PREFIX = "AWT"
_PLATE_SEQUENCE = 0
PART_IN_STOCK = f"{PREFIX}-PART-STOCK"
PART_OUT_OF_STOCK = f"{PREFIX}-PART-ORDER"

USERS = {
	"manager": (f"{PREFIX.lower()}.manager@example.com", "Workshop Manager", C.MANAGER),
	"reception": (f"{PREFIX.lower()}.reception@example.com", "Workshop Reception", C.RECEPTION),
	"mechanic": (f"{PREFIX.lower()}.mechanic@example.com", "Workshop Mechanic", C.MECHANIC),
	"denter": (f"{PREFIX.lower()}.denter@example.com", "Workshop Denter", C.DENTER),
	"qc": (f"{PREFIX.lower()}.qc@example.com", "Workshop Quality Inspector", C.QUALITY_INSPECTOR),
	"store": (f"{PREFIX.lower()}.store@example.com", "Workshop Store Keeper", C.STORE_KEEPER),
	"accounts": (f"{PREFIX.lower()}.accounts@example.com", "Workshop Accounts", C.ACCOUNTS),
}


def ensure_user(key):
	email, profile, role = USERS[key]
	if frappe.db.exists("User", email):
		return email
	user = frappe.get_doc({
		"doctype": "User", "email": email, "first_name": key.title(), "last_name": PREFIX,
		"send_welcome_email": 0, "user_type": "System User",
	})
	if frappe.db.exists("Role Profile", profile):
		user.append("role_profiles", {"role_profile": profile})
	user.insert(ignore_permissions=True)
	if role not in frappe.get_roles(email):
		user.append("roles", {"role": role})
		user.save(ignore_permissions=True)
	return email


def ensure_customer(name=f"{PREFIX} Customer"):
	if not frappe.db.exists("Customer", name):
		frappe.get_doc({
			"doctype": "Customer", "customer_name": name, "customer_type": "Individual",
			"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
			"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
		}).insert(ignore_permissions=True)
	return name


def ensure_part(code, opening_qty=0):
	settings = get_settings()
	if not frappe.db.exists("Item", code):
		frappe.get_doc({
			"doctype": "Item", "item_code": code, "item_name": code, "stock_uom": "Nos", "is_stock_item": 1,
			"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
			"item_defaults": [{"company": settings.company, "default_warehouse": settings.workshop_warehouse}],
		}).insert(ignore_permissions=True)
	if not frappe.db.exists("Item Price", {"item_code": code, "price_list": settings.selling_price_list}):
		frappe.get_doc({"doctype": "Item Price", "item_code": code, "price_list": settings.selling_price_list,
			"price_list_rate": 500, "selling": 1}).insert(ignore_permissions=True)
	if opening_qty:
		entry = frappe.get_doc({
			"doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "company": settings.company,
			"items": [{"item_code": code, "qty": opening_qty, "t_warehouse": settings.workshop_warehouse, "basic_rate": 250}],
		})
		entry.insert(ignore_permissions=True)
		entry.submit()
	return code


def make_vehicle(registration, vin=None, customer=None, mileage=50000):
	return frappe.get_doc({
		"doctype": "Vehicle Master", "customer": customer or ensure_customer(), "make": "Toyota", "model": "Camry",
		"year": 2021, "registration_number": registration, "vin": vin, "current_mileage": mileage,
	}).insert(ignore_permissions=True)


class WorkshopTestCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.users = {key: ensure_user(key) for key in USERS}
		cls.customer = ensure_customer()
		cls.settings = get_settings()
		ensure_part(PART_IN_STOCK, opening_qty=25)
		ensure_part(PART_OUT_OF_STOCK)
		if not frappe.db.get_value("Workshop Settings", "Workshop Settings", "labour_rate"):
			frappe.db.set_single_value("Workshop Settings", "labour_rate", 150)
		frappe.db.commit()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.plate = self.unique_plate()

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def unique_plate(self):
		"""A fresh plate in the 3 letters + 4 digits format, unique within a test run."""
		global _PLATE_SEQUENCE
		_PLATE_SEQUENCE += 1
		letters = string.ascii_uppercase
		first = letters[(_PLATE_SEQUENCE // 9000) % 26]
		return f"T{first}{random.choice(letters)}-{1000 + (_PLATE_SEQUENCE % 9000)}"

	# ------------------------------------------------------------------ steps
	def new_job(self, vehicle=None, complaint="Noise from the front wheel", user=None, **kwargs):
		frappe.set_user(user or self.users["reception"])
		vehicle = vehicle or make_vehicle(self.unique_plate())
		values = {
			"doctype": "Workshop Job Card", "vehicle": vehicle.name, "current_mileage": vehicle.current_mileage + 100,
			"complaint": complaint, "service_type": "Mechanical Repair", "intake_datetime": frappe.utils.now_datetime(),
			"expected_delivery_date": add_days(nowdate(), 2), "workshop_manager": self.users["manager"],
		}
		values.update(kwargs)
		job = frappe.get_doc(values).insert()
		frappe.set_user("Administrator")
		return job

	def inspect(self, job, trade="Mechanic", user_key="mechanic", hours=2, faulty=2, submit=True):
		frappe.set_user(self.users[user_key])
		frappe.flags.args = frappe._dict(inspection_type=trade, technician=self.users[user_key])
		inspection = mappers.make_vehicle_inspection(job.name)
		for idx, row in enumerate(inspection.checklist):
			row.condition = "Faulty" if idx < faulty else "OK"
			row.damage_found = 1 if row.condition == "Faulty" else 0
			row.remarks = "Worn" if row.condition == "Faulty" else ""
		inspection.overall_condition = "Repair Required"
		inspection.estimated_labour_hours = hours
		inspection.findings = "Wear found during inspection"
		inspection.insert()
		if submit:
			inspection.submit()
		frappe.flags.args = None
		frappe.set_user("Administrator")
		return inspection

	def assess(self, job, parts=((PART_IN_STOCK, 1),), labour=(("Mechanic", "Replace part", 2),), submit=True):
		frappe.set_user(self.users["manager"])
		assessment = mappers.make_damage_assessment(job.name)
		if not assessment.damage_items:
			assessment.append("damage_items", {"damage_area": "Front", "trade": "Mechanic",
				"severity": "Moderate", "description": "Damage found"})
		assessment.set("parts", [])
		for code, qty in parts:
			assessment.append("parts", {"item_code": code, "qty": qty})
		assessment.set("labour", [])
		for trade, description, hours in labour:
			assessment.append("labour", {"trade": trade, "description": description, "hours": hours})
		assessment.insert()
		if submit:
			assessment.submit()
		frappe.set_user("Administrator")
		return assessment

	def quote(self, job, submit=True):
		frappe.set_user(self.users["manager"])
		quotation = mappers.make_quotation(job.name)
		quotation.insert()
		if submit:
			quotation.submit()
		frappe.set_user("Administrator")
		return quotation

	def approve(self, job, decision=C.APPROVAL_APPROVED, remarks=None):
		frappe.set_user(self.users["reception"])
		actions.mark_quotation_sent(job.name, channel="In person")
		actions.record_customer_approval(job.name, decision, remarks)
		frappe.set_user("Administrator")
		return job.reload()

	def issue_parts(self, job):
		frappe.set_user(self.users["store"])
		entry = mappers.make_parts_issue(job.name)
		entry.insert()
		entry.submit()
		frappe.set_user("Administrator")
		return entry

	def assign_task(self, job, trade="Mechanic", user_key="mechanic", subject="Replace part", hours=2):
		frappe.set_user(self.users["manager"])
		name = actions.create_repair_task(job.name, trade, self.users[user_key], subject, hours)
		frappe.set_user("Administrator")
		return frappe.get_doc("Task", name)

	def complete_repair(self, job, task, user_key="mechanic", hours=2.5):
		frappe.set_user(self.users["manager"])
		actions.start_repair(job.name)
		frappe.set_user(self.users[user_key])
		actions.update_repair_progress(job.name, [{"task": task.name, "status": "Completed", "progress": 100,
			"labour_hours": hours}])
		actions.request_quality_check(job.name)
		frappe.set_user("Administrator")
		return job.reload()

	def quality_check(self, job, result=C.QC_PASSED, remarks="Checked"):
		frappe.set_user(self.users["qc"])
		frappe.flags.args = frappe._dict(inspection_type=C.QC_TYPE, qc_result=result, technician=self.users["qc"])
		inspection = mappers.make_vehicle_inspection(job.name)
		for row in inspection.checklist:
			row.condition = "OK" if result == C.QC_PASSED else ("Faulty" if row.idx == 1 else "OK")
		inspection.qc_result = result
		inspection.remarks = remarks
		inspection.insert()
		inspection.submit()
		frappe.flags.args = None
		frappe.set_user("Administrator")
		return inspection

	def invoice(self, job, submit=True):
		frappe.set_user(self.users["accounts"])
		invoice = mappers.make_sales_invoice(job.name)
		invoice.insert()
		if submit:
			invoice.submit()
		frappe.set_user("Administrator")
		return invoice

	def pay(self, job):
		frappe.set_user(self.users["accounts"])
		payment = mappers.make_payment_entry(job.name)
		payment.mode_of_payment = frappe.db.get_value("Mode of Payment", {"type": "Bank"}, "name") or "Cash"
		payment.reference_no = f"{PREFIX}-PAY"
		payment.reference_date = nowdate()
		if not payment.paid_to:
			payment.paid_to = frappe.db.get_value(
				"Account", {"company": self.settings.company, "account_type": "Bank", "is_group": 0}, "name")
		payment.insert()
		payment.submit()
		frappe.set_user("Administrator")
		return payment

	def run_to(self, status, parts=((PART_IN_STOCK, 1),)):
		"""Drive a new Job Card up to the given lifecycle status and return it."""
		job = self.new_job()
		if status == C.OPEN:
			return job
		self.inspect(job)
		job.reload()
		if status == C.INSPECTION_COMPLETED:
			return job
		self.assess(job, parts=parts)
		self.quote(job)
		job.reload()
		if status == C.AWAITING_APPROVAL:
			return job
		self.approve(job)
		if status == C.PARTS_PENDING:
			return job
		self.issue_parts(job)
		task = self.assign_task(job)
		frappe.set_user(self.users["manager"])
		actions.start_repair(job.name)
		frappe.set_user("Administrator")
		job.reload()
		self.task = task
		if status == C.WORK_IN_PROGRESS:
			return job
		frappe.set_user(self.users["mechanic"])
		actions.update_repair_progress(job.name, [{"task": task.name, "status": "Completed", "progress": 100,
			"labour_hours": 2.5}])
		actions.request_quality_check(job.name)
		frappe.set_user("Administrator")
		job.reload()
		if status == C.QUALITY_CHECK:
			return job
		self.quality_check(job)
		job.reload()
		if status == C.COMPLETED:
			return job
		self.invoice(job)
		return job.reload()
