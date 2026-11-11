# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Articles du poste de bureau (/bureau/articles) : liste, aperçu, fiche, création et modification.

Même contrat que `bureau_clients.py` : les listes passent par `frappe.get_list` pour garder les permissions, chaque
écriture passe par `doc.insert()` ou `doc.save()` pour garder validations et hooks (code FU/CO/PF/AU, lots forcés),
et une modification reçoit la date `modified` affichée à l'écran. Un document lié que le rôle ne peut pas lire
donne `None` : l'écran n'en parle pas, sans erreur.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, strip_html

from unicare.api import activity
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
from unicare.conditionnement.constants import TYPES_AVEC_LOT

ITEM = "Item"
TYPE_FIELD = "custom_type_conditionnement"
ROOT_ITEM_GROUP = "Tous les Groupes d'Articles"
RELATED_LIMIT = 50
ARTICLE_SEARCH_LIMIT = 8

LIST_FIELDS = [
	"name",
	"modified",
	"creation",
	"item_name",
	TYPE_FIELD,
	"item_group",
	"stock_uom",
	"is_stock_item",
	"has_batch_no",
	"disabled",
	"_user_tags",
	BELL_FIELD,
]

# Vue → type conditionnement. Un article désactivé n'apparaît que dans sa vue.
TYPE_VIEWS = {
	"fut": "Fût",
	"conditionnement": "Conditionnement",
	"produit_fini": "Produit fini",
	"autre": "Autre",
}
VIEWS = {
	"all": lambda row: not row["disabled"],
	**{
		key: (lambda value: lambda row: not row["disabled"] and row["type"] == value)(value)
		for key, value in TYPE_VIEWS.items()
	},
	"desactive": lambda row: bool(row["disabled"]),
}
SORT_KEYS = {"designation", "name", "type", "groupe", "uom", "stock", "creation", "modified"}

# Champs modifiables depuis la fenêtre. Le type ne change plus : il a fixé le code (FU-, CO-, PF-, AU-).
EDITABLE_FIELDS = {
	"designation": "item_name",
	"groupe": "item_group",
	"uom": "stock_uom",
	"is_stock_item": "is_stock_item",
	"has_batch_no": "has_batch_no",
	"description": "description",
	"shelf_life_in_days": "shelf_life_in_days",
	"is_purchase_item": "is_purchase_item",
	"is_sales_item": "is_sales_item",
	"disabled": "disabled",
}
CHECK_FIELDS = {"is_stock_item", "has_batch_no", "is_purchase_item", "is_sales_item", "disabled"}
REQUIRED_VALUES = {
	"type": _("Choisissez le type d'article."),
	"designation": _("Saisissez la désignation."),
	"groupe": _("Choisissez le groupe d'articles."),
	"uom": _("Choisissez l'unité de stock."),
}

# Achats et ventes : (clé, document, ligne, champ de la date, champ du tiers).
MOUVEMENTS = (
	("commandes_achat", "Purchase Order", "Purchase Order Item", "transaction_date", "supplier"),
	("receptions", "Purchase Receipt", "Purchase Receipt Item", "posting_date", "supplier"),
	("commandes_vente", "Sales Order", "Sales Order Item", "transaction_date", "customer"),
	("factures", "Sales Invoice", "Sales Invoice Item", "posting_date", "customer"),
)
RECETTE = "Recette de Conditionnement"
ORDRE = "Ordre de Conditionnement"


def _readable(doctype):
	return frappe.has_permission(doctype, "read")


def _stocks(names=None):
	"""Quantité réelle par article, tous dépôts confondus, pour qui lit le stock."""
	if not _readable("Bin"):
		return None
	filters = {}
	if names is not None:
		if not names:
			return {}
		filters["item_code"] = ["in", names]
	rows = frappe.get_all(
		"Bin", filters=filters, fields=["item_code", "sum(actual_qty) as qty"], group_by="item_code"
	)
	return {row.item_code: flt(row.qty, 3) for row in rows}


def _list_row(item, stocks):
	return {
		"name": item.name,
		"modified": item.modified,
		"creation": str(item.creation),
		"tags": row_tags(item),
		"cloche": row_bell(item),
		"designation": item.item_name or item.name,
		"type": item.get(TYPE_FIELD),
		"groupe": item.item_group,
		"uom": item.stock_uom,
		"lots": cint(item.has_batch_no),
		"disabled": cint(item.disabled),
		"stock": stocks.get(item.name, 0) if stocks is not None and cint(item.is_stock_item) else None,
	}


