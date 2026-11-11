# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Mouvements de stock du poste de bureau (/bureau/mouvements) : liste, aperçu, fiche, saisie et cycle.

Les Stock Entry d'ERPNext, de trois natures saisies ici : transfert entre deux dépôts (Material Transfer), entrée
dans un dépôt (Material Receipt, lot saisi ou créé) et sortie d'un dépôt (Material Issue : consommation, casse, rebut).
Un brouillon se modifie, se valide ou se supprime ; un mouvement validé s'annule, puis se refait en nouvelle version.

Un mouvement créé par un ordre de production (transfert de matières, reconditionnement…) est montré en lecture
seule : c'est l'ordre qui le crée et qui l'annule. Le serveur refuse toute action sur lui depuis le bureau.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_fullname, getdate, today

from unicare.api import activity
from unicare.api.bureau_devis import LIGNES_MAX, _day
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
from unicare.api.bureau_stock import bins, check_depot, company, depots, lot_disponible, lots_disponibles
from unicare.api.bureau_versions import amend, cancelled_actions, versions

MOUVEMENT = "Stock Entry"
LIGNES = "Stock Entry Detail"
ORDRE = "Ordre de Conditionnement"
ARTICLE_SEARCH_LIMIT = 12

# Nature du bureau → objet du Stock Entry, et les dépôts qu'elle demande.
NATURES = {
	"transfert": {"purpose": "Material Transfer", "source": True, "cible": True},
	"entree": {"purpose": "Material Receipt", "source": False, "cible": True},
	"sortie": {"purpose": "Material Issue", "source": True, "cible": False},
}
PURPOSE_NATURE = {config["purpose"]: nature for nature, config in NATURES.items()}

FIELDS = [
	"name",
	"modified",
	"creation",
	"owner",
	"docstatus",
	"purpose",
	"stock_entry_type",
	"posting_date",
	"from_warehouse",
	"to_warehouse",
	"custom_ordre_conditionnement",
	"total_outgoing_value",
	"total_incoming_value",
	"remarks",
	"amended_from",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "brouillons", "transferts", "entrees", "sorties", "ordres", "annules")
SORT_KEYS = {"name", "date", "nature", "source", "cible", "valeur", "lignes", "creation", "modified"}


