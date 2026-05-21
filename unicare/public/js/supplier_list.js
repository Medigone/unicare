const _has_indicator = frappe.has_indicator.bind(frappe);

frappe.has_indicator = function (doctype) {
	if (doctype === "Supplier") {
		return false;
	}
	return _has_indicator(doctype);
};

function get_supplier_statut_html(value) {
	if (value === "Actif") {
		return `<span class="indicator-pill green filterable no-indicator-dot ellipsis" data-filter="custom_statut,=,Actif">
			<span class="ellipsis">${__("Actif")}</span>
		</span>`;
	}
	if (value === "Exclu") {
		return `<span class="indicator-pill grey filterable no-indicator-dot ellipsis" data-filter="custom_statut,=,Exclu">
			<span class="ellipsis">${__("Exclu")}</span>
		</span>`;
	}
	return value || "";
}

frappe.listview_settings["Supplier"] = {
	formatters: {
		custom_statut(value) {
			return get_supplier_statut_html(value);
		},
	},
};
