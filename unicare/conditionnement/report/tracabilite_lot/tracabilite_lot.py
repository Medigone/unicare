# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	batch_no = filters.get("batch_no")
	if not batch_no:
		frappe.throw(_("Sélectionnez un lot."))

	columns = get_columns()
	data = get_data(batch_no)
	return columns, data


def get_columns():
	return [
		{"label": _("Sens"), "fieldname": "sens", "fieldtype": "Data", "width": 140},
		{
			"label": _("Ordre"),
			"fieldname": "ordre",
			"fieldtype": "Link",
			"options": "Ordre de Conditionnement",
			"width": 160,
		},
		{"label": _("Statut"), "fieldname": "statut", "fieldtype": "Data", "width": 120},
		{
			"label": _("Produit fini"),
			"fieldname": "produit_fini",
			"fieldtype": "Link",
			"options": "Item",
			"width": 140,
		},
		{"label": _("Nom produit"), "fieldname": "nom_produit", "fieldtype": "Data", "width": 180},
		{
			"label": _("Lot PF"),
			"fieldname": "lot_pf",
			"fieldtype": "Link",
			"options": "Batch",
			"width": 160,
		},
		{
			"label": _("Article consommé"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 140,
		},
		{
			"label": _("Lot MP"),
			"fieldname": "lot_mp",
			"fieldtype": "Link",
			"options": "Batch",
			"width": 140,
		},
		{"label": _("Qté réelle"), "fieldname": "qty_reelle", "fieldtype": "Float", "width": 110},
		{"label": _("Qté rebut"), "fieldname": "qty_rebut", "fieldtype": "Float", "width": 110},
		{"label": _("Qté PF"), "fieldname": "qty_reelle_pf", "fieldtype": "Float", "width": 110},
		{"label": _("Date"), "fieldname": "date_prevue", "fieldtype": "Date", "width": 110},
	]


def get_data(batch_no):
	data = []

	as_fg = frappe.get_all(
		"Ordre de Conditionnement",
		filters={"lot_pf": batch_no, "workflow_state": ["!=", "Annulé"]},
		fields=[
			"name",
			"workflow_state",
			"produit_fini",
			"nom_produit",
			"lot_pf",
			"qty_reelle_pf",
			"date_prevue",
		],
	)
	for ordre in as_fg:
		matieres = frappe.get_all(
			"Matiere Ordre Conditionnement",
			filters={"parent": ordre.name},
			fields=["item_code", "batch_no", "qty_reelle"],
		)
		if not matieres:
			data.append(
				{
					"sens": _("Lot PF → matières"),
					"ordre": ordre.name,
					"statut": ordre.workflow_state,
					"produit_fini": ordre.produit_fini,
					"nom_produit": ordre.nom_produit,
					"lot_pf": ordre.lot_pf,
					"qty_reelle_pf": ordre.qty_reelle_pf,
					"date_prevue": ordre.date_prevue,
				}
			)
			continue
		for row in matieres:
			data.append(
				{
					"sens": _("Lot PF → matières"),
					"ordre": ordre.name,
					"statut": ordre.workflow_state,
					"produit_fini": ordre.produit_fini,
					"nom_produit": ordre.nom_produit,
					"lot_pf": ordre.lot_pf,
					"item_code": row.item_code,
					"lot_mp": row.batch_no,
					"qty_reelle": row.qty_reelle,
					"qty_reelle_pf": ordre.qty_reelle_pf,
					"date_prevue": ordre.date_prevue,
				}
			)

	parents = frappe.get_all(
		"Matiere Ordre Conditionnement",
		filters={"batch_no": batch_no},
		fields=["parent", "item_code", "qty_reelle"],
	)
	seen = {row["ordre"] for row in data}
	for line in parents:
		if line.parent in seen:
			continue
		ordre = _get_ordre(line.parent)
		if not ordre:
			continue
		data.append(
			{
				"sens": _("Lot MP → produit fini"),
				"ordre": ordre.name,
				"statut": ordre.workflow_state,
				"produit_fini": ordre.produit_fini,
				"nom_produit": ordre.nom_produit,
				"lot_pf": ordre.lot_pf,
				"item_code": line.item_code,
				"lot_mp": batch_no,
				"qty_reelle": line.qty_reelle,
				"qty_reelle_pf": ordre.qty_reelle_pf,
				"date_prevue": ordre.date_prevue,
			}
		)
		seen.add(ordre.name)

	rebuts = frappe.get_all(
		"Rebut Ordre Conditionnement",
		filters={"batch_no": batch_no},
		fields=["parent", "item_code", "qty"],
	)
	for line in rebuts:
		ordre = _get_ordre(line.parent)
		if not ordre:
			continue
		data.append(
			{
				"sens": _("Lot MP → rebut"),
				"ordre": ordre.name,
				"statut": ordre.workflow_state,
				"produit_fini": ordre.produit_fini,
				"nom_produit": ordre.nom_produit,
				"lot_pf": ordre.lot_pf,
				"item_code": line.item_code,
				"lot_mp": batch_no,
				"qty_rebut": line.qty,
				"qty_reelle_pf": ordre.qty_reelle_pf,
				"date_prevue": ordre.date_prevue,
			}
		)

	return data


def _get_ordre(name):
	ordre = frappe.db.get_value(
		"Ordre de Conditionnement",
		name,
		[
			"name",
			"workflow_state",
			"produit_fini",
			"nom_produit",
			"lot_pf",
			"qty_reelle_pf",
			"date_prevue",
		],
		as_dict=True,
	)
	if not ordre or ordre.workflow_state == "Annulé":
		return None
	return ordre
