// Copyright (c) 2026, IntraPro and contributors
// For license information, please see license.txt

frappe.ui.form.on("Recette de Conditionnement", {
	refresh(frm) {
		frm.set_query("produit_fini", () => ({
			filters: {
				custom_type_conditionnement: "Produit fini",
				is_stock_item: 1,
				disabled: 0,
			},
		}));
		frm.set_query("item_code", "ingredients", () => ({
			filters: {
				is_stock_item: 1,
				disabled: 0,
				custom_type_conditionnement: ["in", ["Fût", "Conditionnement"]],
			},
		}));
	},
});

frappe.ui.form.on("Ingredient Recette", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) {
			return;
		}
		frappe.db.get_value("Item", row.item_code, ["custom_type_conditionnement", "stock_uom", "item_name"], (r) => {
			if (!r) {
				return;
			}
			if (r.custom_type_conditionnement === "Fût") {
				frappe.model.set_value(cdt, cdn, "type_ingredient", "Fût");
			} else if (r.custom_type_conditionnement === "Conditionnement") {
				frappe.model.set_value(cdt, cdn, "type_ingredient", "Conditionnement");
			}
			if (r.stock_uom) {
				frappe.model.set_value(cdt, cdn, "uom", r.stock_uom);
			}
			if (r.item_name) {
				frappe.model.set_value(cdt, cdn, "item_name", r.item_name);
			}
		});
	},
});
