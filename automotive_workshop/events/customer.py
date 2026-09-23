from frappe import _


def get_dashboard_data(data):
	data.setdefault("transactions", []).insert(0, {
		"label": _("Workshop"),
		"items": ["Vehicle Master", "Workshop Job Card"],
	})
	data.setdefault("non_standard_fieldnames", {}).update({"Vehicle Master": "customer", "Workshop Job Card": "customer"})
	return data
