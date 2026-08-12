// Copyright (c) 2026, IntraPro and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reception de Matieres", {
	refresh(frm) {
		frm.set_query("purchase_order", () => {
			const filters = { docstatus: 1 };
			if (frm.doc.supplier) {
				filters.supplier = frm.doc.supplier;
			}
			return { filters };
		});
		frm.set_query("item_code", "items", () => ({
			filters: {
				is_stock_item: 1,
				disabled: 0,
				custom_type_conditionnement: ["in", ["Fût", "Conditionnement"]],
			},
		}));
	},
	warehouse(frm) {
		(frm.doc.items || []).forEach((row) => {
			if (!row.warehouse) {
				frappe.model.set_value(row.doctype, row.name, "warehouse", frm.doc.warehouse);
			}
		});
	},
	purchase_order(frm) {
		if (!frm.doc.purchase_order) {
			return;
		}

		const fill_from_po = () => {
			frappe.call({
				method:
					"unicare.conditionnement.doctype.reception_de_matieres.reception_de_matieres.get_items_from_purchase_order",
				args: {
					purchase_order: frm.doc.purchase_order,
					warehouse: frm.doc.warehouse,
				},
				freeze: true,
				freeze_message: __("Chargement des articles…"),
				callback(r) {
					if (!r.message) {
						return;
					}
					if (r.message.supplier) {
						frm.set_value("supplier", r.message.supplier);
					}
					frm.clear_table("items");
					(r.message.items || []).forEach((row) => {
						frm.add_child("items", row);
					});
					frm.refresh_field("items");
				},
			});
		};

		if ((frm.doc.items || []).some((row) => row.item_code)) {
			frappe.confirm(
				__("Remplacer les articles par ceux de la commande d'achat ?"),
				fill_from_po
			);
		} else {
			fill_from_po();
		}
	},
});

frappe.ui.form.on("Ligne Reception Matiere", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.warehouse && frm.doc.warehouse) {
			frappe.model.set_value(cdt, cdn, "warehouse", frm.doc.warehouse);
		}
		if (!row.item_code) {
			return;
		}
		frappe.db.get_value(
			"Item",
			row.item_code,
			["item_name", "stock_uom", "has_batch_no", "custom_type_conditionnement"],
			(r) => {
				if (!r) {
					return;
				}
				frappe.model.set_value(cdt, cdn, "item_name", r.item_name);
				frappe.model.set_value(cdt, cdn, "uom", r.stock_uom);
				frappe.model.set_value(cdt, cdn, "has_batch_no", r.has_batch_no);
				if (r.custom_type_conditionnement === "Conditionnement" && !row.warehouse) {
					frappe.db.get_single_value("Parametres Conditionnement", "warehouse_conditionnement").then((wh) => {
						if (wh) {
							frappe.model.set_value(cdt, cdn, "warehouse", wh);
						}
					});
				}
			}
		);
	},
});
