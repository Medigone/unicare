# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Inventaires du poste de bureau (/bureau/inventaires) : liste, aperçu, fiche, comptage et cycle.

Le Stock Reconciliation d'ERPNext, à l'objet « Stock Reconciliation ». On crée un inventaire d'un dépôt (et, au choix,
d'un groupe d'articles) : la feuille de comptage reprend chaque article, et chaque lot pour un article suivi par lots,
avec sa quantité théorique (outil standard `get_items`). On saisit les quantités comptées ; l'écart s'affiche.

Le brouillon s'enregistre sans les contrôles d'ERPNext (`flags.ignore_validate`) : ERPNext retirerait sinon toutes les
lignes sans écart, c'est-à-dire la feuille de comptage elle-même. Les contrôles du bureau tiennent lieu ici ; ceux
d'ERPNext s'appliquent à la validation, qui ne garde que les lignes avec écart et ajuste le stock.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_fullname, nowtime, today

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
from unicare.api.bureau_stock import check_depot, company, depots, stock_par_lot
from unicare.api.bureau_versions import amend, cancelled_actions, versions

INVENTAIRE = "Stock Reconciliation"
LIGNES = "Stock Reconciliation Item"
PURPOSE = "Stock Reconciliation"
LIGNES_MAX = 500

FIELDS = [
	"name",
	"modified",
	"creation",
	"owner",
	"docstatus",
	"posting_date",
	"set_warehouse",
	"difference_amount",
	"amended_from",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "brouillons", "valides", "annules")
SORT_KEYS = {"name", "date", "depot", "lignes", "ecart", "creation", "modified"}


