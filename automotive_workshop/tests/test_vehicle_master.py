"""Vehicle Master validation."""

import frappe

from automotive_workshop.tests.base import WorkshopTestCase, make_vehicle


class TestVehicleMaster(WorkshopTestCase):
	def test_registration_is_normalised_and_title_is_built(self):
		vehicle = make_vehicle("zza 1234")
		self.assertEqual(vehicle.registration_number, "ZZA-1234")
		self.assertEqual(vehicle.vehicle_title, "Toyota Camry 2021")

	def test_arabic_plate_and_arabic_digits_are_accepted(self):
		vehicle = make_vehicle("ن ه و ١٢٣٤")
		self.assertEqual(vehicle.registration_number, "نهو-1234")

	def test_invalid_registration_is_rejected(self):
		for plate in ("ABCDE-12345", "!!!", "ABC-12345"):
			with self.assertRaises(frappe.ValidationError, msg=plate):
				make_vehicle(plate)

	def test_duplicate_registration_is_rejected(self):
		make_vehicle("DUP-1111")
		with self.assertRaises(frappe.DuplicateEntryError):
			make_vehicle("dup 1111")

	def test_vin_must_be_a_valid_vin(self):
		vehicle = make_vehicle("VIN-1001", vin="jtdbe32k123456789")
		self.assertEqual(vehicle.vin, "JTDBE32K123456789")
		with self.assertRaises(frappe.ValidationError):
			make_vehicle("VIN-1002", vin="TOO-SHORT")
		with self.assertRaises(frappe.ValidationError):
			make_vehicle("VIN-1003", vin="JTDBE32KIOQ456789")  # I, O and Q never appear in a VIN

	def test_duplicate_vin_is_rejected(self):
		make_vehicle("VIN-2001", vin="JTDBE32K123456111")
		with self.assertRaises(frappe.DuplicateEntryError):
			make_vehicle("VIN-2002", vin="JTDBE32K123456111")

	def test_vehicle_without_vin_is_allowed_more_than_once(self):
		make_vehicle("NOV-1001")
		make_vehicle("NOV-1002")  # must not collide on an empty VIN

	def test_owner_cannot_change_while_a_job_is_open(self):
		job = self.new_job()
		vehicle = frappe.get_doc("Vehicle Master", job.vehicle)
		other = frappe.get_doc({
			"doctype": "Customer", "customer_name": "AWT Second Customer", "customer_type": "Individual",
			"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
			"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
		}).insert(ignore_permissions=True)
		vehicle.customer = other.name
		self.assertRaises(frappe.ValidationError, vehicle.save)

	def test_vehicle_status_follows_the_job_card(self):
		job = self.new_job()
		self.assertEqual(frappe.db.get_value("Vehicle Master", job.vehicle, "status"), "In Workshop")
		self.assertEqual(frappe.db.get_value("Vehicle Master", job.vehicle, "current_mileage"), job.current_mileage)
