"""Demo data for Automotive Workshop Management.

Creates a realistic Saudi workshop scenario and drives Job Cards through the
lifecycle using the same services the user interface calls, so the demo proves
the real workflow rather than writing statuses directly.

Every record it creates is marked (customers, suppliers and vehicles carry the
[DEMO] tag; Job Cards carry a DEMO note), and `drop_demo()` removes them again.

	bench --site <site> execute automotive_workshop.demo.create_demo
	bench --site <site> execute automotive_workshop.demo.drop_demo
"""

import os

import frappe
from frappe.utils import add_days, add_to_date, flt, now_datetime, nowdate

from automotive_workshop.workshop import actions
from automotive_workshop.workshop import constants as C
from automotive_workshop.workshop import mappers
from automotive_workshop.workshop.settings import get_settings

TAG = "[DEMO]"
NOTE = "DEMO RECORD - created by automotive_workshop.demo"


def demo_password():
	"""Password for the demo users. No credential is kept in this repository.

	Set AW_DEMO_PASSWORD to choose one; otherwise a random password is generated
	and printed once, at the end of create_demo(). Demo users belong on a local
	demo site only and must never be created on a production site.
	"""
	if not frappe.flags.aw_demo_password:
		frappe.flags.aw_demo_password = os.environ.get("AW_DEMO_PASSWORD") or frappe.generate_hash(length=16)
	return frappe.flags.aw_demo_password


USERS = {
	"reception@workshop.local": ("Noura", "Al-Otaibi", "Workshop Reception"),
	"manager@workshop.local": ("Khalid", "Al-Harbi", "Workshop Manager"),
	"denter@workshop.local": ("Sami", "Al-Dosari", "Workshop Denter"),
	"mechanic@workshop.local": ("Faisal", "Al-Qahtani", "Workshop Mechanic"),
	"electrician@workshop.local": ("Omar", "Al-Zahrani", "Workshop Electrician"),
	"qc@workshop.local": ("Abdullah", "Al-Shammari", "Workshop Quality Inspector"),
	"purchase@workshop.local": ("Yousef", "Al-Ghamdi", "Workshop Purchase"),
	"store@workshop.local": ("Majed", "Al-Anazi", "Workshop Store Keeper"),
	"accounts@workshop.local": ("Hani", "Al-Mutairi", "Workshop Accounts"),
}
RECEPTION, MANAGER = "reception@workshop.local", "manager@workshop.local"
DENTER, MECHANIC = "denter@workshop.local", "mechanic@workshop.local"
ELECTRICIAN, QC = "electrician@workshop.local", "qc@workshop.local"
PURCHASE, STORE, ACCOUNTS = "purchase@workshop.local", "store@workshop.local", "accounts@workshop.local"

PARTS = [
	("DEMO-BUMPER-CAM", "Front Bumper Cover - Camry", 1250, 4),
	("DEMO-HEADLAMP-CAM", "Headlamp Assembly RH - Camry", 1850, 2),
	("DEMO-BRAKEPAD-FR", "Brake Pad Set Front", 320, 10),
	("DEMO-FENDER-SON", "Front Fender LH - Sonata", 900, 0),
	("DEMO-ALT-PATROL", "Alternator - Patrol", 2100, 0),
	("DEMO-OILFILTER", "Oil Filter", 45, 24),
	("DEMO-BONNET-CAM", "Bonnet - Camry", 2200, 0),
]
CUSTOMERS = [
	("Ahmed Al-Salem", "0501234567"),
	("Reem Trading Est.", "0533344556"),
	("Saud Al-Otaibi", "0555667788"),
]
VEHICLES = [
	# customer index, make, model, year, registration, vin, colour, mileage, type, fuel
	(0, "Toyota", "Camry", 2021, "ABC-1234", "DEMXX000000000001", "White", 84500, "Sedan", "Petrol"),
	(0, "Nissan", "Patrol", 2019, "ABC-5678", "DEMXX000000000002", "Black", 142000, "SUV", "Petrol"),
	(1, "Hyundai", "Sonata", 2022, "TRD-9012", "DEMXX000000000003", "Silver", 41200, "Sedan", "Petrol"),
	(2, "Toyota", "Hilux", 2020, "SAU-3344", "DEMXX000000000004", "Grey", 98700, "Pickup", "Diesel"),
	(2, "Ford", "Explorer", 2023, "SAU-7788", "DEMXX000000000005", "Blue", 22500, "SUV", "Petrol"),
]


