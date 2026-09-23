"""Custom fields on standard ERPNext DocTypes. All are prefixed aw_.

Each standard document gets a back-reference to the Workshop Job Card, which is
the single anchor; the Job Card itself stores only the links it needs to show
its own status (quotation, invoice, QC).
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

JOB = {"fieldname": "aw_job_card", "label": "Workshop Job Card", "fieldtype": "Link",
	   "options": "Workshop Job Card", "read_only": 1, "no_copy": 1, "search_index": 1, "in_standard_filter": 1}
VEHICLE = {"fieldname": "aw_vehicle", "label": "Vehicle", "fieldtype": "Link", "options": "Vehicle Master",
		   "read_only": 1, "no_copy": 1}


def _section(anchor, collapsible=0):
	return {"fieldname": "aw_workshop_section", "label": "Workshop", "fieldtype": "Section Break",
			"insert_after": anchor, "collapsible": collapsible}


def _item_job(anchor):
	return [{**JOB, "insert_after": anchor, "in_standard_filter": 0, "in_list_view": 0, "columns": 0}]


CUSTOM_FIELDS = {
	"Quotation": [
		_section("valid_till"),
		{**JOB, "insert_after": "aw_workshop_section"},
		{**VEHICLE, "insert_after": "aw_job_card"},
		{"fieldname": "aw_registration", "label": "Registration", "fieldtype": "Data", "read_only": 1,
		 "no_copy": 1, "insert_after": "aw_vehicle"},
		{"fieldname": "aw_column_break", "fieldtype": "Column Break", "insert_after": "aw_registration"},
		{"fieldname": "aw_customer_approval", "label": "Customer Approval", "fieldtype": "Select",
		 "options": "\nPending\nApproved\nRejected\nRevision Requested", "read_only": 1, "no_copy": 1,
		 "allow_on_submit": 1, "in_list_view": 1, "in_standard_filter": 1, "insert_after": "aw_column_break"},
		{"fieldname": "aw_sent_on", "label": "Sent to Customer On", "fieldtype": "Datetime", "read_only": 1,
		 "no_copy": 1, "allow_on_submit": 1, "insert_after": "aw_customer_approval"},
		{"fieldname": "aw_approved_on", "label": "Decision Recorded On", "fieldtype": "Datetime", "read_only": 1,
		 "no_copy": 1, "allow_on_submit": 1, "insert_after": "aw_sent_on"},
		{"fieldname": "aw_approval_remarks", "label": "Customer Remarks", "fieldtype": "Small Text", "read_only": 1,
		 "no_copy": 1, "allow_on_submit": 1, "insert_after": "aw_approved_on"},
	],
	"Sales Invoice": [
		_section("due_date"),
		{**JOB, "insert_after": "aw_workshop_section"},
		{**VEHICLE, "insert_after": "aw_job_card"},
		{"fieldname": "aw_quotation", "label": "Workshop Quotation", "fieldtype": "Link", "options": "Quotation",
		 "read_only": 1, "no_copy": 1, "insert_after": "aw_vehicle"},
	],
	"Payment Entry": [{**JOB, "insert_after": "reference_date"}],
	"Material Request": [
		{**JOB, "insert_after": "schedule_date"},
		{**VEHICLE, "insert_after": "aw_job_card"},
	],
	"Stock Entry": [{**JOB, "insert_after": "stock_entry_type"}],
	"Purchase Order Item": _item_job("material_request_item"),
	"Purchase Receipt Item": _item_job("purchase_order_item"),
	"Supplier Quotation Item": _item_job("material_request_item"),
	"Request for Quotation Item": _item_job("material_request_item"),
	"Task": [
		_section("description", collapsible=0),
		{**JOB, "insert_after": "aw_workshop_section", "read_only": 0, "set_only_once": 1},
		{**VEHICLE, "insert_after": "aw_job_card"},
		{"fieldname": "aw_customer", "label": "Customer", "fieldtype": "Link", "options": "Customer",
		 "read_only": 1, "no_copy": 1, "insert_after": "aw_vehicle"},
		{"fieldname": "aw_column_break", "fieldtype": "Column Break", "insert_after": "aw_customer"},
		{"fieldname": "aw_trade", "label": "Trade", "fieldtype": "Select", "options": "\nDenter\nMechanic\nElectrician",
		 "in_standard_filter": 1, "insert_after": "aw_column_break", "mandatory_depends_on": "eval:doc.aw_job_card"},
		{"fieldname": "aw_technician", "label": "Technician", "fieldtype": "Link", "options": "User",
		 "in_standard_filter": 1, "in_list_view": 1, "search_index": 1, "insert_after": "aw_trade",
		 "mandatory_depends_on": "eval:doc.aw_job_card"},
		{"fieldname": "aw_labour_hours", "label": "Labour Hours Worked", "fieldtype": "Float", "non_negative": 1,
		 "insert_after": "aw_technician", "depends_on": "eval:doc.aw_job_card"},
		{"fieldname": "aw_work_notes", "label": "Work Notes", "fieldtype": "Small Text",
		 "insert_after": "aw_labour_hours", "depends_on": "eval:doc.aw_job_card"},
	],
}


def setup_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, update=True)
