# Copyright (c) 2026, Sufiyan Shaikh and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_link_to_form

# Arabic-Indic and Eastern Arabic-Indic digits, normalised to ASCII.
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
PLATE = re.compile(
	r"^(?:(?P<l1>[A-Z]{1,3}|[ء-ي]{1,3})-?(?P<d1>\d{1,4})|(?P<d2>\d{1,4})-?(?P<l2>[A-Z]{1,3}|[ء-ي]{1,3}))$"
)
VIN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def normalise_registration(value):
	value = (value or "").translate(DIGITS).upper()
	return re.sub(r"[\s\-_.]+", "", value)


def format_registration(value):
	"""Validate a Saudi plate and return it as LETTERS-DIGITS, or None if invalid."""
	match = PLATE.match(normalise_registration(value))
	if not match:
		return None
	letters = match.group("l1") or match.group("l2")
	digits = match.group("d1") or match.group("d2")
	return f"{letters}-{digits}"


class VehicleMaster(Document):
	def validate(self):
		self.validate_registration()
		self.validate_vin()
		self.set_title()
		self.validate_owner_change()
		if self.year and not 1950 <= cint(self.year) <= frappe.utils.getdate().year + 1:
			frappe.throw(_("Model Year {0} is not a valid year.").format(self.year))

	def validate_registration(self):
		formatted = format_registration(self.registration_number)
		if not formatted:
			frappe.throw(
				_("Registration Number {0} is not a valid Saudi plate. Enter 1 to 3 letters and 1 to 4 digits, for example ABC-1234.").format(
					frappe.bold(self.registration_number)),
				title=_("Invalid Registration Number"),
			)
		self.registration_number = formatted
		duplicate = frappe.db.get_value(
			"Vehicle Master", {"registration_number": formatted, "name": ["!=", self.name]}, ["name", "customer_name"], as_dict=True
		)
		if duplicate:
			frappe.throw(
				_("Registration Number {0} is already recorded on vehicle {1} ({2}).").format(
					frappe.bold(formatted), get_link_to_form("Vehicle Master", duplicate.name), duplicate.customer_name),
				frappe.DuplicateEntryError, title=_("Duplicate Registration"),
			)

	def validate_vin(self):
		vin = re.sub(r"\s+", "", (self.vin or "")).upper()
		if not vin:
			self.vin = None
			return
		if not VIN.match(vin):
			frappe.throw(
				_("VIN {0} is not valid. A VIN has exactly 17 letters and digits and never contains I, O or Q.").format(frappe.bold(vin)),
				title=_("Invalid VIN"),
			)
		duplicate = frappe.db.get_value("Vehicle Master", {"vin": vin, "name": ["!=", self.name]}, ["name", "registration_number"], as_dict=True)
		if duplicate:
			frappe.throw(
				_("VIN {0} already belongs to vehicle {1} ({2}).").format(
					frappe.bold(vin), get_link_to_form("Vehicle Master", duplicate.name), duplicate.registration_number),
				frappe.DuplicateEntryError, title=_("Duplicate VIN"),
			)
		self.vin = vin

	def set_title(self):
		parts = [self.make, self.model, str(self.year) if self.year else None]
		self.vehicle_title = " ".join(p.strip() for p in parts if p)

	def validate_owner_change(self):
		if not self.is_new() and self.has_value_changed("customer"):
			open_job = frappe.db.get_value("Workshop Job Card", {"vehicle": self.name, "released": 0}, "name")
			if open_job:
				frappe.throw(
					_("The owner cannot be changed while Job Card {0} is open for this vehicle.").format(
						get_link_to_form("Workshop Job Card", open_job)))
