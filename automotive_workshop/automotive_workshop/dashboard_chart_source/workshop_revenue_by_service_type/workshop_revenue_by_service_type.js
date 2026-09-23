frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Workshop Revenue by Service Type"] = {
	method: "automotive_workshop.automotive_workshop.dashboard_chart_source.workshop_revenue_by_service_type.workshop_revenue_by_service_type.get",
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 0,
		},
	],
};
