// Droit de timbre (paiement en espèces) : calculé côté serveur à l'enregistrement, voir unicare/accounts/droit_timbre.py.
frappe.ui.form.on("Sales Invoice", {
	unicare_paiement_especes(frm) {
		if (frm.doc.docstatus === 0) {
			frappe.show_alert({
				message: frm.doc.unicare_paiement_especes
					? __("Le droit de timbre sera ajouté à l'enregistrement.")
					: __("Le droit de timbre sera retiré à l'enregistrement."),
				indicator: "blue",
			});
		}
	},
});
