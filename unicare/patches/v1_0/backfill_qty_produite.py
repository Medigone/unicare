# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


def execute():
	create_custom_fields(
		{
			"Batch": [
				{
					"fieldname": "custom_qty_produite",
					"fieldtype": "Float",
					"insert_after": "custom_ordre_conditionnement",
					"label": "Quantité produite",
					"module": "Conditionnement",
					"read_only": 1,
				}
			]
		},
		update=True,
	)

	if not frappe.db.has_column("Batch", "custom_qty_produite"):
		return

	ordres = frappe.get_all(
		"Ordre de Conditionnement",
		filters={"lot_pf": ["is", "set"], "qty_reelle_pf": [">", 0]},
		fields=["name", "lot_pf", "qty_reelle_pf"],
	)
	for ordre in ordres:
		if not ordre.lot_pf or not frappe.db.exists("Batch", ordre.lot_pf):
			continue
		if flt(frappe.db.get_value("Batch", ordre.lot_pf, "custom_qty_produite")):
			continue
		frappe.db.set_value(
			"Batch",
			ordre.lot_pf,
			"custom_qty_produite",
			flt(ordre.qty_reelle_pf),
			update_modified=False,
		)