# ------------------------------------------------------------------ helpers
def _as(user):
	frappe.set_user(user)


def _insert(doc, user=None, submit=False):
	if user:
		_as(user)
	doc.insert()
	if submit:
		doc.submit()
	return doc


def _settings():
	return get_settings()


def create_users():
	"""Create the demo staff, and return the ones newly created.

	Roles come from the Role Profile child table: Frappe v16 ignores the
	deprecated role_profile_name field when it is set on its own. Existing users
	keep whatever password they already have.
	"""
	created = []
	for email, (first, last, profile) in USERS.items():
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
		else:
			user = frappe.get_doc({
				"doctype": "User", "email": email, "first_name": first, "last_name": last,
				"send_welcome_email": 0, "user_type": "System User", "new_password": demo_password(),
			})
			created.append(email)
		if frappe.db.exists("Role Profile", profile) and profile not in {r.role_profile for r in user.role_profiles}:
			user.append("role_profiles", {"role_profile": profile})
		user.save(ignore_permissions=True) if not user.is_new() else user.insert(ignore_permissions=True)
	return created


def create_masters():
	company = _settings().company
	warehouse = _settings().workshop_warehouse
	group = frappe.db.get_value("Item Group", {"item_group_name": "Products"}, "name") or \
		frappe.db.get_value("Item Group", {"is_group": 0}, "name")

	for name, mobile in CUSTOMERS:
		full = f"{name} {TAG}"
		if not frappe.db.exists("Customer", full):
			frappe.get_doc({
				"doctype": "Customer", "customer_name": full, "customer_type": "Individual" if "Est." not in name else "Company",
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"), "mobile_no": mobile,
			}).insert(ignore_permissions=True)

	supplier = f"Al-Jazirah Auto Parts {TAG}"
	if not frappe.db.exists("Supplier", supplier):
		frappe.get_doc({
			"doctype": "Supplier", "supplier_name": supplier,
			"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
		}).insert(ignore_permissions=True)

	for code, name, rate, _qty in PARTS:
		if not frappe.db.exists("Item", code):
			frappe.get_doc({
				"doctype": "Item", "item_code": code, "item_name": name, "item_group": group, "stock_uom": "Nos",
				"is_stock_item": 1, "description": f"{name} {TAG}",
				"item_defaults": [{"company": company, "default_warehouse": warehouse}],
			}).insert(ignore_permissions=True)
		price_list = _settings().selling_price_list or "Standard Selling"
		if not frappe.db.exists("Item Price", {"item_code": code, "price_list": price_list}):
			frappe.get_doc({"doctype": "Item Price", "item_code": code, "price_list": price_list,
				"price_list_rate": rate, "selling": 1}).insert(ignore_permissions=True)

	labour = _settings().labour_item
	price_list = _settings().selling_price_list or "Standard Selling"
	if not frappe.db.exists("Item Price", {"item_code": labour, "price_list": price_list}):
		frappe.get_doc({"doctype": "Item Price", "item_code": labour, "price_list": price_list,
			"price_list_rate": 150, "selling": 1}).insert(ignore_permissions=True)
	if not flt(_settings().labour_rate):
		frappe.db.set_single_value("Workshop Settings", "labour_rate", 150)

	receive_opening_stock(company, warehouse)
	create_vehicles()


def receive_opening_stock(company, warehouse):
	rows = [(code, qty, rate * 0.6) for code, _n, rate, qty in PARTS if qty]
	if not rows:
		return
	on_hand = frappe.db.get_value("Stock Entry", {"remarks": f"Opening stock {TAG}", "docstatus": 1}, "name")
	if on_hand:
		return
	entry = frappe.get_doc({
		"doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "company": company,
		"posting_date": add_days(nowdate(), -30), "set_posting_time": 1, "remarks": f"Opening stock {TAG}",
		"items": [{"item_code": code, "qty": qty, "t_warehouse": warehouse, "basic_rate": rate} for code, qty, rate in rows],
	})
	entry.insert(ignore_permissions=True)
	entry.submit()


