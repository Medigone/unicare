// Copyright (c) 2026, IntraPro and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ordre de Conditionnement", {
	onload(frm) {
		if (frm.is_new()) {
			frappe.db.get_doc("Parametres Conditionnement").then((p) => {
				if (!frm.doc.warehouse_mp && p.warehouse_mp) {
					frm.set_value("warehouse_mp", p.warehouse_mp);
				}
				if (!frm.doc.warehouse_conditionnement && p.warehouse_conditionnement) {
					frm.set_value("warehouse_conditionnement", p.warehouse_conditionnement);
				}
				if (!frm.doc.warehouse_atelier && p.warehouse_atelier) {
					frm.set_value("warehouse_atelier", p.warehouse_atelier);
				}
				if (!frm.doc.warehouse_pf && p.warehouse_pf) {
					frm.set_value("warehouse_pf", p.warehouse_pf);
				}
				if (!frm.doc.warehouse_rebuts && p.warehouse_rebuts) {
					frm.set_value("warehouse_rebuts", p.warehouse_rebuts);
				}
			});
		}
	},
	refresh(frm) {
		frm.set_query("recette", () => ({
			filters: { actif: 1 },
		}));
		frm.set_query("lot_pf", () => ({
			filters: {
				item: frm.doc.produit_fini || "",
				disabled: 0,
			},
		}));
		frm.set_query("batch_no", "matieres", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				filters: {
					item: row.item_code,
					disabled: 0,
				},
			};
		});

		if (frm.doc.stock_entry_preparation) {
			frm.add_custom_button(
				__("Transfert préparation"),
				() => frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry_preparation),
				__("Écritures de stock")
			);
		}
		if (frm.doc.stock_entry_production) {
			frm.add_custom_button(
				__("Repack production"),
				() => frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry_production),
				__("Écritures de stock")
			);
		}
		if (frm.doc.lot_pf) {
			frm.add_custom_button(__("Lot PF"), () => frappe.set_route("Form", "Batch", frm.doc.lot_pf));
		}

		refresh_all_stocks(frm);
	},
	recette(frm) {
		charger_recette(frm);
	},
	qty_prevue(frm) {
		charger_recette(frm);
	},
	generer_lot_pf(frm) {
		if (!frm.doc.produit_fini) {
			frappe.msgprint(__("Sélectionnez d'abord une recette / un produit fini."));
			return;
		}

		const create_lot = () => {
			frappe.call({
				method: "unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement.generer_lot_pf",
				args: {
					produit_fini: frm.doc.produit_fini,
					ordre: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Création du lot…"),
				callback(r) {
					if (!r.message) {
						return;
					}
					frm.set_value("lot_pf", r.message);
					frappe.show_alert({
						message: __("Lot {0} créé", [r.message]),
						indicator: "green",
					});
				},
			});
		};

		if (frm.doc.lot_pf) {
			frappe.confirm(
				__("Un lot est déjà renseigné ({0}). Générer un nouveau lot ?", [frm.doc.lot_pf]),
				create_lot
			);
		} else {
			create_lot();
		}
	},
});

frappe.ui.form.on("Matiere Ordre Conditionnement", {
	batch_no(frm, cdt, cdn) {
		refresh_stock(frm, cdt, cdn);
	},
	warehouse(frm, cdt, cdn) {
		refresh_stock(frm, cdt, cdn);
	},
	item_code(frm, cdt, cdn) {
		refresh_stock(frm, cdt, cdn);
	},
});

frappe.ui.form.on("Checklist Preparation", {
	conforme(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.conforme) {
			frappe.model.set_value(cdt, cdn, "controle_par", frappe.session.user);
			frappe.model.set_value(cdt, cdn, "date_heure", frappe.datetime.now_datetime());
		}
	},
});

function charger_recette(frm) {
	if (!frm.doc.recette || !frm.doc.qty_prevue) {
		return;
	}
	frappe.call({
		method: "unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement.charger_recette",
		args: {
			recette: frm.doc.recette,
			qty_prevue: frm.doc.qty_prevue,
		},
		callback(r) {
			if (!r.message) {
				return;
			}
			frm.set_value("produit_fini", r.message.produit_fini);
			frm.set_value("uom", r.message.uom);
			frm.clear_table("matieres");
			(r.message.matieres || []).forEach((row) => {
				frm.add_child("matieres", row);
			});
			frm.refresh_field("matieres");
			refresh_all_stocks(frm);
		},
	});
}

function warehouse_for_stock(frm, row) {
	const state = frm.doc.workflow_state;
	if (["Préparé", "En production"].includes(state) && frm.doc.warehouse_atelier) {
		return frm.doc.warehouse_atelier;
	}
	return row.warehouse;
}

function refresh_all_stocks(frm) {
	const rows = frm.doc.matieres || [];
	if (!rows.length) {
		return;
	}

	let pending = rows.length;
	const done = () => {
		pending -= 1;
		if (pending <= 0) {
			frm.refresh_field("matieres");
		}
	};

	rows.forEach((row) => {
		const warehouse = warehouse_for_stock(frm, row);
		if (!row.item_code || !warehouse) {
			row.stock_disponible = 0;
			done();
			return;
		}
		frappe.call({
			method: "unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement.get_stock_disponible",
			args: {
				item_code: row.item_code,
				warehouse: warehouse,
				batch_no: row.batch_no,
			},
			callback(r) {
				row.stock_disponible = r.message || 0;
				done();
			},
			error: done,
		});
	});
}

function refresh_stock(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const warehouse = warehouse_for_stock(frm, row);
	if (!row.item_code || !warehouse) {
		frappe.model.set_value(cdt, cdn, "stock_disponible", 0);
		return;
	}
	frappe.call({
		method: "unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement.get_stock_disponible",
		args: {
			item_code: row.item_code,
			warehouse: warehouse,
			batch_no: row.batch_no,
		},
		callback(r) {
			frappe.model.set_value(cdt, cdn, "stock_disponible", r.message || 0);
		},
	});
}
