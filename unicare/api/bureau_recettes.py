# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Recettes de conditionnement du poste de bureau (/bureau/recettes) : liste, aperçu, fiche et fenêtre de saisie.

Une recette dit ce qu'il faut pour une quantité de base d'un produit fini : des matières de type Fût (au moins une)
et de conditionnement, et le rendement visé. Les ordres la reprennent à leur création ; la modifier ne change pas les
ordres déjà créés. Une recette utilisée par un ordre ne se supprime pas : on la rend inactive.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_fullname

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

RECETTE = "Recette de Conditionnement"
INGREDIENT = "Ingredient Recette"
ORDRE = "Ordre de Conditionnement"
TYPES_MATIERE = ("Fût", "Conditionnement")

FIELDS = [
	"name",
	"modified",
	"creation",
	"produit_fini",
	"nom_produit",
	"actif",
	"quantite_base",
	"uom",
	"rendement_theorique",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "actives", "inactives")
SORT_KEYS = {"name", "designation", "matieres", "ordres", "rendement", "creation", "modified"}


def in_view(view, row):
	return view == "all" or (view == "actives") == bool(row["actif"])


def _counts(names):
	if not names:
		return {}, {}
	matieres = {}
	for row in frappe.get_all(INGREDIENT, filters={"parent": ["in", names], "parenttype": RECETTE}, fields=["parent"]):
		matieres[row.parent] = matieres.get(row.parent, 0) + 1
	ordres = {}
	for row in frappe.get_all(ORDRE, filters={"recette": ["in", names]}, fields=["recette"]):
		ordres[row.recette] = ordres.get(row.recette, 0) + 1
	return matieres, ordres


def _list_row(recette, matieres, ordres):
	return {
		"name": recette.name,
		"modified": recette.modified,
		"creation": str(recette.creation),
		"tags": row_tags(recette),
		"cloche": row_bell(recette),
		"produit": recette.produit_fini,
		"designation": recette.nom_produit or recette.produit_fini,
		"actif": bool(cint(recette.actif)),
		"quantite_base": flt(recette.quantite_base, 3),
		"unite": recette.uom,
		"rendement": flt(recette.rendement_theorique, 1),
		"matieres": matieres.get(recette.name, 0),
		"ordres": ordres.get(recette.name, 0),
	}


def order_recettes(rows, sort=None, direction=None):
	if sort not in SORT_KEYS:
		return sorted(rows, key=lambda row: (not row["actif"], cstr(row["designation"]).casefold(), cstr(row["name"])))
	descending = cstr(direction) == "desc"
	ordered = sorted(rows, key=lambda row: cstr(row["name"]))

	def value(row):
		item = row[sort]
		return item if isinstance(item, (int, float)) else cstr(item).casefold()

	return sorted(ordered, key=value, reverse=descending)


