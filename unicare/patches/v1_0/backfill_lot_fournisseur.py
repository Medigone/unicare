# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe

from unicare.conditionnement.stock import get_lots_fournisseur_from_matieres


def execute():
	if not frappe.db.has_column("Batch", "custom_lot_fournisseur"):
		return

	_backfill_lots_reception()
	_backfill_lots_production()


def _backfill_lots_reception():
	for batch in frappe.get_all(
		"Batch", fields=["name", "custom_lot_fournisseur", "custom_origine"]
	):
		if batch.custom_origine == "Production":
			continue
		values = {}
		if not batch.custom_lot_fournisseur:
			values["custom_lot_fournisseur"] = batch.name
		if not batch.custom_origine:
			values["custom_origine"] = "Réception"
		if values:
			frappe.db.set_value("Batch", batch.name, values, update_modified=False)


def _backfill_lots_production():
	ordres = frappe.get_all(
		"Ordre de Conditionnement",
		filters={"lot_pf": ["is", "set"]},
		fields=["name", "lot_pf"],
	)
	for ordre in ordres:
		if not ordre.lot_pf or not frappe.db.exists("Batch", ordre.lot_pf):
			continue
		if frappe.db.get_value("Batch", ordre.lot_pf, "custom_lot_fournisseur"):
			continue
		doc = frappe.get_doc("Ordre de Conditionnement", ordre.name)
		lot = get_lots_fournisseur_from_matieres(doc.matieres)
		if lot:
			frappe.db.set_value(
				"Batch", ordre.lot_pf, "custom_lot_fournisseur", lot, update_modified=False
			)
