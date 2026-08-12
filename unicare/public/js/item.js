// Copyright (c) 2026, IntraPro and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item", {
	onload(frm) {
		set_item_code_auto(frm);
	},
	refresh(frm) {
		set_item_code_auto(frm);
	},
});

function set_item_code_auto(frm) {
	if (!frm.is_new()) {
		return;
	}

	frm.set_df_property("item_code", "reqd", 0);
	frm.set_df_property("item_code", "read_only", 1);
	frm.set_df_property(
		"item_code",
		"description",
		__("Généré automatiquement selon le Type conditionnement (FU / CO / PF / AU)")
	);

	if (!frm.doc.item_code) {
		frm.set_value("item_code", __("Auto"));
	}
}
