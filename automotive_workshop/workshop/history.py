import frappe
from frappe import _


@frappe.whitelist()
def get_service_history(vehicle, exclude=None):
	"""Job Cards for a vehicle, newest first, built from the transactional records."""
	frappe.has_permission("Vehicle Master", "read", vehicle, throw=True)
	filters = {"vehicle": vehicle}
	if exclude:
		filters["name"] = ["!=", exclude]
	return frappe.get_list(
		"Workshop Job Card",
		filters=filters,
		fields=["name", "intake_datetime", "service_type", "status", "current_stage", "complaint",
				"current_mileage", "invoice_total", "outstanding_amount", "released", "released_on", "currency"],
		order_by="intake_datetime desc",
		limit_page_length=100,
	)