def _status(docstatus):
	return {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(cint(docstatus), "Draft")


def in_view(view, row):
	if view == "all":
		return True
	return row["status"] == {"brouillons": "Draft", "valides": "Submitted", "annules": "Cancelled"}[view]


def _lines(names):
	if not names:
		return {}
	rows = frappe.get_all(
		LIGNES,
		filters={"parent": ["in", names], "parenttype": INVENTAIRE},
		fields=["parent", "warehouse"],
	)
	lines = {}
	for row in rows:
		entry = lines.setdefault(row.parent, {"lignes": 0, "depots": set()})
		entry["lignes"] += 1
		if row.warehouse:
			entry["depots"].add(row.warehouse)
	return lines


def _list_row(inventaire, lines):
	entry = lines.get(inventaire.name, {"lignes": 0, "depots": set()})
	return {
		"name": inventaire.name,
		"modified": inventaire.modified,
		"creation": str(inventaire.creation),
		"tags": row_tags(inventaire),
		"cloche": row_bell(inventaire),
		"status": _status(inventaire.docstatus),
		"date": _day(inventaire.posting_date),
		"depot": inventaire.set_warehouse or (", ".join(sorted(entry["depots"])) or None),
		"lignes": entry["lignes"],
		# Écart de valeur : connu une fois validé (ERPNext le calcule à la validation).
		"ecart": flt(inventaire.difference_amount, 2) if cint(inventaire.docstatus) else None,
	}


def order_inventaires(rows, sort=None, direction=None):
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
def get_inventaires(view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), INVENTAIRE)
	inventaires = frappe.get_list(
		INVENTAIRE,
		filters=[["company", "=", company()], ["purpose", "=", PURPOSE], *conditions],
		distinct=has_child_filter(conditions, INVENTAIRE),
		or_filters=[["name", "like", pattern], ["set_warehouse", "like", pattern]] if value else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	lines = _lines([row.name for row in inventaires])
	rows = [_list_row(row, lines) for row in inventaires]
	counts = {name: sum(1 for row in rows if in_view(name, row)) for name in VIEWS}
	ordered = order_inventaires([row for row in rows if in_view(view, row)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"inventaires": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


@frappe.whitelist()
def get_inventaire_options():
	require_bureau()
	groupes = frappe.get_all("Item Group", filters={"is_group": 0}, order_by="name asc", pluck="name")
	return {"depots": depots(), "groupes": groupes, "filter_fields": doctype_filter_fields(INVENTAIRE)}


def _theorique(doc):
	"""Quantité en stock maintenant de chaque ligne : par lot (périmés compris) ou par article dans le dépôt."""
	lots = stock_par_lot([row.batch_no for row in doc.items if row.batch_no])
	bins = {}
	codes = [row.item_code for row in doc.items if not row.batch_no]
	if codes:
		for row in frappe.get_all(
			"Bin",
			filters={"item_code": ["in", codes], "warehouse": ["in", [row.warehouse for row in doc.items] or [""]]},
			fields=["item_code", "warehouse", "actual_qty"],
		):
			bins[(row.item_code, row.warehouse)] = flt(row.actual_qty, 3)
	result = {}
	for row in doc.items:
		if row.batch_no:
			result[row.name] = flt(lots.get(row.batch_no, {}).get(row.warehouse, 0), 3)
		else:
			result[row.name] = bins.get((row.item_code, row.warehouse), 0)
	return result


def _line(item, theorique):
	"""Une ligne de comptage. Brouillon : le théorique est celui d'aujourd'hui ; validé : celui qu'ERPNext a figé."""
	current = flt(item.current_qty, 3) if theorique is None else theorique
	compte = flt(item.qty, 3)
	taux = flt(item.valuation_rate or item.current_valuation_rate, 2)
	return {
		"name": item.name,
		"article": item.item_code,
		"designation": item.item_name or item.item_code,
		"groupe": item.item_group,
		"depot": item.warehouse,
		"lot": item.batch_no or None,
		"unite": item.stock_uom,
		"theorique": current,
		"compte": compte,
		"ecart": flt(compte - current, 3),
		"taux": taux,
		"ecart_valeur": flt((compte - current) * taux, 2),
	}


def blocked(doc, lignes):
	if doc.docstatus != 0:
		return []
	if not doc.items:
		return [_("L'inventaire n'a aucune ligne.")]
	if not any(line["ecart"] for line in lignes):
		return [_("Aucun écart entre le comptage et le stock : il n'y a rien à ajuster.")]
	return []


def actions(doc):
	if doc.docstatus == 2:
		return cancelled_actions(doc)
	found = []
	if doc.docstatus == 0:
		if doc.has_permission("write"):
			found.append("compter")
		if doc.has_permission("submit"):
			found.append("valider")
		if doc.has_permission("delete"):
			found.append("supprimer")
		return found
	if doc.has_permission("cancel"):
		found.append("annuler")
	return found


def _inventaire_payload(doc):
	allowed = actions(doc)
	theorique = _theorique(doc) if doc.docstatus == 0 else {}
	lignes = [_line(item, theorique.get(item.name) if doc.docstatus == 0 else None) for item in doc.items]
	ecarts = [line for line in lignes if line["ecart"]]
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"status": _status(doc.docstatus),
		"docstatus": cint(doc.docstatus),
		"date": _day(doc.posting_date),
		"depot": doc.set_warehouse or None,
		"cree_par": get_fullname(doc.owner),
		"lignes": lignes,
		"resume": {
			"lignes": len(lignes),
			"ecarts": len(ecarts),
			"plus": flt(sum(line["ecart"] for line in ecarts if line["ecart"] > 0), 3),
			"moins": flt(sum(line["ecart"] for line in ecarts if line["ecart"] < 0), 3),
			"valeur": flt(doc.difference_amount, 2) if doc.docstatus else flt(sum(line["ecart_valeur"] for line in ecarts), 2),
		},
		"version_de": doc.get("amended_from") or None,
		"versions": versions(doc),
		"actions": allowed,
		"blocked": blocked(doc, lignes) if "valider" in allowed else [],
		"can_print": bool(doc.has_permission("print")),
		"comments": activity.comment_summary(INVENTAIRE, doc.name),
	}


@frappe.whitelist()
def get_inventaire(name):
	require_bureau()
	doc = frappe.get_doc(INVENTAIRE, name)
	doc.check_permission("read")
	return _inventaire_payload(doc)


def _load(name, modified):
	require_bureau()
	doc = frappe.get_doc(INVENTAIRE, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_("Cet inventaire vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."),
			frappe.TimestampMismatchError,
		)
	return doc


def _for_work(name, modified, action):
	doc = _load(name, modified)
	if action not in actions(doc):
		frappe.throw(_("Cette action n'est pas possible sur cet inventaire."), frappe.PermissionError)
	return doc


def _save_draft(doc):
	"""Enregistre la feuille de comptage telle quelle : ERPNext n'en retire pas les lignes sans écart."""
	doc.flags.ignore_validate = True
	if doc.is_new():
		doc.insert()
	else:
		doc.save()


@frappe.whitelist(methods=["POST"])
def create_inventaire(values=None):
	"""Crée la feuille de comptage d'un dépôt (et, au choix, d'un groupe d'articles), au stock théorique d'aujourd'hui."""
	from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import get_items

	require_bureau()
	frappe.has_permission(INVENTAIRE, "create", throw=True)
	values = _parse(values) or {}
	depot = check_depot(values.get("depot"))
	groupe = cstr(values.get("groupe")).strip()
	if groupe and not frappe.db.exists("Item Group", groupe):
		frappe.throw(_("Choisissez un groupe d'articles de la liste."))
	rows = get_items(depot, today(), nowtime(), company())
	if groupe:
		groupes = {row.name: row.item_group for row in frappe.get_all("Item", filters={"name": ["in", [r.get("item_code") for r in rows] or [""]]}, fields=["name", "item_group"])}
		rows = [row for row in rows if groupes.get(row.get("item_code")) == groupe]
	# Un article sans stock ni lot reste dans la feuille : on peut en trouver au comptage.
	if not rows:
		frappe.throw(_("Aucun article à compter dans ce dépôt."))
	if len(rows) > LIGNES_MAX:
		frappe.throw(_("Plus de {0} lignes : choisissez un groupe d'articles.").format(LIGNES_MAX))
	doc = frappe.new_doc(INVENTAIRE)
	doc.update({"company": company(), "purpose": PURPOSE, "posting_date": today(), "set_warehouse": depot})
	for row in rows:
		doc.append(
			"items",
			{
				"item_code": row.get("item_code"),
				"item_name": row.get("item_name"),
				"warehouse": depot,
				"batch_no": row.get("batch_no") or None,
				"use_serial_batch_fields": 1 if row.get("batch_no") else 0,
				"qty": flt(row.get("qty")),
				"current_qty": flt(row.get("current_qty")),
				"valuation_rate": flt(row.get("valuation_rate")),
				"current_valuation_rate": flt(row.get("current_valuation_rate")),
			},
		)
	_save_draft(doc)
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def compter(name, modified, lignes=None, ajouts=None, retirer=None):
	"""Brouillon : quantités comptées, lignes ajoutées (article, lot, quantité), lignes retirées."""
	from unicare.conditionnement.stock import ensure_batch

	doc = _for_work(name, modified, "compter")
	rows = {row.name: row for row in doc.items}
	for ligne in _parse(lignes) or []:
		row = rows.get(cstr((ligne or {}).get("name")))
		if not row:
			frappe.throw(_("Cette ligne n'est plus dans l'inventaire : rechargez-le."))
		quantite = flt(ligne.get("quantite"))
		if quantite < 0:
			frappe.throw(_("Une quantité comptée ne peut pas être négative."))
		row.qty = quantite
	removed = {cstr(name) for name in (_parse(retirer) or [])}
	if removed:
		doc.set("items", [row for row in doc.items if row.name not in removed])
	depot = doc.set_warehouse or (doc.items[0].warehouse if doc.items else None)
	for ajout in _parse(ajouts) or []:
		article = cstr((ajout or {}).get("article")).strip()
		if not frappe.db.exists("Item", {"name": article, "disabled": 0, "is_stock_item": 1}):
			frappe.throw(_("L'article {0} n'est pas un article stocké actif.").format(article))
		lot = cstr(ajout.get("lot")).strip() or None
		with_batch = cint(frappe.get_cached_value("Item", article, "has_batch_no"))
		if with_batch and not lot:
			frappe.throw(_("L'article {0} est suivi par lots : saisissez le lot compté.").format(article))
		if lot:
			if not with_batch:
				frappe.throw(_("L'article {0} n'est pas suivi par lots.").format(article))
			existing = frappe.db.get_value("Batch", lot, "item")
			if existing and existing != article:
				frappe.throw(_("Le lot {0} appartient à l'article {1}.").format(lot, existing))
			lot = ensure_batch(item_code=article, batch_no=lot, origine="Réception")
		if any(row.item_code == article and (row.batch_no or None) == lot for row in doc.items):
			frappe.throw(_("{0} est déjà dans la feuille de comptage.").format(lot or article))
		quantite = flt(ajout.get("quantite"))
		if quantite < 0:
			frappe.throw(_("Une quantité comptée ne peut pas être négative."))
		rate = flt(frappe.db.get_value("Bin", {"item_code": article, "warehouse": depot}, "valuation_rate")) or flt(
			frappe.get_cached_value("Item", article, "valuation_rate")
		)
		doc.append(
			"items",
			{
				"item_code": article,
				"warehouse": depot,
				"batch_no": lot,
				"use_serial_batch_fields": 1 if lot else 0,
				"qty": quantite,
				"valuation_rate": rate,
				"allow_zero_valuation_rate": 0 if rate else 1,
			},
		)
	if not doc.items:
		frappe.throw(_("L'inventaire doit garder au moins une ligne : supprimez le brouillon plutôt."))
	if len(doc.items) > LIGNES_MAX:
		frappe.throw(_("Un inventaire compte au plus {0} lignes.").format(LIGNES_MAX))
	_save_draft(doc)
	return _inventaire_payload(doc)


@frappe.whitelist(methods=["POST"])
def validate_inventaire(name, modified):
	"""Soumet l'inventaire : ERPNext ne garde que les lignes avec écart et ajuste le stock à la date et l'heure d'aujourd'hui."""
	doc = _for_work(name, modified, "valider")
	reasons = blocked(doc, _inventaire_payload(doc)["lignes"])
	if reasons:
		frappe.throw(" ".join(reasons))
	doc.posting_date = today()
	doc.posting_time = nowtime()
	doc.submit()
	return _inventaire_payload(frappe.get_doc(INVENTAIRE, doc.name))


@frappe.whitelist(methods=["POST"])
def cancel_inventaire(name, modified):
	doc = _for_work(name, modified, "annuler")
	doc.cancel()
	return _inventaire_payload(doc)


@frappe.whitelist(methods=["POST"])
def delete_inventaire(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(INVENTAIRE, doc.name)
	return {"deleted": doc.name}


@frappe.whitelist(methods=["POST"])
def create_version(name, modified):
	"""Nouvelle version (brouillon `NOM-1`) d'un inventaire annulé, avec sa feuille de comptage."""
	doc = _for_work(name, modified, "nouvelle_version")
	return amend(doc, ignore_validate=True)


def inventaire_for_bulk(name, modified):
	return _load(name, modified)


def bulk_guard(doc, operation):
	"""Une feuille de comptage se modifie sur sa fiche ; en groupe, seulement la suppression des brouillons ou annulés."""
	if operation != "delete":
		return _("Un inventaire se modifie sur sa fiche.")
	if doc.docstatus == 1:
		return _("Inventaire validé : annulez-le d'abord.")
	return None


def _check_activity(name):
	require_bureau()
	frappe.get_doc(INVENTAIRE, name).check_permission("read")


@frappe.whitelist()
def get_inventaire_activity(name):
	require_bureau()
	return activity.get_feed(INVENTAIRE, name)


@frappe.whitelist(methods=["POST"])
def add_inventaire_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(INVENTAIRE, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_inventaire_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(INVENTAIRE, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_inventaire_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(INVENTAIRE, name, comment)
