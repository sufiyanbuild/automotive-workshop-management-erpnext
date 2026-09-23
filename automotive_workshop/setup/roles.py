import frappe

from automotive_workshop.workshop.constants import WORKSHOP_ROLES

# Standard ERPNext roles bundled with each workshop role, so department users
# can work the standard Buying, Stock, Selling and Accounts screens they need.
ROLE_PROFILES = {
	"Workshop Reception": ["Reception"],
	"Workshop Manager": ["Workshop Manager", "Sales User", "Projects User", "Stock User"],
	"Workshop Denter": ["Denter"],
	"Workshop Mechanic": ["Mechanic"],
	"Workshop Electrician": ["Electrician"],
	"Workshop Quality Inspector": ["Quality Inspector"],
	"Workshop Purchase": ["Purchase Department", "Purchase User"],
	"Workshop Store Keeper": ["Store Keeper", "Stock User"],
	"Workshop Accounts": ["Accounts Department", "Accounts User", "Sales User"],
	"Workshop Administrator": ["System Manager", "Workshop Manager"],
}


def create_roles():
	created = []
	for role in WORKSHOP_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
			created.append(role)
	return created


def create_role_profiles():
	for name, roles in ROLE_PROFILES.items():
		profile = frappe.get_doc("Role Profile", name) if frappe.db.exists("Role Profile", name) else frappe.new_doc("Role Profile")
		profile.role_profile = name
		existing = {r.role for r in profile.roles}
		for role in roles:
			if role not in existing and frappe.db.exists("Role", role):
				profile.append("roles", {"role": role})
		profile.save(ignore_permissions=True)
