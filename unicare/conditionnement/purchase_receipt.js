// Copyright (c) 2026, IntraPro and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Receipt Item", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) {
			return;
		}

		frappe.db.get_value(
			"Item",
			row.item_code,
			["has_batch_no", "custom_type_conditionnement"],
			(r) => {
				if (!r) {
					return;
				}
				if (cint(r.has_batch_no)) {
					frappe.model.set_value(cdt, cdn, "use_serial_batch_fields", 1);
				}
				if (row.warehouse) {
					return;
				}
				const field =
					r.custom_type_conditionnement === "Conditionnement"
						? "warehouse_conditionnement"
						: r.custom_type_conditionnement === "Fût"
							? "warehouse_mp"
							: null;
				if (!field) {
					return;
				}
				frappe.db.get_single_value("Parametres Conditionnement", field).then((wh) => {
					if (wh) {
						frappe.model.set_value(cdt, cdn, "warehouse", wh);
					}
				});
			}
		);
	},
});
