import frappe
from frappe import _


def get_settings():
	return frappe.get_cached_doc("Workshop Settings")


def require_setting(fieldname):
	"""Return a Workshop Settings value, or stop with an instruction to configure it."""
	settings = get_settings()
	value = settings.get(fieldname)
	if not value:
		label = settings.meta.get_label(fieldname)
		frappe.throw(
			_("Please set {0} in Workshop Settings before continuing.").format(frappe.bold(_(label))),
			title=_("Workshop Settings Incomplete"),
		)
	return value


def get_company():
	return get_settings().company or frappe.defaults.get_user_default("Company")