def create_vehicles():
	for idx, make, model, year, reg, vin, colour, mileage, vtype, fuel in VEHICLES:
		if frappe.db.exists("Vehicle Master", {"registration_number": reg}):
			continue
		frappe.get_doc({
			"doctype": "Vehicle Master", "customer": f"{CUSTOMERS[idx][0]} {TAG}", "make": make, "model": model,
			"year": year, "registration_number": reg, "vin": vin, "color": colour, "current_mileage": mileage,
			"vehicle_type": vtype, "fuel_type": fuel, "notes": NOTE,
			"registration_expiry": add_days(nowdate(), 200),
		}).insert(ignore_permissions=True)


def vehicle_by_reg(reg):
	return frappe.db.get_value("Vehicle Master", {"registration_number": reg}, "name")


# ------------------------------------------------------------------ lifecycle steps
def book_in(reg, complaint, service_type, days_ago=0, mileage_extra=500, priority="Medium"):
	_as(RECEPTION)
	vehicle = frappe.get_doc("Vehicle Master", vehicle_by_reg(reg))
	job = frappe.get_doc({
		"doctype": "Workshop Job Card", "vehicle": vehicle.name,
		"intake_datetime": add_to_date(now_datetime(), days=-days_ago),
		"current_mileage": vehicle.current_mileage + mileage_extra, "service_type": service_type,
		"priority": priority, "complaint": complaint, "workshop_manager": MANAGER,
		"expected_delivery_date": add_days(nowdate(), 3), "intake_notes": NOTE,
	})
	job.insert()
	return job.name


def inspect(job, inspection_type, user, condition="Repair Required", hours=2, findings="", damage_points=2):
	_as(user)
	frappe.flags.args = frappe._dict(inspection_type=inspection_type, technician=user)
	inspection = mappers.make_vehicle_inspection(job)
	for idx, row in enumerate(inspection.checklist):
		row.condition = "Faulty" if idx < damage_points and condition == "Repair Required" else "OK"
		row.damage_found = 1 if row.condition == "Faulty" else 0
		if row.condition == "Faulty":
			row.remarks = findings or "Damage found during inspection"
	inspection.overall_condition = condition
	inspection.estimated_labour_hours = hours
	inspection.findings = findings
	inspection.recommendations = findings
	inspection.insert()
	inspection.submit()
	frappe.flags.args = None
	return inspection.name


def assess(job, parts, labour, user=MANAGER, recommendation="Repair as per estimate."):
	_as(user)
	assessment = mappers.make_damage_assessment(job)
	if not assessment.damage_items:
		assessment.append("damage_items", {"damage_area": "Front", "trade": "Mechanic", "severity": "Moderate",
			"description": "Damage recorded during inspection"})
	assessment.set("parts", [])
	for code, qty in parts:
		assessment.append("parts", {"item_code": code, "qty": qty})
	assessment.set("labour", [])
	for trade, description, hours in labour:
		assessment.append("labour", {"trade": trade, "description": description, "hours": hours})
	assessment.recommendation = recommendation
	assessment.insert()
	assessment.submit()
	return assessment.name


def quote(job, user=MANAGER):
	_as(user)
	quotation = mappers.make_quotation(job)
	quotation.insert()
	quotation.submit()
	return quotation.name


def send_and_decide(job, decision, remarks=None, user=RECEPTION):
	_as(user)
	actions.mark_quotation_sent(job, channel="In person")
	if decision:
		actions.record_customer_approval(job, decision, remarks)


def request_parts(job, user=STORE):
	_as(user)
	request = mappers.make_material_request(job)
	if not request.items:
		return None
	request.insert()
	request.submit()
	return request.name


def purchase_parts(material_request, user=PURCHASE):
	"""Material Request -> Purchase Order -> Purchase Receipt, with the Job Card carried through."""
	from erpnext.stock.doctype.material_request.material_request import make_purchase_order

	_as(user)
	order = make_purchase_order(material_request)
	order.supplier = f"Al-Jazirah Auto Parts {TAG}"
	order.schedule_date = add_days(nowdate(), 1)
	for item in order.items:
		item.rate = item.rate or flt(frappe.db.get_value("Item Price", {"item_code": item.item_code}, "price_list_rate")) * 0.6 or 500
	order.insert()
	order.submit()

	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	_as(STORE)
	receipt = make_purchase_receipt(order.name)
	receipt.insert()
	receipt.submit()
	return order.name, receipt.name


