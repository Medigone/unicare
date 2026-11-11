# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Lots du poste de bureau (/bureau/lots) : liste, aperçu, fiche, modification et suppression.

Les Batch d'ERPNext : quantité en stock (périmés compris), péremption, lot du fournisseur, origine (réception ou ordre
de conditionnement). La fiche montre le stock du lot par dépôt, ses mouvements et sa traçabilité dans les ordres de
conditionnement (rapport `tracabilite_lot`). Péremption, date de fabrication, lot fournisseur et désactivation se
modifient ici ; un lot se supprime s'il n'a jamais bougé (Frappe en reste juge).
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, cstr, flt, getdate, today

from unicare.api import activity
from unicare.api.bureau_devis import _day
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
from unicare.api.bureau_stock import BATCH, ledger, readable, stock_par_lot

EXPIRE_SOUS = 30
FIELDS = [
	"name",
	"modified",
	"creation",
	"item",
	"item_name",
	"batch_qty",
	"stock_uom",
	"expiry_date",
	"manufacturing_date",
	"custom_date_fabrication",
	"custom_lot_fournisseur",
	"custom_origine",
	"custom_ordre_conditionnement",
	"supplier",
	"disabled",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "avec_stock", "expirent", "perimes", "vides", "desactives")
SORT_KEYS = {"name", "designation", "quantite", "peremption", "fabrication", "origine", "lot_fournisseur", "creation", "modified"}


def in_view(view, row, current_day=None):
	if view == "all":
		return True
	if view == "desactives":
		return bool(row["desactive"])
	qty = flt(row["quantite"])
	if view == "avec_stock":
		return qty > 0
	if view == "vides":
		return qty <= 0
	peremption = row.get("peremption")
	if not peremption or qty <= 0:
		return False
	day = getdate(current_day or today())
	if view == "perimes":
		return getdate(peremption) < day
	return day <= getdate(peremption) <= add_days(day, EXPIRE_SOUS)


def _list_row(lot):
	return {
		"name": lot.name,
		"modified": lot.modified,
		"creation": str(lot.creation),
		"tags": row_tags(lot),
		"cloche": row_bell(lot),
		"article": lot.item,
		"designation": lot.item_name or lot.item,
		"quantite": flt(lot.batch_qty, 3),
		"unite": lot.stock_uom,
		"peremption": _day(lot.expiry_date),
		"fabrication": _day(lot.custom_date_fabrication or lot.manufacturing_date),
		"lot_fournisseur": lot.custom_lot_fournisseur or None,
		"origine": lot.custom_origine or None,
		"ordre": lot.custom_ordre_conditionnement or None,
		"fournisseur": lot.supplier or None,
		"desactive": cint(lot.disabled),
	}


def order_lots(rows, sort=None, direction=None):
	"""Les plus récents d'abord, ou par la colonne demandée. Une ligne sans valeur reste à la fin."""
	if sort not in SORT_KEYS:
		return sorted(rows, key=lambda row: (cstr(row["creation"]), cstr(row["name"])), reverse=True)
	descending = cstr(direction) == "desc"
	ordered = sorted(rows, key=lambda row: cstr(row["name"]))
	filled = [row for row in ordered if row.get(sort) not in (None, "")]
	empty = [row for row in ordered if row.get(sort) in (None, "")]

	def value(row):
		item = row[sort]
		return item if isinstance(item, (int, float)) else cstr(item).casefold()

	return sorted(filled, key=value, reverse=descending) + empty


