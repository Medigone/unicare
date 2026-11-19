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
VUES = ("tous", "avec_seuil", "sous_seuil", "sans_seuil")
PAGE = 50


def _stale(modified, current, message=None):
	if cstr(modified) != str(current):
		frappe.throw(
			message
			or _(
				"Ces réglages viennent d'être modifiés par ailleurs. Ils ont été rechargés : vérifiez-les, puis recommencez."
			),
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
		"arbre": _arbre(),
		"resume": _resume_depots(),
		"unites": frappe.get_all("UOM", filters={"enabled": 1}, order_by="name asc", pluck="name"),
		"droits": {
			"parametres": bool(frappe.has_permission(PARAMETRES, "write")),
			"seuils": bool(frappe.has_permission(ARTICLE, "write")),
			"creer_depot": bool(frappe.has_permission("Warehouse", "create")),
			"supprimer_depot": bool(frappe.has_permission("Warehouse", "delete")),
		},
	}


DEPOT = "Warehouse"


def _arbre():
	"""Les dossiers (groupes) et dépôts actifs de la société, chacun avec son dossier parent (None sous la racine).
	La racine de l'ERP (« Tous les entrepôts ») n'est pas renvoyée."""
	from unicare.api.bureau_stock import company

	rows = frappe.get_all(
		DEPOT,
		filters={"company": company(), "disabled": 0},
		fields=["name", "warehouse_name", "parent_warehouse", "is_group", "modified"],
		order_by="lft asc",
		limit_page_length=0,
	)
	racines = {row.name for row in rows if cint(row.is_group) and not row.parent_warehouse}
	return [
		{
			"name": row.name,
			"label": row.warehouse_name or row.name,
			"parent": None
			if not row.parent_warehouse or row.parent_warehouse in racines
			else row.parent_warehouse,
			"dossier": bool(cint(row.is_group)),
			"modified": str(row.modified),
		}
		for row in rows
		if row.name not in racines
	]


def _racine_depots():
	"""Le groupe racine des dépôts de la société (« Tous les entrepôts »)."""
	from unicare.api.bureau_stock import company

	groupes = frappe.get_all(
		DEPOT, filters={"company": company(), "is_group": 1}, fields=["name", "parent_warehouse"], order_by="lft asc"
	)
	return next((row.name for row in groupes if not row.parent_warehouse), None)


def _dossier_depots(nom):
	"""Un dossier de dépôts de la société (actif), ou la racine sans `nom`."""
	from unicare.api.bureau_stock import company

	nom = cstr(nom).strip()
	if not nom:
		return _racine_depots()
	if not frappe.db.exists(DEPOT, {"name": nom, "company": company(), "is_group": 1, "disabled": 0}):
		frappe.throw(_("« {0} » n'est pas un dossier de dépôts.").format(nom))
	return nom


def _resume_depots():
	"""Par dépôt : le nombre d'articles actifs avec un seuil, et ceux dont le stock est passé dessous."""
	actifs = set(
		frappe.get_all(
			ARTICLE,
			filters={"disabled": 0, "is_stock_item": 1, "has_variants": 0},
			pluck="name",
			limit_page_length=0,
		)
	)
	seuils = [
		row
		for row in frappe.get_all(
			SEUIL,
			filters={
				"parenttype": ARTICLE,
				"material_request_type": TYPE,
				"warehouse_reorder_level": [">", 0],
			},
			fields=["parent", "warehouse", "warehouse_reorder_level"],
			limit_page_length=0,
		)
		if row.parent in actifs
	]
	stocks = {
		(row.item_code, row.warehouse): flt(row.actual_qty, 3)
		for row in frappe.get_all(
			"Bin",
			filters={"item_code": ["in", list({row.parent for row in seuils}) or [""]]},
			fields=["item_code", "warehouse", "actual_qty"],
			limit_page_length=0,
		)
	}
	resume = {}
	for row in seuils:
		depot = resume.setdefault(row.warehouse, {"seuils": 0, "sous": 0})
		depot["seuils"] += 1
		if stocks.get((row.parent, row.warehouse), 0) < flt(row.warehouse_reorder_level, 3):
			depot["sous"] += 1
	return resume


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
		filters={
			"parenttype": ARTICLE,
			"parent": ["in", list(codes)],
			"warehouse": depot,
			"material_request_type": TYPE,
		},
		fields=["parent", "warehouse_reorder_level", "warehouse_reorder_qty"],
	)
	return {row.parent: row for row in rows}