def issue_parts(job, user=STORE):
	_as(user)
	entry = mappers.make_parts_issue(job)
	if not entry.items:
		return None
	entry.insert()
	entry.submit()
	return entry.name


def assign_tasks(job, tasks, user=MANAGER):
	_as(user)
	names = []
	for trade, technician, subject, hours in tasks:
		names.append(actions.create_repair_task(job, trade, technician, subject, hours))
	return names


def do_repair(job, task_updates, user=MANAGER):
	_as(user)
	actions.start_repair(job)
	for technician, updates in task_updates.items():
		_as(technician)
		actions.update_repair_progress(job, updates)
	_as(user)
	actions.request_quality_check(job)


def quality_check(job, result, remarks="", user=QC):
	_as(user)
	frappe.flags.args = frappe._dict(inspection_type=C.QC_TYPE, qc_result=result, technician=user)
	inspection = mappers.make_vehicle_inspection(job)
	for row in inspection.checklist:
		row.condition = "OK" if result == C.QC_PASSED else ("Faulty" if row.idx == 1 else "OK")
	inspection.qc_result = result
	inspection.remarks = remarks
	inspection.insert()
	inspection.submit()
	frappe.flags.args = None
	return inspection.name


def invoice_and_pay(job, pay=True, user=ACCOUNTS):
	_as(user)
	invoice = mappers.make_sales_invoice(job)
	invoice.insert()
	invoice.submit()
	if not pay:
		return invoice.name, None
	payment = mappers.make_payment_entry(job)
	payment.mode_of_payment = frappe.db.get_value("Mode of Payment", {"type": "Bank"}, "name") or "Cash"
	payment.reference_no = f"DEMO-{invoice.name}"
	payment.reference_date = nowdate()
	if not payment.paid_to:
		payment.paid_to = frappe.db.get_value("Account", {"company": _settings().company, "account_type": "Bank", "is_group": 0}, "name")
	payment.insert()
	payment.submit()
	return invoice.name, payment.name


def release(job, notes="Vehicle handed over to the customer.", user=RECEPTION):
	_as(user)
	return actions.release_vehicle(job, notes=notes)


