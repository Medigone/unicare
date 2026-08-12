// Copyright (c) 2026, IntraPro and contributors
// For license information, please see license.txt

frappe.listview_settings["Ordre de Conditionnement"] = {
	get_indicator(doc) {
		const colors = {
			Brouillon: "blue",
			Préparé: "orange",
			"En production": "yellow",
			Terminé: "green",
			Annulé: "red",
		};
		const state = doc.workflow_state || "Brouillon";
		return [__(state), colors[state] || "gray", `workflow_state,=,${state}`];
	},
};