def order_articles(rows, sort=None, direction=None):
	"""Par désignation, ou par la colonne demandée. Une ligne sans valeur reste à la fin, dans les deux sens."""
	key = sort if sort in SORT_KEYS else "designation"
	descending = cstr(direction) == "desc" and sort in SORT_KEYS
	ordered = sorted(rows, key=lambda row: cstr(row["designation"]).casefold())
	filled = [row for row in ordered if row.get(key) not in (None, "")]
	empty = [row for row in ordered if row.get(key) in (None, "")]

	def value(row):
		item = row[key]
		return item if isinstance(item, (int, float)) else cstr(item).casefold()

	return sorted(filled, key=value, reverse=descending) + empty


@frappe.whitelist()
def get_articles(
	view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None
):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), ITEM)
	items = frappe.get_list(
		ITEM,
		filters=[["has_variants", "=", 0], *conditions],
		distinct=has_child_filter(conditions, ITEM),
		or_filters=[
			["item_name", "like", pattern],
			["name", "like", pattern],
			["item_group", "like", pattern],
		]
		if value
		else None,
		fields=LIST_FIELDS,
		limit_page_length=0,
	)
	stocks = _stocks()
	rows = [_list_row(item, stocks) for item in items]
	counts = {name: sum(1 for row in rows if test(row)) for name, test in VIEWS.items()}
	ordered = order_articles([row for row in rows if VIEWS[view](row)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"articles": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


def _plain(values):
	return [{"value": value, "label": value} for value in values]


def _types():
	return [
		option for option in (frappe.get_meta(ITEM).get_field(TYPE_FIELD).options or "").split("\n") if option
	]


def _groupes():
	return frappe.get_all(
		"Item Group", filters={"is_group": 0}, order_by="name asc", pluck="name", limit_page_length=0
	)


@frappe.whitelist()
def get_article_options():
	"""Valeurs proposées dans les filtres et la fenêtre. Des noms seulement : tout rôle du bureau les reçoit."""
	require_bureau()
	groupes = _groupes()
	# Les unités déjà employées d'abord : la liste complète en compte plus de deux cents.
	uoms = frappe.get_all(
		ITEM, filters={"has_variants": 0}, pluck="stock_uom", distinct=True, limit_page_length=0
	)
	types = _types()
	return {
		"types": types,
		"types_avec_lot": list(TYPES_AVEC_LOT),
		"groupes": groupes,
		"uoms": sorted({uom for uom in uoms if uom}),
		"filter_fields": doctype_filter_fields(
			ITEM, {TYPE_FIELD: _plain(types), "item_group": _plain(groupes)}
		),
	}


@frappe.whitelist()
def search_articles(search=None):
	"""Articles dont la désignation ressemble à la saisie, pour repérer un doublon avant de créer."""
	require_bureau()
	value = cstr(search).strip()
	if not value:
		return []
	items = frappe.get_list(
		ITEM,
		or_filters=[["item_name", "like", f"%{value}%"], ["name", "like", f"%{value}%"]],
		fields=["name", "item_name", TYPE_FIELD, "disabled"],
		order_by="item_name asc",
		limit_page_length=ARTICLE_SEARCH_LIMIT,
	)
	return [
		{
			"name": item.name,
			"label": item.item_name or item.name,
			"type": item.get(TYPE_FIELD),
			"disabled": cint(item.disabled),
		}
		for item in items
	]


def _bins(name):
	if not _readable("Bin"):
		return None
	rows = frappe.get_all(
		"Bin",
		filters={"item_code": name},
		fields=["warehouse", "actual_qty", "reserved_qty", "ordered_qty", "projected_qty"],
		order_by="actual_qty desc",
	)
	return [
		{key: (flt(value, 3) if key != "warehouse" else value) for key, value in row.items()} for row in rows
	]


def _lots(doc):
	if not cint(doc.has_batch_no) or not _readable("Batch"):
		return None
	return frappe.get_list(
		"Batch",
		filters={"item": doc.name},
		fields=[
			"name",
			"batch_qty",
			"manufacturing_date",
			"expiry_date",
			"disabled",
			"custom_lot_fournisseur as lot_fournisseur",
			"custom_origine as origine",
			"custom_ordre_conditionnement as ordre",
		],
		order_by="creation desc",
		limit_page_length=RELATED_LIMIT,
	)


def _recettes(name):
	"""Recettes qui produisent l'article, et celles où il entre comme ingrédient."""
	if not _readable(RECETTE):
		return None
	produit = frappe.get_list(
		RECETTE,
		filters={"produit_fini": name},
		fields=["name", "nom_produit", "actif", "quantite_base", "uom", "rendement_theorique"],
		order_by="actif desc, modified desc",
		limit_page_length=RELATED_LIMIT,
	)
	ingredient = frappe.get_list(
		RECETTE,
		filters=[["Ingredient Recette", "item_code", "=", name]],
		fields=[
			"name",
			"produit_fini",
			"nom_produit",
			"actif",
			"`tabIngredient Recette`.qty as qty",
			"`tabIngredient Recette`.uom as uom",
		],
		order_by="`tabRecette de Conditionnement`.actif desc, `tabRecette de Conditionnement`.modified desc",
		limit_page_length=RELATED_LIMIT,
	)
	return {"produit": produit, "ingredient": ingredient}


def _ordres(name):
	"""Ordres de conditionnement qui produisent l'article, et ceux qui le consomment comme matière."""
	if not _readable(ORDRE):
		return None
	fields = ["name", "produit_fini", "nom_produit", "date_prevue", "workflow_state", "docstatus"]
	produit = frappe.get_list(
		ORDRE,
		filters={"produit_fini": name},
		fields=[*fields, "qty_prevue", "qty_reelle_pf", "uom"],
		order_by="date_prevue desc, creation desc",
		limit_page_length=RELATED_LIMIT,
	)
	matiere = frappe.get_list(
		ORDRE,
		filters=[["Matiere Ordre Conditionnement", "item_code", "=", name]],
		fields=[
			*fields,
			"`tabMatiere Ordre Conditionnement`.qty_theorique as qty_prevue",
			"`tabMatiere Ordre Conditionnement`.qty_reelle as qty_reelle_pf",
			"`tabMatiere Ordre Conditionnement`.uom as uom",
		],
		order_by="`tabOrdre de Conditionnement`.date_prevue desc, `tabOrdre de Conditionnement`.creation desc",
		limit_page_length=RELATED_LIMIT,
	)
	return {"produit": produit, "matiere": matiere}


def _mouvements(name):
	"""Dernières lignes d'achat et de vente de l'article. `None` par document que la personne ne lit pas."""
	result = {}
	for key, doctype, child, date_field, party in MOUVEMENTS:
		if not _readable(doctype):
			result[key] = None
			continue
		result[key] = frappe.get_list(
			doctype,
			filters=[[child, "item_code", "=", name], [doctype, "docstatus", "<", 2]],
			fields=[
				"name",
				f"{date_field} as date",
				f"{party} as tiers",
				"status",
				f"`tab{child}`.qty as qty",
				f"`tab{child}`.uom as uom",
				f"`tab{child}`.amount as montant",
			],
			order_by=f"`tab{doctype}`.{date_field} desc, `tab{doctype}`.creation desc",
			limit_page_length=RELATED_LIMIT,
		)
	return result


def _article_payload(doc, full=False):
	stock = None
	if cint(doc.is_stock_item):
		stocks = _stocks([doc.name])
		stock = stocks.get(doc.name, 0) if stocks is not None else None
	payload = {
		"name": doc.name,
		"modified": doc.modified,
		"tags": row_tags(doc.as_dict()),
		"designation": doc.item_name or doc.name,
		"type": doc.get(TYPE_FIELD),
		"groupe": doc.item_group,
		"uom": doc.stock_uom,
		"is_stock_item": cint(doc.is_stock_item),
		"has_batch_no": cint(doc.has_batch_no),
		"is_purchase_item": cint(doc.is_purchase_item),
		"is_sales_item": cint(doc.is_sales_item),
		"disabled": cint(doc.disabled),
		"description": strip_html(cstr(doc.description)).strip() or None,
		"shelf_life_in_days": cint(doc.shelf_life_in_days) or None,
		"barcodes": [row.barcode for row in doc.get("barcodes") or [] if row.barcode],
		"image": doc.image,
		"depuis": str(doc.creation)[:10],
		"stock": stock,
		"can_edit": bool(doc.has_permission("write")),
		"can_delete": bool(doc.has_permission("delete")),
	}
	if full:
		payload.update(
			{
				"bins": _bins(doc.name) if cint(doc.is_stock_item) else None,
				"lots": _lots(doc),
				"recettes": _recettes(doc.name),
				"ordres": _ordres(doc.name),
				"mouvements": _mouvements(doc.name),
				"comments": activity.comment_summary(ITEM, doc.name),
			}
		)
	return payload


@frappe.whitelist()
def get_article(name, full=0):
	require_bureau()
	doc = frappe.get_doc(ITEM, name)
	doc.check_permission("read")
	return _article_payload(doc, full=cint(full))


def _article_for_write(name, modified):
	"""Article à modifier : mêmes droits que le Desk, et version identique à celle affichée à l'écran."""
	require_bureau()
	doc = frappe.get_doc(ITEM, name)
	doc.check_permission("write")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Cet article vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	return doc


def _clean_values(values):
	values = _parse(values) or {}
	cleaned = {}
	for key, value in values.items():
		if key in CHECK_FIELDS:
			cleaned[key] = 1 if cint(value) else 0
		elif key == "shelf_life_in_days":
			cleaned[key] = cint(value) if cstr(value).strip() else 0
		else:
			cleaned[key] = cstr(value).strip()
	return cleaned


def _check_required(values, keys):
	for key in keys:
		if not values.get(key):
			frappe.throw(REQUIRED_VALUES[key])


def _check_unique(designation, current=None):
	"""Deux articles actifs ne portent pas la même désignation : le Desk ne le vérifie pas, le bureau si."""
	existing = frappe.db.get_value(ITEM, {"item_name": designation, "disabled": 0}, "name")
	if existing and existing != current:
		frappe.throw(_("Un article « {0} » existe déjà ({1}).").format(designation, existing))


def _check_choices(values):
	if values.get("type") and values["type"] not in _types():
		frappe.throw(_("Type d'article inconnu : {0}.").format(values["type"]))
	if values.get("groupe") and not frappe.db.exists("Item Group", {"name": values["groupe"], "is_group": 0}):
		frappe.throw(_("Choisissez un groupe d'articles de la liste."))
	if values.get("uom") and not frappe.db.exists("UOM", {"name": values["uom"], "enabled": 1}):
		frappe.throw(_("Choisissez une unité de la liste."))
	if cint(values.get("shelf_life_in_days")) < 0:
		frappe.throw(_("La durée de conservation ne peut pas être négative."))


@frappe.whitelist(methods=["POST"])
def create_article(values=None):
	"""Crée un article. Le code vient du type (CustomItem) ; un fût ou un produit fini est toujours stocké par lots."""
	require_bureau()
	frappe.has_permission(ITEM, "create", throw=True)
	values = _clean_values(values)
	_check_required(values, REQUIRED_VALUES)
	_check_choices(values)
	_check_unique(values["designation"])
	avec_lot = values["type"] in TYPES_AVEC_LOT
	doc = frappe.new_doc(ITEM)
	doc.update(
		{
			TYPE_FIELD: values["type"],
			"item_name": values["designation"],
			"item_group": values["groupe"],
			"stock_uom": values["uom"],
			"is_stock_item": 1 if avec_lot else values.get("is_stock_item", 1),
			"has_batch_no": 1 if avec_lot else values.get("has_batch_no", 0),
			"description": values.get("description") or values["designation"],
			"shelf_life_in_days": values.get("shelf_life_in_days") or 0,
		}
	)
	if values.get("barcode"):
		doc.append("barcodes", {"barcode": values["barcode"]})
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_article(name, modified, values=None):
	"""Seuls les champs changés arrivent : ce qu'un autre a modifié sur le Desk sur un autre champ reste."""
	doc = _article_for_write(name, modified)
	values = {key: value for key, value in _clean_values(values).items() if key in EDITABLE_FIELDS}
	_check_required(values, [key for key in REQUIRED_VALUES if key in values])
	_check_choices(values)
	if "designation" in values:
		_check_unique(values["designation"], name)
	for key, value in values.items():
		doc.set(
			EDITABLE_FIELDS[key],
			value if key in CHECK_FIELDS or key == "shelf_life_in_days" else value or None,
		)
	doc.save()
	return _article_payload(doc, full=True)


# Fil de l'article : mêmes commentaires que la timeline du Desk.
@frappe.whitelist()
def get_article_activity(name):
	require_bureau()
	return activity.get_feed(ITEM, name)


@frappe.whitelist(methods=["POST"])
def add_article_comment(name, text, mentions=None):
	require_bureau()
	return activity.add_comment(ITEM, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_article_comment(name, comment, text, mentions=None):
	require_bureau()
	return activity.update_comment(ITEM, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_article_comment(name, comment):
	require_bureau()
	return activity.delete_comment(ITEM, name, comment)


@frappe.whitelist(methods=["POST"])
def delete_article(name, modified):
	"""Supprime la fiche, comme sur le Desk : Frappe refuse tant qu'une pièce ou un autre document y est lié."""
	doc = _article_for_write(name, modified)
	doc.check_permission("delete")
	frappe.delete_doc(ITEM, doc.name)
	return {"deleted": doc.name}