@frappe.whitelist()
def get_recettes(view="actives", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None):
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), RECETTE)
	recettes = frappe.get_list(
		RECETTE,
		filters=conditions,
		distinct=has_child_filter(conditions, RECETTE),
		or_filters=[["name", "like", pattern], ["nom_produit", "like", pattern], ["produit_fini", "like", pattern]] if value else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	matieres, ordres = _counts([row.name for row in recettes])
	rows = [_list_row(row, matieres, ordres) for row in recettes]
	counts = {name: sum(1 for row in rows if in_view(name, row)) for name in VIEWS}
	ordered = order_recettes([row for row in rows if in_view(view, row)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"recettes": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


def _items(types):
	return [
		{"value": row.name, "label": row.item_name or row.name, "type": row.custom_type_conditionnement, "unite": row.stock_uom}
		for row in frappe.get_all(
			"Item",
			filters={"disabled": 0, "custom_type_conditionnement": ["in", list(types)]},
			fields=["name", "item_name", "custom_type_conditionnement", "stock_uom"],
			order_by="item_name asc",
			limit_page_length=1000,
		)
	]


@frappe.whitelist()
def get_recette_options():
	"""Produits finis et matières (fûts, conditionnement) proposés dans la fenêtre : des noms seulement."""
	require_bureau()
	return {
		"produits": _items(("Produit fini",)),
		"matieres": _items(TYPES_MATIERE),
		"unites": frappe.get_all("UOM", filters={"enabled": 1}, order_by="name asc", pluck="name"),
		"filter_fields": doctype_filter_fields(RECETTE),
	}


def actions(doc, ordres):
	found = []
	if doc.has_permission("write"):
		found += ["modifier", "desactiver" if cint(doc.actif) else "activer"]
	if frappe.has_permission(RECETTE, "create"):
		found.append("dupliquer")
	if frappe.has_permission(ORDRE, "create") and cint(doc.actif):
		found.append("nouvel_ordre")
	if doc.has_permission("delete") and not ordres:
		found.append("supprimer")
	return found


def _recette_payload(doc):
	ordres = frappe.get_list(
		ORDRE,
		filters={"recette": doc.name},
		fields=["name", "workflow_state", "date_prevue", "qty_prevue", "qty_reelle_pf", "rendement_reel"],
		order_by="creation desc",
		limit_page_length=0,
	)
	termines = [row for row in ordres if row.workflow_state == "Terminé"]
	from unicare.api.bureau_ordres import ETAPES

	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"produit": doc.produit_fini,
		"designation": doc.nom_produit or doc.produit_fini,
		"actif": bool(cint(doc.actif)),
		"quantite_base": flt(doc.quantite_base, 3),
		"unite": doc.uom,
		"rendement": flt(doc.rendement_theorique, 1),
		"rendement_moyen": flt(sum(flt(row.rendement_reel) for row in termines) / len(termines), 1) if termines else None,
		"ordres_termines": len(termines),
		"ingredients": [
			{
				"name": row.name,
				"article": row.item_code,
				"designation": row.item_name or row.item_code,
				"type": row.type_ingredient,
				"quantite": flt(row.qty, 6),
				"unite": row.uom,
				"obligatoire": bool(cint(row.obligatoire)),
			}
			for row in doc.ingredients
		],
		"ordres": [
			{
				"name": row.name,
				"state": row.workflow_state or "Brouillon",
				"etape": ETAPES.get(row.workflow_state or "Brouillon", row.workflow_state),
				"date_prevue": _day(row.date_prevue),
				"qty_prevue": flt(row.qty_prevue, 3),
				"qty_reelle": flt(row.qty_reelle_pf, 3) if row.workflow_state == "Terminé" else None,
				"rendement": flt(row.rendement_reel, 1) if row.workflow_state == "Terminé" else None,
			}
			for row in ordres[:5]
		],
		"nb_ordres": len(ordres),
		"actions": actions(doc, ordres),
		"cree_par": get_fullname(doc.owner),
		"comments": activity.comment_summary(RECETTE, doc.name),
	}


@frappe.whitelist()
def get_recette(name):
	require_bureau()
	doc = frappe.get_doc(RECETTE, name)
	doc.check_permission("read")
	return _recette_payload(doc)


def _load(name, modified):
	require_bureau()
	doc = frappe.get_doc(RECETTE, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_("Cette recette vient d'être modifiée par ailleurs. Elle a été rechargée : vérifiez-la, puis recommencez."),
			frappe.TimestampMismatchError,
		)
	return doc


def _for_work(name, modified, action):
	doc = _load(name, modified)
	if action not in actions(doc, frappe.get_all(ORDRE, filters={"recette": doc.name}, pluck="name", limit=1)):
		frappe.throw(_("Cette action n'est pas possible sur cette recette."), frappe.PermissionError)
	return doc


def _apply(doc, values):
	"""Produit, quantité de base, unité, rendement et matières. Le type d'une matière vient de sa fiche article."""
	produit = cstr(values.get("produit")).strip()
	item = frappe.db.get_value("Item", {"name": produit, "disabled": 0}, ["custom_type_conditionnement", "stock_uom"], as_dict=True) if produit else None
	if not item or item.custom_type_conditionnement != "Produit fini":
		frappe.throw(_("Choisissez un produit fini de la liste."))
	doc.produit_fini = produit
	doc.quantite_base = flt(values.get("quantite_base"))
	doc.uom = cstr(values.get("unite")).strip() or item.stock_uom
	doc.rendement_theorique = flt(values.get("rendement")) if values.get("rendement") not in (None, "") else 100
	if doc.rendement_theorique <= 0 or doc.rendement_theorique > 100:
		frappe.throw(_("Le rendement visé est un pourcentage entre 1 et 100."))
	doc.set("ingredients", [])
	vus = set()
	for ligne in values.get("ingredients") or []:
		article = cstr((ligne or {}).get("article")).strip()
		matiere = frappe.db.get_value("Item", {"name": article, "disabled": 0}, ["item_name", "custom_type_conditionnement", "stock_uom"], as_dict=True) if article else None
		if not matiere or matiere.custom_type_conditionnement not in TYPES_MATIERE:
			frappe.throw(_("{0} n'est ni un fût ni un article de conditionnement.").format(article or _("Une ligne")))
		if article in vus:
			frappe.throw(_("{0} figure deux fois : regroupez les quantités sur une ligne.").format(matiere.item_name))
		vus.add(article)
		doc.append(
			"ingredients",
			{
				"item_code": article,
				"item_name": matiere.item_name,
				"type_ingredient": matiere.custom_type_conditionnement,
				"qty": flt(ligne.get("quantite")),
				"uom": cstr(ligne.get("unite")).strip() or matiere.stock_uom,
				"obligatoire": 0 if ligne.get("obligatoire") is False or cstr(ligne.get("obligatoire")) == "0" else 1,
			},
		)


@frappe.whitelist(methods=["POST"])
def create_recette(values=None):
	require_bureau()
	frappe.has_permission(RECETTE, "create", throw=True)
	doc = frappe.new_doc(RECETTE)
	doc.actif = 1
	_apply(doc, _parse(values) or {})
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_recette(name, modified, values=None):
	doc = _for_work(name, modified, "modifier")
	_apply(doc, _parse(values) or {})
	doc.save()
	return _recette_payload(doc)


@frappe.whitelist(methods=["POST"])
def set_actif(name, modified, actif):
	doc = _for_work(name, modified, "desactiver" if not cint(actif) else "activer")
	doc.actif = 1 if cint(actif) else 0
	doc.save()
	return _recette_payload(doc)


@frappe.whitelist(methods=["POST"])
def dupliquer(name):
	"""Copie de la recette (active), à modifier : la façon de préparer une variante ou une nouvelle version."""
	doc = _for_work(name, None, "dupliquer")
	copie = frappe.copy_doc(doc)
	copie.actif = 1
	copie.insert()
	return {"name": copie.name}


@frappe.whitelist(methods=["POST"])
def delete_recette(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(RECETTE, doc.name)
	return {"deleted": doc.name}


def recette_for_bulk(name, modified):
	return _load(name, modified)


def bulk_guard(doc, operation):
	if operation == "delete" and frappe.db.exists(ORDRE, {"recette": doc.name}):
		return _("Recette utilisée par des ordres : rendez-la inactive plutôt.")
	if operation not in ("delete", "update"):
		return _("Une recette se modifie sur sa fiche.")
	return None


def _check_activity(name):
	require_bureau()
	frappe.get_doc(RECETTE, name).check_permission("read")


@frappe.whitelist()
def get_recette_activity(name):
	require_bureau()
	return activity.get_feed(RECETTE, name)


@frappe.whitelist(methods=["POST"])
def add_recette_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(RECETTE, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_recette_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(RECETTE, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_recette_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(RECETTE, name, comment)
