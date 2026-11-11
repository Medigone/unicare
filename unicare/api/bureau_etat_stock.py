# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""État du stock du poste de bureau (/bureau/stock) : une ligne par article et par dépôt, et son historique.

Les lignes sont les Bin d'ERPNext (quantité réelle, réservée, commandée, projetée, valeur), avec le seuil de
réapprovisionnement de l'article pour ce dépôt (Item Reorder). La liste est en lecture seule : le stock ne change que
par les pièces (réceptions, livraisons, mouvements, inventaires). La fiche montre le grand livre du couple et ses lots.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

from unicare.api.bureau_list import (
	BELL_FIELD,
	_parse,
	condition_filters,
	doctype_filter_fields,
	has_child_filter,
	page_bounds,
	row_bell,
	row_tags,
)
from unicare.api.bureau_postes import require_bureau
from unicare.api.bureau_stock import BIN, company, depots, ledger, lots_disponibles, readable

FIELDS = [
	"name",
	"modified",
	"creation",
	"item_code",
	"warehouse",
	"actual_qty",
	"reserved_qty",
	"ordered_qty",
	"projected_qty",
	"stock_value",
	"valuation_rate",
	"stock_uom",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = {
	"all": lambda row: True,
	"en_stock": lambda row: row["quantite"] > 0,
	"rupture": lambda row: row["quantite"] <= 0,
	"sous_seuil": lambda row: row["seuil"] is not None and row["quantite"] < row["seuil"],
	"negatif": lambda row: row["quantite"] < 0,
	"reserve": lambda row: row["reserve"] > 0,
}
SORT_KEYS = {
	"designation",
	"article",
	"depot",
	"groupe",
	"quantite",
	"reserve",
	"commande",
	"projete",
	"seuil",
	"valeur",
	"modified",
}


def _items(codes):
	if not codes:
		return {}
	rows = frappe.get_all(
		"Item",
		filters={"name": ["in", list(codes)]},
		fields=["name", "item_name", "item_group", "custom_type_conditionnement as type", "has_batch_no"],
	)
	return {row.name: row for row in rows}


def _seuils(codes):
	"""Seuil de réapprovisionnement par (article, dépôt)."""
	if not codes:
		return {}
	rows = frappe.get_all(
		"Item Reorder",
		filters={"parent": ["in", list(codes)], "parenttype": "Item"},
		fields=["parent", "warehouse", "warehouse_reorder_level"],
	)
	return {(row.parent, row.warehouse): flt(row.warehouse_reorder_level, 3) for row in rows if flt(row.warehouse_reorder_level)}


def _row(bin_row, items, seuils):
	item = items.get(bin_row.item_code) or frappe._dict()
	return {
		"name": bin_row.name,
		"modified": bin_row.modified,
		"creation": str(bin_row.creation),
		"tags": row_tags(bin_row),
		"cloche": row_bell(bin_row),
		"article": bin_row.item_code,
		"designation": item.item_name or bin_row.item_code,
		"groupe": item.item_group,
		"type": item.type,
		"avec_lot": cint(item.has_batch_no),
		"depot": bin_row.warehouse,
		"quantite": flt(bin_row.actual_qty, 3),
		"reserve": flt(bin_row.reserved_qty, 3),
		"commande": flt(bin_row.ordered_qty, 3),
		"projete": flt(bin_row.projected_qty, 3),
		"valeur": flt(bin_row.stock_value, 2),
		"taux": flt(bin_row.valuation_rate, 2),
		"unite": bin_row.stock_uom,
		"seuil": seuils.get((bin_row.item_code, bin_row.warehouse)),
	}


def order_lignes(rows, sort=None, direction=None):
	key = sort if sort in SORT_KEYS else "designation"
	descending = cstr(direction) == "desc" and sort in SORT_KEYS
	ordered = sorted(rows, key=lambda row: (cstr(row["designation"]).casefold(), cstr(row["depot"])))
	filled = [row for row in ordered if row.get(key) not in (None, "")]
	empty = [row for row in ordered if row.get(key) in (None, "")]

	def value(row):
		item = row[key]
		return item if isinstance(item, (int, float)) else cstr(item).casefold()

	return sorted(filled, key=value, reverse=descending) + empty


def _active(row):
	"""Une ligne vide (rien en stock, réservé, commandé ni prévu) n'apporte rien à la liste."""
	return any(row[key] for key in ("quantite", "reserve", "commande", "projete"))


@frappe.whitelist()
def get_etat_stock(view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None):
	"""Une page de la liste, le total, l'ordre de toute la vue, les compteurs de toutes les vues et la valeur de la vue."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip().casefold()
	conditions = condition_filters(_parse(conditions), BIN)
	bins = frappe.get_list(
		BIN,
		filters=[["warehouse", "in", depots(include_disabled=True) or [""]], *conditions],
		distinct=has_child_filter(conditions, BIN),
		fields=FIELDS,
		limit_page_length=0,
	)
	codes = {row.item_code for row in bins}
	items = _items(codes)
	seuils = _seuils(codes)
	rows = [row for row in (_row(b, items, seuils) for b in bins) if _active(row)]
	if value:
		rows = [
			row
			for row in rows
			if value in cstr(row["designation"]).casefold()
			or value in cstr(row["article"]).casefold()
			or value in cstr(row["depot"]).casefold()
			or value in cstr(row["groupe"]).casefold()
		]
	counts = {name: sum(1 for row in rows if test(row)) for name, test in VIEWS.items()}
	shown = [row for row in rows if VIEWS[view](row)]
	ordered = order_lignes(shown, sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"lignes": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"valeur": flt(sum(row["valeur"] for row in shown), 2),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


@frappe.whitelist()
def get_etat_stock_options():
	require_bureau()
	return {
		"depots": depots(include_disabled=True),
		"filter_fields": doctype_filter_fields(
			BIN, {"warehouse": [{"value": name, "label": name} for name in depots(include_disabled=True)]}
		),
	}


@frappe.whitelist()
def get_ligne_stock(name, full=0):
	"""Une ligne de stock (article × dépôt) ; la fiche (`full`) ajoute son grand livre et ses lots."""
	require_bureau()
	doc = frappe.get_doc(BIN, name)
	doc.check_permission("read")
	items = _items({doc.item_code})
	payload = _row(frappe._dict(doc.as_dict()), items, _seuils({doc.item_code}))
	payload["modified"] = str(doc.modified)
	payload["company"] = company()
	if cint(full):
		payload["mouvements"] = ledger(item_code=doc.item_code, warehouse=doc.warehouse) if readable("Stock Ledger Entry") else None
		payload["lots"] = (
			lots_disponibles(doc.item_code, doc.warehouse).get(doc.warehouse, []) if payload["avec_lot"] else None
		)
	return payload
