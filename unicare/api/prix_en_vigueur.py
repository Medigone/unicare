# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Prix en vigueur d'un tarif : la ligne « Item Price » qu'une pièce reprend à sa date.

Même règle qu'ERPNext : une ligne vaut de `valid_from` à `valid_upto`, les deux jours compris. Une ligne réservée à un
client (vente) ou à un fournisseur (achat) l'emporte pour ce tiers et n'est jamais proposée aux autres. À égalité, la
plus récente l'emporte (`valid_from`, puis `modified`). Les lignes d'un lot (`batch_no`) ne servent qu'à ce lot : elles
sont laissées de côté ici.
"""

import frappe
from frappe.utils import getdate, nowdate

PRIX = "Item Price"
CHAMPS = [
	"name",
	"item_code",
	"price_list_rate",
	"uom",
	"valid_from",
	"valid_upto",
	"customer",
	"supplier",
	"batch_no",
	"note",
	"lead_time_days",
	"modified",
]


def lignes_tarif(liste, codes):
	"""Toutes les lignes de prix de ces articles dans le tarif, la plus récente d'abord."""
	if not liste or not codes:
		return []
	return frappe.get_all(
		PRIX,
		filters={"price_list": liste, "item_code": ["in", list(codes)]},
		fields=CHAMPS,
		order_by="valid_from desc, modified desc",
	)


def vaut_le(row, date):
	"""La ligne s'applique-t-elle à cette date ?"""
	return (not row.valid_from or getdate(row.valid_from) <= date) and (
		not row.valid_upto or getdate(row.valid_upto) >= date
	)


def tiers(row):
	return row.customer or row.supplier or None


def choisir(rows, date, client=None, fournisseur=None):
	"""Parmi des lignes déjà triées (la plus récente d'abord), celle en vigueur par article."""
	propres, generales = {}, {}
	for row in rows:
		if row.batch_no or not vaut_le(row, date):
			continue
		if not tiers(row):
			generales.setdefault(row.item_code, row)
		elif (client and row.customer == client) or (fournisseur and row.supplier == fournisseur):
			propres.setdefault(row.item_code, row)
	return {**generales, **propres}


def prix_en_vigueur(liste, codes, date=None, client=None, fournisseur=None):
	"""Par article, la ligne de prix que reprend une pièce de ce tiers à cette date (aujourd'hui par défaut)."""
	date = getdate(date) if date else getdate(nowdate())
	return choisir(lignes_tarif(liste, codes), date, client, fournisseur)
