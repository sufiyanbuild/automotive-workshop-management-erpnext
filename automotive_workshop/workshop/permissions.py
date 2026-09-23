"""Row-level visibility for technicians.

Denters, mechanics and electricians see:

  * every Job Card and Damage Assessment for a vehicle still in the workshop,
    because any of them may be called to inspect or work on a live job, and
  * only the inspections and repair tasks that are their own.

Once a vehicle is released, its Job Card stays visible only to the technicians
who actually worked on it, so the service history is not open to everyone.
Every other workshop role keeps the normal DocType permissions.
"""

import frappe

from automotive_workshop.workshop import constants as C


def is_supervisor(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)) & set(C.SUPERVISORY_ROLES))


def is_restricted_technician(user=None):
	user = user or frappe.session.user
	if is_supervisor(user):
		return False
	return bool(set(frappe.get_roles(user)) & set(C.TECHNICIAN_ROLES))


def _assigned_jobs_sql(user):
	u = frappe.db.escape(user)
	return f"""(select vi.job_card from `tabVehicle Inspection` vi where vi.technician = {u})
		union (select t.aw_job_card from `tabTask` t where t.aw_technician = {u} and t.aw_job_card is not null)"""


def job_card_query(user=None):
	user = user or frappe.session.user
	if not is_restricted_technician(user):
		return ""
	return f"(`tabWorkshop Job Card`.released = 0 or `tabWorkshop Job Card`.name in ({_assigned_jobs_sql(user)}))"


def inspection_query(user=None):
	user = user or frappe.session.user
	if not is_restricted_technician(user):
		return ""
	return f"`tabVehicle Inspection`.technician = {frappe.db.escape(user)}"


def assessment_query(user=None):
	user = user or frappe.session.user
	if not is_restricted_technician(user):
		return ""
	return f"""`tabDamage Assessment`.job_card in (
		select jc.name from `tabWorkshop Job Card` jc where jc.released = 0
		union ({_assigned_jobs_sql(user)}))"""


def task_query(user=None):
	user = user or frappe.session.user
	if not is_restricted_technician(user):
		return ""
	return f"`tabTask`.aw_technician = {frappe.db.escape(user)}"


def _job_visible(job_card, user):
	"""True while the vehicle is in the workshop, or if the technician worked on it."""
	if not job_card:
		return False
	if not frappe.db.get_value("Workshop Job Card", job_card, "released"):
		return True
	return bool(
		frappe.db.exists("Vehicle Inspection", {"job_card": job_card, "technician": user})
		or frappe.db.exists("Task", {"aw_job_card": job_card, "aw_technician": user})
	)


def job_card_has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if not is_restricted_technician(user) or doc.is_new():
		return True
	return _job_visible(doc.name, user)


def inspection_has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if not is_restricted_technician(user) or doc.is_new():
		return True
	return doc.technician == user


def assessment_has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if not is_restricted_technician(user) or doc.is_new():
		return True
	return _job_visible(doc.job_card, user)


def task_has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if not is_restricted_technician(user):
		return True
	# Tasks outside the workshop are not a technician's business.
	return bool(doc.get("aw_job_card")) and doc.get("aw_technician") == user