# ------------------------------------------------------------------ scenarios
def create_demo():
	"""Build the demo workshop. Safe to run twice: existing records are kept."""
	frappe.flags.in_demo = True
	created_users = create_users()
	create_masters()
	built = []

	# 1. Complete lifecycle, delivered: Toyota Camry accident repair.
	if not frappe.db.exists("Workshop Job Card", {"vehicle": vehicle_by_reg("ABC-1234"), "released": 1}):
		job = book_in("ABC-1234", "Front-end damage after a parking collision. Headlamp not working.",
			"Accident Repair", days_ago=12, mileage_extra=0)
		inspect(job, "Denter", DENTER, hours=6, findings="Front bumper cracked, bonnet creased beyond repair.")
		inspect(job, "Electrician", ELECTRICIAN, hours=2, findings="RH headlamp assembly broken, wiring intact.")
		assess(job, parts=[("DEMO-BUMPER-CAM", 1), ("DEMO-HEADLAMP-CAM", 1), ("DEMO-BONNET-CAM", 1)],
			labour=[("Denter", "Replace front bumper and bonnet", 6),
					("Electrician", "Replace RH headlamp assembly and align", 2)])
		quote(job)
		send_and_decide(job, C.APPROVAL_APPROVED)
		# The bonnet is not in stock: request it, buy it in, receive it, then issue everything.
		request = request_parts(job)
		if request:
			purchase_parts(request)
		issue_parts(job)
		assign_tasks(job, [
			("Denter", DENTER, "Replace front bumper cover and bonnet", 6),
			("Electrician", ELECTRICIAN, "Replace RH headlamp assembly and align", 2),
		])
		tasks = frappe.get_all("Task", filters={"aw_job_card": job}, fields=["name", "aw_technician"])
		do_repair(job, {
			DENTER: [{"task": t.name, "status": "Completed", "progress": 100, "labour_hours": 6.5}
					 for t in tasks if t.aw_technician == DENTER],
			ELECTRICIAN: [{"task": t.name, "status": "Completed", "progress": 100, "labour_hours": 2}
						  for t in tasks if t.aw_technician == ELECTRICIAN],
		})
		quality_check(job, C.QC_PASSED, "Panel gaps correct, headlamp aligned, road test clear.")
		invoice_and_pay(job)
		release(job)
		built.append(("Delivered", job))

	# 2. Awaiting the customer's decision on a quotation.
	if not frappe.db.exists("Workshop Job Card", {"vehicle": vehicle_by_reg("TRD-9012"), "released": 0}):
		job = book_in("TRD-9012", "Scraped front left fender against a wall.", "Body and Paint", days_ago=3)
		inspect(job, "Denter", DENTER, hours=5, findings="Front LH fender creased, paint damaged.")
		assess(job, parts=[("DEMO-FENDER-SON", 1)], labour=[("Denter", "Replace and paint front LH fender", 5)])
		quote(job)
		send_and_decide(job, None)
		built.append(("Awaiting Approval", job))

	# 3. Approved, waiting for a part that must be bought in.
	if not frappe.db.exists("Workshop Job Card", {"vehicle": vehicle_by_reg("ABC-5678"), "released": 0}):
		job = book_in("ABC-5678", "Battery warning light on, vehicle does not charge.", "Electrical Repair",
			days_ago=2, priority="High")
		inspect(job, "Electrician", ELECTRICIAN, hours=3, findings="Alternator output low, needs replacement.")
		assess(job, parts=[("DEMO-ALT-PATROL", 1)], labour=[("Electrician", "Replace alternator and test charging", 3)])
		quote(job)
		send_and_decide(job, C.APPROVAL_APPROVED)
		request_parts(job)
		built.append(("Parts Pending", job))

	# 4. Repair under way.
	if not frappe.db.exists("Workshop Job Card", {"vehicle": vehicle_by_reg("SAU-3344"), "released": 0}):
		job = book_in("SAU-3344", "Brakes squealing and service due.", "General Service", days_ago=1)
		inspect(job, "Mechanic", MECHANIC, hours=3, findings="Front brake pads worn, oil service due.")
		assess(job, parts=[("DEMO-BRAKEPAD-FR", 1), ("DEMO-OILFILTER", 1)],
			labour=[("Mechanic", "Replace front brake pads and carry out oil service", 3)])
		quote(job)
		send_and_decide(job, C.APPROVAL_APPROVED)
		issue_parts(job)
		assign_tasks(job, [("Mechanic", MECHANIC, "Replace front brake pads and oil service", 3)])
		_as(MANAGER)
		actions.start_repair(job)
		task = frappe.db.get_value("Task", {"aw_job_card": job}, "name")
		_as(MECHANIC)
		actions.update_repair_progress(job, [{"task": task, "status": "Working", "progress": 40, "labour_hours": 1.5}])
		built.append(("Work In Progress", job))

	# 5. Waiting for the final quality check.
	if not frappe.db.exists("Workshop Job Card", {"vehicle": vehicle_by_reg("SAU-7788"), "released": 0}):
		job = book_in("SAU-7788", "Air conditioning not cooling.", "AC Repair", days_ago=4)
		inspect(job, "Mechanic", MECHANIC, hours=4, findings="AC compressor clutch faulty, gas low.")
		assess(job, parts=[("DEMO-OILFILTER", 1)], labour=[("Mechanic", "Overhaul AC system and regas", 4)])
		quote(job)
		send_and_decide(job, C.APPROVAL_APPROVED)
		issue_parts(job)
		assign_tasks(job, [("Mechanic", MECHANIC, "Overhaul AC system and regas", 4)])
		task = frappe.db.get_value("Task", {"aw_job_card": job}, "name")
		do_repair(job, {MECHANIC: [{"task": task, "status": "Completed", "progress": 100, "labour_hours": 4.5}]})
		built.append(("Quality Check", job))

	# 6. A returning customer: the Camry is booked in again, so its history shows.
	if not frappe.db.exists("Workshop Job Card", {"vehicle": vehicle_by_reg("ABC-1234"), "released": 0}):
		job = book_in("ABC-1234", "Routine service, customer reports a rattle over speed bumps.",
			"General Service", days_ago=0, mileage_extra=2200)
		built.append(("Open", job))

	frappe.set_user("Administrator")
	frappe.db.commit()
	for status, job in built:
		print(f"  {job}  {status}")
	print(f"Demo ready: {len(built)} Job Card(s).")
	if created_users:
		print(f"Demo users created: {', '.join(created_users)}")
		print(f"Their password for this run: {demo_password()}  (set AW_DEMO_PASSWORD to choose your own)")
	else:
		print("Demo users already existed; their passwords were left unchanged.")
	return built