def _status(docstatus):
	return {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(cint(docstatus), "Draft")


def nature_of(purpose):
	"""Nature du bureau d'un mouvement, ou `production` pour ce que créent les ordres (reconditionnement…)."""
	return PURPOSE_NATURE.get(purpose, "production")


def from_ordre(doc):
	"""Un mouvement que pilote un ordre de production, ou d'une nature que le bureau ne saisit pas."""
	return bool(doc.get("custom_ordre_conditionnement")) or nature_of(doc.get("purpose")) == "production"


def in_view(view, row):
	if view == "all":
		return True
	if view == "brouillons":
		return row["status"] == "Draft"
	if view == "annules":
		return row["status"] == "Cancelled"
	if view == "ordres":
		return bool(row["ordre"]) or row["nature"] == "production"
	nature = {"transferts": "transfert", "entrees": "entree", "sorties": "sortie"}[view]
	return row["nature"] == nature and row["status"] != "Cancelled"


def _lines_by_mouvement(names):
	if not names:
		return {}
	rows = frappe.get_all(
		LIGNES,
		filters={"parent": ["in", names], "parenttype": MOUVEMENT},
		fields=["parent", "item_name", "item_code", "s_warehouse", "t_warehouse"],
		order_by="idx asc",
	)
	lines = {}
	for row in rows:
		entry = lines.setdefault(row.parent, {"articles": [], "sources": set(), "cibles": set()})
		entry["articles"].append(row.item_name or row.item_code)
		if row.s_warehouse:
			entry["sources"].add(row.s_warehouse)
		if row.t_warehouse:
			entry["cibles"].add(row.t_warehouse)
	return lines


def _list_row(mouvement, lines):
	entry = lines.get(mouvement.name, {"articles": [], "sources": set(), "cibles": set()})
	articles = entry["articles"]
	source = mouvement.from_warehouse or (", ".join(sorted(entry["sources"])) or None)
	cible = mouvement.to_warehouse or (", ".join(sorted(entry["cibles"])) or None)
	return {
		"name": mouvement.name,
		"modified": mouvement.modified,
		"creation": str(mouvement.creation),
		"tags": row_tags(mouvement),
		"cloche": row_bell(mouvement),
		"nature": nature_of(mouvement.purpose),
		"type": mouvement.stock_entry_type or mouvement.purpose,
		"status": _status(mouvement.docstatus),
		"date": _day(mouvement.posting_date),
		"source": source,
		"cible": cible,
		"valeur": flt(mouvement.total_outgoing_value or mouvement.total_incoming_value, 2),
		"ordre": mouvement.custom_ordre_conditionnement or None,
		"remarque": cstr(mouvement.remarks).strip() or None,
		"lignes": len(articles),
		"articles": ", ".join(articles[:3]) + (f" (+{len(articles) - 3})" if len(articles) > 3 else ""),
	}


def order_mouvements(rows, sort=None, direction=None):
	if sort not in SORT_KEYS:
		return sorted(rows, key=lambda row: (cstr(row["date"]), cstr(row["name"])), reverse=True)
	descending = cstr(direction) == "desc"
	ordered = sorted(rows, key=lambda row: cstr(row["name"]), reverse=True)
	filled = [row for row in ordered if row.get(sort) not in (None, "")]
	empty = [row for row in ordered if row.get(sort) in (None, "")]

	def value(row):
		item = row[sort]
		return item if isinstance(item, (int, float)) else cstr(item).casefold()

	return sorted(filled, key=value, reverse=descending) + empty


@frappe.whitelist()
def get_mouvements(view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), MOUVEMENT)
	mouvements = frappe.get_list(
		MOUVEMENT,
		filters=[["company", "=", company()], *conditions],
		distinct=has_child_filter(conditions, MOUVEMENT),
		or_filters=[
			["name", "like", pattern],
			["remarks", "like", pattern],
			["custom_ordre_conditionnement", "like", pattern],
			["from_warehouse", "like", pattern],
			["to_warehouse", "like", pattern],
		]
		if value
		else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	lines = _lines_by_mouvement([row.name for row in mouvements])
	rows = [_list_row(row, lines) for row in mouvements]
	counts = {name: sum(1 for row in rows if in_view(name, row)) for name in VIEWS}
	ordered = order_mouvements([row for row in rows if in_view(view, row)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"mouvements": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


@frappe.whitelist()
def get_mouvement_options():
	require_bureau()
	return {"depots": depots(), "filter_fields": doctype_filter_fields(MOUVEMENT)}


@frappe.whitelist()
def search_stock_articles(search=None, depot=None):
	"""Articles stockés actifs, avec leur unité, le suivi par lots et, si un dépôt est donné, le stock qu'il en a."""
	require_bureau()
	value = cstr(search).strip()
	items = frappe.get_list(
		"Item",
		filters={"disabled": 0, "is_stock_item": 1, "has_variants": 0},
		or_filters=[["item_name", "like", f"%{value}%"], ["name", "like", f"%{value}%"]] if value else None,
		fields=["name", "item_name", "stock_uom", "has_batch_no"],
		order_by="item_name asc",
		limit_page_length=ARTICLE_SEARCH_LIMIT,
	)
	stock = {}
	if depot:
		for row in frappe.get_all(
			"Bin",
			filters={"warehouse": depot, "item_code": ["in", [item.name for item in items] or [""]]},
			fields=["item_code", "actual_qty"],
		):
			stock[row.item_code] = flt(row.actual_qty, 3)
	return [
		{
			"name": item.name,
			"label": item.item_name or item.name,
			"uom": item.stock_uom,
			"avec_lot": cint(item.has_batch_no),
			"stock": stock.get(item.name) if depot else None,
		}
		for item in items
	]


@frappe.whitelist()
def get_lots_article(article, depot):
	"""Lots d'un article à sortir d'un dépôt, la péremption la plus proche d'abord (lots périmés exclus)."""
	require_bureau()
	frappe.get_doc("Item", article).check_permission("read")
	return lots_disponibles(article, depot).get(depot, [])


def _has_batch(item_code):
	return cint(frappe.get_cached_value("Item", item_code, "has_batch_no"))


def _line_lots(item):
	"""Lot(s) d'une ligne : `batch_no` sur le brouillon, ceux de son Serial and Batch Bundle une fois validée."""
	if item.batch_no:
		return [item.batch_no]
	if item.serial_and_batch_bundle:
		return frappe.get_all(
			"Serial and Batch Entry",
			filters={"parent": item.serial_and_batch_bundle, "batch_no": ["is", "set"]},
			pluck="batch_no",
			order_by="idx asc",
		)
	return []


def _line(item):
	return {
		"name": item.name,
		"article": item.item_code,
		"designation": item.item_name or item.item_code,
		"quantite": flt(item.qty),
		"unite": item.uom or item.stock_uom,
		"source": item.s_warehouse or None,
		"cible": item.t_warehouse or None,
		"lots": _line_lots(item),
		"avec_lot": _has_batch(item.item_code),
		"taux": flt(item.basic_rate, 2),
		"valeur": flt(item.amount or item.basic_amount, 2),
	}


def blocked(doc):
	"""Ce qui empêche de valider : aucune ligne, dépôt manquant, lot manquant, quantité au-delà du disponible."""
	if doc.docstatus != 0:
		return []
	reasons = []
	if not doc.items:
		reasons.append(_("Le mouvement n'a aucune ligne."))
	for index, item in enumerate(doc.items, start=1):
		label = _("Ligne {0} ({1})").format(index, item.item_name or item.item_code)
		if NATURES.get(nature_of(doc.purpose), {}).get("source") and not item.s_warehouse:
			reasons.append(_("{0} : choisissez le dépôt de départ.").format(label))
			continue
		if NATURES.get(nature_of(doc.purpose), {}).get("cible") and not item.t_warehouse:
			reasons.append(_("{0} : choisissez le dépôt d'arrivée.").format(label))
			continue
		if _has_batch(item.item_code) and not item.batch_no:
			reasons.append(_("{0} : choisissez le lot.").format(label))
			continue
		if item.s_warehouse:
			if item.batch_no:
				available = flt(lot_disponible(item.item_code, item.s_warehouse, item.batch_no))
			else:
				available = sum(row.actual_qty for row in bins(item_code=item.item_code, warehouse=item.s_warehouse))
			if flt(item.transfer_qty or item.qty) > available:
				reasons.append(
					_("{0} : {1} disponible(s) seulement.").format(label, frappe.format(available, {"fieldtype": "Float"}))
				)
	return reasons


def actions(doc):
	"""Ce que cette personne peut faire sur ce mouvement, maintenant. Rien sur un mouvement d'ordre."""
	if from_ordre(doc):
		return []
	if doc.docstatus == 2:
		return cancelled_actions(doc)
	found = []
	if doc.docstatus == 0:
		if doc.has_permission("write"):
			found.append("modifier")
		if doc.has_permission("submit"):
			found.append("valider")
		if doc.has_permission("delete"):
			found.append("supprimer")
		return found
	if doc.has_permission("cancel"):
		found.append("annuler")
	return found


def _mouvement_payload(doc):
	allowed = actions(doc)
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"status": _status(doc.docstatus),
		"docstatus": cint(doc.docstatus),
		"nature": nature_of(doc.purpose),
		"type": doc.stock_entry_type or doc.purpose,
		"date": _day(doc.posting_date),
		"source": doc.from_warehouse or None,
		"cible": doc.to_warehouse or None,
		"remarque": cstr(doc.remarks).strip() or None,
		"ordre": doc.get("custom_ordre_conditionnement") or None,
		"depuis_ordre": from_ordre(doc),
		"cree_par": get_fullname(doc.owner),
		"lignes": [_line(item) for item in doc.items],
		"valeur_sortie": flt(doc.total_outgoing_value, 2),
		"valeur_entree": flt(doc.total_incoming_value, 2),
		"version_de": doc.get("amended_from") or None,
		"versions": versions(doc),
		"actions": allowed,
		"blocked": blocked(doc) if "valider" in allowed else [],
		"can_print": bool(doc.has_permission("print")),
		"comments": activity.comment_summary(MOUVEMENT, doc.name),
	}


@frappe.whitelist()
def get_mouvement(name):
	require_bureau()
	doc = frappe.get_doc(MOUVEMENT, name)
	doc.check_permission("read")
	return _mouvement_payload(doc)


def _load(name, modified):
	require_bureau()
	doc = frappe.get_doc(MOUVEMENT, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_("Ce mouvement vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."),
			frappe.TimestampMismatchError,
		)
	return doc


def _for_work(name, modified, action):
	doc = _load(name, modified)
	if from_ordre(doc):
		frappe.throw(
			_("Ce mouvement est piloté par l'ordre de production {0} : c'est l'ordre qui le modifie ou l'annule.").format(
				doc.get("custom_ordre_conditionnement") or ""
			),
			frappe.PermissionError,
		)
	if action not in actions(doc):
		frappe.throw(_("Cette action n'est pas possible sur ce mouvement."), frappe.PermissionError)
	return doc


def _clean(values, nature):
	"""Saisie de la fenêtre → (dépôt de départ, dépôt d'arrivée, remarque, lignes)."""
	config = NATURES[nature]
	source = check_depot(values.get("source"), label=_("dépôt de départ")) if config["source"] else None
	cible = check_depot(values.get("cible"), label=_("dépôt d'arrivée")) if config["cible"] else None
	if source and source == cible:
		frappe.throw(_("Les dépôts de départ et d'arrivée doivent être différents."))
	lignes = _parse(values.get("lignes")) or []
	if not isinstance(lignes, list):
		frappe.throw(_("Lignes illisibles."))
	if len(lignes) > LIGNES_MAX:
		frappe.throw(_("Un mouvement compte au plus {0} lignes.").format(LIGNES_MAX))
	cleaned = []
	for ligne in lignes:
		article = cstr((ligne or {}).get("article")).strip()
		if not article:
			continue
		if not frappe.db.exists("Item", {"name": article, "disabled": 0, "is_stock_item": 1}):
			frappe.throw(_("L'article {0} n'est pas un article stocké actif.").format(article))
		quantite = flt(ligne.get("quantite"))
		if quantite <= 0:
			frappe.throw(_("La quantité de {0} doit être positive.").format(article))
		lot = cstr(ligne.get("lot")).strip() or None
		if lot and not _has_batch(article):
			frappe.throw(_("L'article {0} n'est pas suivi par lots.").format(article))
		if lot and nature != "entree":
			lot_item = frappe.db.get_value("Batch", lot, "item")
			if lot_item != article:
				frappe.throw(_("Le lot {0} n'est pas un lot de l'article {1}.").format(lot, article))
		peremption = ligne.get("peremption") or None
		cleaned.append({"article": article, "quantite": quantite, "lot": lot, "peremption": peremption})
	if not cleaned:
		frappe.throw(_("Ajoutez au moins une ligne."))
	return source, cible, cstr(values.get("remarque")).strip(), cleaned


def _entry_rate(article, depot):
	"""Taux d'une entrée : celui du dépôt, sinon celui de l'article, sinon son dernier prix d'achat."""
	rate = flt(frappe.db.get_value("Bin", {"item_code": article, "warehouse": depot}, "valuation_rate"))
	if not rate:
		values = frappe.db.get_value("Item", article, ["valuation_rate", "last_purchase_rate"], as_dict=True) or {}
		rate = flt(values.get("valuation_rate")) or flt(values.get("last_purchase_rate"))
	return rate


def _fill(doc, nature, values):
	from unicare.conditionnement.stock import ensure_batch

	source, cible, remarque, lignes = _clean(values, nature)
	doc.purpose = NATURES[nature]["purpose"]
	doc.stock_entry_type = doc.purpose
	doc.from_warehouse = source
	doc.to_warehouse = cible
	doc.remarks = remarque or None
	doc.set("items", [])
	for ligne in lignes:
		rate = _entry_rate(ligne["article"], cible) if nature == "entree" else 0
		lot = ligne["lot"]
		if lot and nature == "entree":
			# Une entrée peut créer son lot, avec sa péremption, comme une réception.
			lot = ensure_batch(
				item_code=ligne["article"],
				batch_no=lot,
				expiry_date=getdate(ligne["peremption"]) if ligne["peremption"] else None,
				origine="Réception",
			)
		doc.append(
			"items",
			{
				"item_code": ligne["article"],
				"qty": ligne["quantite"],
				"s_warehouse": source,
				"t_warehouse": cible,
				"batch_no": lot,
				"use_serial_batch_fields": 1,
				# Une entrée est valorisée au taux connu de l'article ; sans aucun taux, elle entre à zéro.
				**({"basic_rate": rate, "allow_zero_valuation_rate": 0 if rate else 1} if nature == "entree" else {}),
			},
		)


@frappe.whitelist(methods=["POST"])
def create_mouvement(values=None):
	"""Crée un mouvement en brouillon : nature, dépôts, remarque et lignes (article, quantité, lot)."""
	require_bureau()
	frappe.has_permission(MOUVEMENT, "create", throw=True)
	values = _parse(values) or {}
	nature = cstr(values.get("nature"))
	if nature not in NATURES:
		frappe.throw(_("Choisissez la nature du mouvement."))
	doc = frappe.new_doc(MOUVEMENT)
	doc.company = company()
	doc.posting_date = today()
	_fill(doc, nature, values)
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_mouvement(name, modified, values=None):
	"""Brouillon seulement : dépôts, remarque et lignes. La nature d'un mouvement ne change pas."""
	doc = _for_work(name, modified, "modifier")
	_fill(doc, nature_of(doc.purpose), _parse(values) or {})
	doc.save()
	return _mouvement_payload(doc)


@frappe.whitelist(methods=["POST"])
def validate_mouvement(name, modified):
	"""Soumet le mouvement : le stock bouge."""
	doc = _for_work(name, modified, "valider")
	reasons = blocked(doc)
	if reasons:
		frappe.throw(" ".join(reasons))
	doc.submit()
	return _mouvement_payload(doc)


@frappe.whitelist(methods=["POST"])
def cancel_mouvement(name, modified):
	doc = _for_work(name, modified, "annuler")
	doc.cancel()
	return _mouvement_payload(doc)


@frappe.whitelist(methods=["POST"])
def delete_mouvement(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(MOUVEMENT, doc.name)
	return {"deleted": doc.name}


@frappe.whitelist(methods=["POST"])
def create_version(name, modified):
	"""Nouvelle version (brouillon `NOM-1`) d'un mouvement annulé, comme « Modifier » sur le Desk."""
	doc = _for_work(name, modified, "nouvelle_version")
	return amend(doc)


def mouvement_for_bulk(name, modified):
	return _load(name, modified)


def bulk_guard(doc, operation):
	"""Brouillons seulement en groupe (annulés aussi pour la suppression) ; jamais un mouvement d'ordre."""
	if from_ordre(doc):
		return _("Mouvement piloté par un ordre de production : il ne change pas d'ici.")
	if doc.docstatus != 0 and not (operation == "delete" and doc.docstatus == 2):
		return _("Mouvement validé ou annulé : il ne change plus.")
	return None


def _check_activity(name):
	require_bureau()
	frappe.get_doc(MOUVEMENT, name).check_permission("read")


@frappe.whitelist()
def get_mouvement_activity(name):
	require_bureau()
	return activity.get_feed(MOUVEMENT, name)


@frappe.whitelist(methods=["POST"])
def add_mouvement_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(MOUVEMENT, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_mouvement_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(MOUVEMENT, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_mouvement_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(MOUVEMENT, name, comment)