def _stocks(depot, codes):
	if not codes:
		return {}
	rows = frappe.get_all(
		"Bin",
		filters={"warehouse": depot, "item_code": ["in", list(codes)]},
		fields=["item_code", "actual_qty"],
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
	compte["sans_seuil"] = compte["tous"] - compte["avec_seuil"]
	if vue == "avec_seuil":
		lignes = [row for row in lignes if row["seuil"]]
	elif vue == "sous_seuil":
		lignes = [row for row in lignes if row["seuil"] and row["stock"] < row["seuil"]]
	elif vue == "sans_seuil":
		lignes = [row for row in lignes if not row["seuil"]]
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
		(
			r
			for r in doc.get("reorder_levels") or []
			if r.warehouse == depot and r.material_request_type == TYPE
		),
		None,
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
	item = frappe._dict(
		name=doc.name, item_name=doc.item_name, stock_uom=doc.stock_uom, modified=doc.modified
	)
	return _ligne(item, _seuils(depot, [doc.name]).get(doc.name), _stocks(depot, [doc.name]).get(doc.name, 0))


@frappe.whitelist()
def get_a_commander(depot):
	"""Les articles du dépôt passés sous leur seuil, avec leur quantité à commander, pour préparer une commande
	d'achat ; et le fournisseur par défaut quand tous ces articles ont le même."""
	require_bureau()
	frappe.has_permission(ARTICLE, "read", throw=True)
	depot = check_depot(depot)
	rows = frappe.get_all(
		SEUIL,
		filters={
			"parenttype": ARTICLE,
			"warehouse": depot,
			"material_request_type": TYPE,
			"warehouse_reorder_level": [">", 0],
		},
		fields=["parent", "warehouse_reorder_level", "warehouse_reorder_qty"],
		limit_page_length=0,
	)
	if not rows:
		return {"depot": depot, "lignes": [], "fournisseur": None}
	items = {
		item.name: item
		for item in frappe.get_all(
			ARTICLE,
			filters={
				"name": ["in", [row.parent for row in rows]],
				"disabled": 0,
				"is_stock_item": 1,
				"is_purchase_item": 1,
			},
			fields=["name", "item_name", "stock_uom"],
		)
	}
	stocks = _stocks(depot, list(items))
	lignes = []
	for row in rows:
		item = items.get(row.parent)
		niveau = flt(row.warehouse_reorder_level, 3)
		if not item or stocks.get(item.name, 0) >= niveau:
			continue
		lignes.append(
			{
				"article": item.name,
				"designation": item.item_name or item.name,
				"unite": item.stock_uom,
				"stock": stocks.get(item.name, 0),
				"seuil": niveau,
				"quantite": flt(row.warehouse_reorder_qty, 3) or niveau,
			}
		)
	lignes.sort(key=lambda ligne: ligne["designation"])
	from unicare.api.bureau_achats import buying_prices

	prix = buying_prices([ligne["article"] for ligne in lignes])
	for ligne in lignes:
		ligne["prix_tarif"] = prix.get(ligne["article"])
	fournisseurs = {
		row.default_supplier
		for row in frappe.get_all(
			"Item Default",
			filters={"parenttype": ARTICLE, "parent": ["in", [ligne["article"] for ligne in lignes] or [""]]},
			fields=["parent", "default_supplier"],
		)
	}
	fournisseur = None
	if lignes and len(fournisseurs) == 1:
		nom = next(iter(fournisseurs))
		if nom and frappe.db.exists("Supplier", {"name": nom, "disabled": 0}):
			fournisseur = {"name": nom, "label": frappe.db.get_value("Supplier", nom, "supplier_name") or nom}
	return {"depot": depot, "lignes": lignes, "fournisseur": fournisseur}


@frappe.whitelist(methods=["POST"])
def supprimer_depot(depot):
	"""Supprime un dépôt qui n'a jamais servi, avec ses seuils. Refusé pour le dépôt de réception par défaut, un dépôt
	qui a du stock ou des mouvements (il se désactive alors depuis sa fiche), ou qu'une pièce ou une fiche utilise."""
	require_bureau()
	depot = check_depot(depot)
	frappe.has_permission("Warehouse", "delete", throw=True)
	if frappe.db.get_single_value(PARAMETRES, "default_warehouse") == depot:
		frappe.throw(
			_(
				"« {0} » est le dépôt de réception par défaut : choisissez-en un autre dans Paramètres."
			).format(depot)
		)
	if flt(frappe.db.sql("select sum(actual_qty) from `tabBin` where warehouse = %s", depot)[0][0]):
		frappe.throw(_("« {0} » a encore du stock : videz-le avant de le supprimer.").format(depot))
	if frappe.db.exists("Stock Ledger Entry", {"warehouse": depot}):
		frappe.throw(
			_(
				"« {0} » a déjà eu des mouvements de stock : il ne peut pas être supprimé. Désactivez-le depuis sa fiche."
			).format(depot)
		)
	frappe.db.savepoint("supprimer_depot")
	try:
		articles = {
			row.parent
			for champ in ("warehouse", "warehouse_group")
			for row in frappe.get_all(SEUIL, filters={"parenttype": ARTICLE, champ: depot}, fields=["parent"])
		}
		for article in articles:
			doc = frappe.get_doc(ARTICLE, article)
			doc.check_permission("write")
			for row in [
				r for r in doc.get("reorder_levels") or [] if depot in (r.warehouse, r.warehouse_group)
			]:
				doc.remove(row)
			doc.flags.ignore_messages = True
			doc.save()
		frappe.delete_doc("Warehouse", depot)
	except frappe.LinkExistsError:
		frappe.db.rollback(save_point="supprimer_depot")
		frappe.clear_last_message()
		frappe.throw(
			_(
				"« {0} » est encore utilisé par des pièces ou des fiches : il ne peut pas être supprimé. Désactivez-le depuis sa fiche."
			).format(depot)
		)
	frappe.clear_last_message()
	return get_reglages_stock()


@frappe.whitelist(methods=["POST"])
def creer_dossier_depots(nom, dossier=None):
	"""Nouveau dossier (groupe ERP) pour ranger des dépôts, sous `dossier` ou la racine."""
	require_bureau()
	frappe.has_permission(DEPOT, "create", throw=True)
	from unicare.api.bureau_stock import company

	nom = cstr(nom).strip()
	if not nom:
		frappe.throw(_("Donnez un nom au dossier."))
	doc = frappe.new_doc(DEPOT)
	doc.update(
		{
			"warehouse_name": nom,
			"company": company(),
			"is_group": 1,
			"parent_warehouse": _dossier_depots(dossier),
		}
	)
	doc.insert()
	return get_reglages_stock()


@frappe.whitelist(methods=["POST"])
def deplacer_depot(name, modified, dossier=None):
	"""Range un dépôt ou un dossier dans un autre dossier (la racine sans `dossier`). Son stock ne change pas."""
	require_bureau()
	from unicare.api.bureau_stock import company

	doc = frappe.get_doc(DEPOT, name)
	if doc.company != company() or doc.name == _racine_depots():
		frappe.throw(_("Ce dépôt ne se range pas ici."))
	doc.check_permission("write")
	_stale(
		modified,
		doc.modified,
		_("Ce dépôt vient d'être modifié par ailleurs. La page a été rechargée : recommencez."),
	)
	cible = _dossier_depots(dossier)
	if cible == doc.name:
		frappe.throw(_("Un dossier ne se range pas dans lui-même."))
	if cint(doc.is_group):
		cible_lft = frappe.db.get_value(DEPOT, cible, "lft")
		if doc.lft < cible_lft < doc.rgt:
			frappe.throw(
				_("« {0} » est rangé dans « {1} » : il ne peut pas le contenir.").format(cible, doc.name)
			)
	doc.parent_warehouse = cible
	doc.save()
	return get_reglages_stock()


@frappe.whitelist(methods=["POST"])
def supprimer_dossier_depots(name):
	"""Supprime un dossier de dépôts vide."""
	require_bureau()
	frappe.has_permission(DEPOT, "delete", throw=True)
	doc = frappe.get_doc(DEPOT, name)
	if not cint(doc.is_group) or doc.name == _racine_depots():
		frappe.throw(_("« {0} » n'est pas un dossier de dépôts.").format(name))
	if frappe.db.exists(DEPOT, {"parent_warehouse": doc.name}):
		frappe.throw(
			_("Le dossier « {0} » n'est pas vide : déplacez ou supprimez d'abord son contenu.").format(name)
		)
	doc.check_permission("delete")
	frappe.delete_doc(DEPOT, doc.name)
	return get_reglages_stock()