@frappe.whitelist()
def get_lots(view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), BATCH)
	lots = frappe.get_list(
		BATCH,
		filters=conditions,
		distinct=has_child_filter(conditions, BATCH),
		or_filters=[
			["name", "like", pattern],
			["item", "like", pattern],
			["item_name", "like", pattern],
			["custom_lot_fournisseur", "like", pattern],
		]
		if value
		else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	rows = [_list_row(row) for row in lots]
	current_day = today()
	counts = {name: sum(1 for row in rows if in_view(name, row, current_day)) for name in VIEWS}
	ordered = order_lots([row for row in rows if in_view(view, row, current_day)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"lots": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


@frappe.whitelist()
def get_lot_options():
	require_bureau()
	return {"expire_sous": EXPIRE_SOUS, "filter_fields": doctype_filter_fields(BATCH)}


def _tracabilite(name):
	"""Les ordres de production où le lot entre (matière) ou dont il sort (produit fini)."""
	if not readable("Ordre de Conditionnement"):
		return None
	from unicare.conditionnement.report.tracabilite_lot.tracabilite_lot import get_data

	return [
		{
			"sens": row.get("sens"),
			"ordre": row.get("ordre"),
			"statut": row.get("statut"),
			"produit": row.get("nom_produit") or row.get("produit_fini"),
			"lot_pf": row.get("lot_pf"),
			"lot_mp": row.get("lot_mp"),
			"article": row.get("item_code"),
			"quantite": flt(row.get("qty_reelle"), 3),
			"quantite_pf": flt(row.get("qty_reelle_pf"), 3),
			"date": _day(row.get("date_prevue")),
		}
		for row in get_data(name) or []
	]


def _lot_payload(doc, full=False):
	payload = {
		**_list_row(frappe._dict(doc.as_dict())),
		"modified": str(doc.modified),
		"tags": row_tags(doc.as_dict()),
		"description": doc.description or None,
		"can_edit": bool(doc.has_permission("write")),
		"can_delete": bool(doc.has_permission("delete")),
	}
	depots = stock_par_lot([doc.name]).get(doc.name, {})
	payload["depots"] = [{"depot": depot, "qty": qty} for depot, qty in sorted(depots.items(), key=lambda item: -item[1])]
	if full:
		payload.update(
			{
				"mouvements": ledger(lot=doc.name) if readable("Stock Ledger Entry") else None,
				"tracabilite": _tracabilite(doc.name),
				"comments": activity.comment_summary(BATCH, doc.name),
			}
		)
	return payload


@frappe.whitelist()
def get_lot(name, full=0):
	require_bureau()
	doc = frappe.get_doc(BATCH, name)
	doc.check_permission("read")
	return _lot_payload(doc, full=cint(full))


def _lot_for_write(name, modified):
	require_bureau()
	doc = frappe.get_doc(BATCH, name)
	doc.check_permission("write")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_("Ce lot vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."),
			frappe.TimestampMismatchError,
		)
	return doc


EDITABLE = {"peremption": "expiry_date", "fabrication": "custom_date_fabrication", "lot_fournisseur": "custom_lot_fournisseur", "desactive": "disabled"}


@frappe.whitelist(methods=["POST"])
def update_lot(name, modified, values=None):
	"""Péremption, date de fabrication, lot du fournisseur et désactivation. Les champs absents ne changent pas."""
	doc = _lot_for_write(name, modified)
	values = {key: value for key, value in (_parse(values) or {}).items() if key in EDITABLE}
	if "peremption" in values or "fabrication" in values:
		peremption = values.get("peremption", doc.expiry_date)
		fabrication = values.get("fabrication", doc.custom_date_fabrication)
		if peremption and fabrication and getdate(peremption) < getdate(fabrication):
			frappe.throw(_("La péremption ne peut pas précéder la fabrication."))
	for key, value in values.items():
		if key == "desactive":
			doc.disabled = cint(value)
		elif key in ("peremption", "fabrication"):
			doc.set(EDITABLE[key], getdate(value) if value else None)
		else:
			doc.set(EDITABLE[key], cstr(value).strip() or None)
	doc.save()
	return _lot_payload(doc, full=True)


@frappe.whitelist(methods=["POST"])
def delete_lot(name, modified):
	"""Supprime un lot qui n'a jamais bougé : Frappe refuse s'il est cité par une pièce."""
	doc = _lot_for_write(name, modified)
	doc.check_permission("delete")
	frappe.delete_doc(BATCH, doc.name)
	return {"deleted": doc.name}


def lot_for_bulk(name, modified):
	return _lot_for_write(name, modified)


@frappe.whitelist()
def get_lot_activity(name):
	require_bureau()
	return activity.get_feed(BATCH, name)


@frappe.whitelist(methods=["POST"])
def add_lot_comment(name, text, mentions=None):
	require_bureau()
	return activity.add_comment(BATCH, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_lot_comment(name, comment, text, mentions=None):
	require_bureau()
	return activity.update_comment(BATCH, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_lot_comment(name, comment):
	require_bureau()
	return activity.delete_comment(BATCH, name, comment)