def drop_demo():
	"""Delete every demo record.

	Job Cards are taken down one at a time, newest first, so that at each step the
	workflow rules are satisfied rather than bypassed: the Job Card is put back to
	Inspection Completed with its system links cleared, which is a state in which
	cancelling its quotation, assessment and inspections is legitimate.
	"""
	frappe.set_user("Administrator")
	vehicles = frappe.get_all("Vehicle Master", filters={"notes": NOTE}, pluck="name")
	jobs = frappe.get_all(
		"Workshop Job Card", filters={"vehicle": ["in", vehicles or [""]]}, pluck="name", order_by="creation desc"
	)

	for job in jobs:
		_reset_job(job)
		# Unwound in the reverse order of the business flow, so no step leaves the
		# stock ledger negative and no document is removed while another depends on it:
		# money, then consumption, then receiving, then ordering, then the paperwork.
		for doctype, field in (
			("Payment Entry", "aw_job_card"),
			("Sales Invoice", "aw_job_card"),
			("Stock Entry", "aw_job_card"),
		):
			for name in frappe.get_all(doctype, filters={field: job}, pluck="name"):
				_remove(doctype, name)
		for doctype in ("Purchase Receipt", "Purchase Order"):
			for name in _job_purchase_docs(doctype, job):
				_remove(doctype, name)
		for doctype, field in (
			("Damage Assessment", "job_card"),
			("Vehicle Inspection", "job_card"),
			("Quotation", "aw_job_card"),
			("Material Request", "aw_job_card"),
			("Task", "aw_job_card"),
		):
			for name in frappe.get_all(doctype, filters={field: job}, pluck="name"):
				_remove(doctype, name)
		frappe.db.set_value("Workshop Job Card", job, "status", C.OPEN, update_modified=False)
		_remove("Workshop Job Card", job)

	# Purchasing and opening stock reference the demo items but not a Job Card.
	for doctype in ("Purchase Receipt", "Purchase Order", "Stock Entry"):
		for name in _demo_docs_by_item(doctype):
			_remove(doctype, name)
	for vehicle in vehicles:
		_remove("Vehicle Master", vehicle)
	for doctype, field in (("Customer", "customer_name"), ("Supplier", "supplier_name")):
		for name in frappe.get_all(doctype, filters={field: ["like", f"%{TAG}"]}, pluck="name"):
			_remove(doctype, name)
	for code, *_rest in PARTS:
		_remove("Item", code)
	frappe.db.commit()
	print("Demo data removed. Demo users were kept; delete them manually if they are not wanted.")


def _reset_job(job):
	from automotive_workshop.automotive_workshop.doctype.workshop_job_card.workshop_job_card import SYSTEM_FIELDS

	meta = frappe.get_meta("Workshop Job Card")
	numeric = ("Currency", "Float", "Int", "Check")
	reset = {f: (0 if meta.get_field(f).fieldtype in numeric else None) for f in SYSTEM_FIELDS}
	reset["status"] = C.INSPECTION_COMPLETED
	frappe.db.set_value("Workshop Job Card", job, reset, update_modified=False)


def _remove(doctype, name):
	if not frappe.db.exists(doctype, name):
		return
	doc = frappe.get_doc(doctype, name)
	if doc.meta.is_submittable and doc.docstatus == 1:
		doc.flags.ignore_permissions = True
		doc.cancel()
	frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, delete_permanently=True)


def _job_purchase_docs(doctype, job):
	"""Buying documents whose lines carry this Job Card, newest first."""
	names = frappe.get_all(f"{doctype} Item", filters={"aw_job_card": job}, pluck="parent", distinct=True)
	if not names:
		return []
	return frappe.get_all(doctype, filters={"name": ["in", names]}, pluck="name", order_by="creation desc")


def _demo_docs_by_item(doctype):
	"""Documents that carry a demo part, newest first."""
	child = "Stock Entry Detail" if doctype == "Stock Entry" else f"{doctype} Item"
	names = frappe.get_all(child, filters={"item_code": ["like", "DEMO-%"]}, pluck="parent", distinct=True)
	if not names:
		return []
	return frappe.get_all(doctype, filters={"name": ["in", names]}, pluck="name", order_by="creation desc")
