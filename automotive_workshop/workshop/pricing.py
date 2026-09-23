import frappe
from frappe.utils import flt

from automotive_workshop.workshop.settings import get_settings


def get_price_list():
	return get_settings().selling_price_list or frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"


def get_part_rate(item_code):
	"""Selling rate for a part from the workshop price list (0 when none is set)."""
	return flt(frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": get_price_list(), "selling": 1}, "price_list_rate"))
