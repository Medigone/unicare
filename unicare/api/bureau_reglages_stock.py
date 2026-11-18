# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Réglages, page Stock (/bureau/reglages-stock) : paramètres de stock et seuils de réapprovisionnement.

Paramètres : ceux des « Stock Settings » qui changent quelque chose dans le bureau (dépôt de réception par défaut,
unité des nouveaux articles, stock négatif, demandes d'achat automatiques). Seuils : la ligne « Item Reorder » de
l'article pour un dépôt (type Purchase), lue par l'état du stock (vue « Sous le seuil ») et le tableau de bord.
Droits : ceux d'ERPNext (Stock Settings, Item).
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

from unicare.api.bureau_devis import filter_words
from unicare.api.bureau_list import _parse
from unicare.api.bureau_postes import require_bureau
from unicare.api.bureau_stock import check_depot, depots

PARAMETRES = "Stock Settings"
ARTICLE = "Item"
SEUIL = "Item Reorder"
TYPE = "Purchase"
VUES = ("tous", "avec_seuil", "sous_seuil")
PAGE = 50


def _stale(modified, current, message=None):
	if cstr(modified) != str(current):
		frappe.throw(
			message
			or _("Ces réglages viennent d'être modifiés par ailleurs. Ils ont été rechargés : vérifiez-les, puis recommencez."),
			frappe.TimestampMismatchError,
		)


@frappe.whitelist()
def get_reglages_stock():
	require_bureau()
	frappe.has_permission(ARTICLE, "read", throw=True)
	settings = frappe.get_single(PARAMETRES)
	return {
		"parametres": {
			"modified": str(settings.modified),
			"default_warehouse": settings.default_warehouse,
			"stock_uom": settings.stock_uom,
			"allow_negative_stock": bool(cint(settings.allow_negative_stock)),
			"auto_indent": bool(cint(settings.auto_indent)),
			"valuation_method": settings.valuation_method,
		},
		"depots": depots(),
		"unites": frappe.get_all("UOM", filters={"enabled": 1}, order_by="name asc", pluck="name"),
		"droits": {
			"parametres": bool(frappe.has_permission(PARAMETRES, "write")),
			"seuils": bool(frappe.has_permission(ARTICLE, "write")),
		},
	}


@frappe.whitelist(methods=["POST"])
def save_parametres(modified, values=None):
	require_bureau()
	doc = frappe.get_single(PARAMETRES)
	doc.check_permission("write")
	_stale(modified, doc.modified)
	values = _parse(values) or {}
	depot = cstr(values.get("default_warehouse")).strip()
	doc.default_warehouse = check_depot(depot, label=_("Dépôt par défaut")) if depot else None
	unite = cstr(values.get("stock_uom")).strip()
	if unite and not frappe.db.exists("UOM", {"name": unite, "enabled": 1}):
		frappe.throw(_("Unité inconnue ou retirée des listes : {0}.").format(unite))
	doc.stock_uom = unite or None
	doc.allow_negative_stock = 1 if values.get("allow_negative_stock") else 0
	doc.auto_indent = 1 if values.get("auto_indent") else 0
	doc.save()
	return get_reglages_stock()


# --- Seuils de réapprovisionnement ----------------------------------------------------------------------


def _seuils(depot, codes):
	if not codes:
		return {}
	rows = frappe.get_all(
		SEUIL,
		filters={"parenttype": ARTICLE, "parent": ["in", list(codes)], "warehouse": depot, "material_request_type": TYPE},
		fields=["parent", "warehouse_reorder_level", "warehouse_reorder_qty"],
	)
	return {row.parent: row for row in rows}


def _stocks(depot, codes):
	if not codes:
		return {}
	rows = frappe.get_all(
		"Bin", filters={"warehouse": depot, "item_code": ["in", list(codes)]}, fields=["item_code", "actual_qty"]
	)
	return {row.item_code: flt(row.actual_qty, 3) for row in rows}


def _ligne(item, seuil, stock):
	niveau = flt(seuil.warehouse_reorder_level, 3) if seuil else 0
	return {
		"article": item.name,
		"designation": item.item_name or item.name,
		"unite": item.stock_uom,
		"stock": stock,
		"seuil": niveau or None,
		"quantite": flt(seuil.warehouse_reorder_qty, 3) or None if seuil and niveau else None,
		"modified": str(item.modified),
	}


@frappe.whitelist()
def get_seuils(depot, search=None, vue="tous", start=0):
	"""Une ligne par article stocké actif : son stock dans le dépôt, son seuil et la quantité à commander."""
	require_bureau()
	frappe.has_permission(ARTICLE, "read", throw=True)
	if vue not in VUES:
		frappe.throw(_("Vue inconnue."))
	depot = check_depot(depot)
	items = frappe.get_all(
		ARTICLE,
		filters={"disabled": 0, "is_stock_item": 1, "has_variants": 0},
		fields=["name", "item_name", "stock_uom", "modified"],
		order_by="item_name asc",
		limit_page_length=0,
	)
	if cstr(search).strip():
		items = filter_words(items, search)
	codes = [item.name for item in items]
	seuils = _seuils(depot, codes)
	stocks = _stocks(depot, codes)
	lignes = [_ligne(item, seuils.get(item.name), stocks.get(item.name, 0)) for item in items]
	compte = {
		"tous": len(lignes),
		"avec_seuil": sum(1 for row in lignes if row["seuil"]),
		"sous_seuil": sum(1 for row in lignes if row["seuil"] and row["stock"] < row["seuil"]),
	}
	if vue == "avec_seuil":
		lignes = [row for row in lignes if row["seuil"]]
	elif vue == "sous_seuil":
		lignes = [row for row in lignes if row["seuil"] and row["stock"] < row["seuil"]]
	start = max(cint(start), 0)
	return {
		"depot": depot,
		"lignes": lignes[start : start + PAGE],
		"total": len(lignes),
		"compte": compte,
		"start": start,
		"page": PAGE,
	}


def _quantite(valeur, label):
	text = cstr(valeur).strip().replace(" ", "").replace(",", ".")
	if not text:
		return 0
	try:
		value = float(text)
	except ValueError:
		frappe.throw(_("{0} illisible : {1}.").format(label, valeur))
	if value < 0:
		frappe.throw(_("{0} ne peut pas être négatif.").format(label))
	return value


@frappe.whitelist(methods=["POST"])
def set_seuil(depot, article, modified, seuil=None, quantite=None):
	"""Pose, change ou retire (seuil vide ou 0) le seuil d'un article dans un dépôt. Quantité vide : le seuil."""
	require_bureau()
	depot = check_depot(depot)
	doc = frappe.get_doc(ARTICLE, article)
	doc.check_permission("write")
	_stale(
		modified,
		doc.modified,
		_("Cet article vient d'être modifié par ailleurs. Il a été rechargé : vérifiez, puis recommencez."),
	)
	if cint(doc.disabled) or not cint(doc.is_stock_item):
		frappe.throw(_("Seul un article stocké et actif a un seuil."))
	niveau = _quantite(seuil, _("Le seuil"))
	a_commander = _quantite(quantite, _("La quantité à commander")) or niveau
	row = next(
		(r for r in doc.get("reorder_levels") or [] if r.warehouse == depot and r.material_request_type == TYPE), None
	)
	if not niveau:
		if row:
			doc.remove(row)
	elif row:
		row.warehouse_reorder_level = niveau
		row.warehouse_reorder_qty = a_commander
	else:
		doc.append(
			"reorder_levels",
			{
				"warehouse": depot,
				"warehouse_group": depot,
				"warehouse_reorder_level": niveau,
				"warehouse_reorder_qty": a_commander,
				"material_request_type": TYPE,
			},
		)
	doc.flags.ignore_messages = True
	doc.save()
	frappe.clear_last_message()
	item = frappe._dict(name=doc.name, item_name=doc.item_name, stock_uom=doc.stock_uom, modified=doc.modified)
	return _ligne(item, _seuils(depot, [doc.name]).get(doc.name), _stocks(depot, [doc.name]).get(doc.name, 0))
