# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Dépôts du poste de bureau (/bureau/depots) : liste, aperçu, fiche, création, modification et suppression.

Les Warehouse de la société qui reçoivent du stock (les groupes servent de parents). La fiche montre le stock du dépôt
par article et son grand livre. Un dépôt se crée et se modifie ici (nom à la création, groupe parent, désactivé) ;
Frappe refuse de désactiver ou de supprimer un dépôt qui a encore du stock ou des écritures.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

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
from unicare.api.bureau_stock import BIN, WAREHOUSE, bins, company, ledger, readable

LIST_FIELDS = [
	"name",
	"modified",
	"creation",
	"warehouse_name",
	"parent_warehouse",
	"warehouse_type",
	"disabled",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = {
	"all": lambda row: True,
	"actifs": lambda row: not row["desactive"],
	"desactives": lambda row: bool(row["desactive"]),
	"avec_stock": lambda row: flt(row["articles"]) > 0,
}
SORT_KEYS = {"depot", "parent", "type", "articles", "valeur", "name", "creation", "modified"}


def _totaux(names=None):
	"""Par dépôt : articles en stock (quantité positive) et valeur du stock. `None` sans droit sur le stock."""
	if not readable(BIN):
		return None
	if names is not None and not names:
		return {}
	condition = "where warehouse in %(names)s" if names is not None else ""
	rows = frappe.db.sql(
		f"""
		select warehouse, sum(case when actual_qty > 0 then 1 else 0 end) as articles, sum(stock_value) as valeur
		from `tabBin` {condition}
		group by warehouse
		""",
		{"names": tuple(names or ())},
		as_dict=True,
	)
	return {row.warehouse: {"articles": cint(row.articles), "valeur": flt(row.valeur, 2)} for row in rows}


def _list_row(depot, totaux):
	total = (totaux or {}).get(depot.name, {"articles": 0, "valeur": 0})
	return {
		"name": depot.name,
		"modified": depot.modified,
		"creation": str(depot.creation),
		"tags": row_tags(depot),
		"cloche": row_bell(depot),
		"depot": depot.warehouse_name or depot.name,
		"parent": depot.parent_warehouse or None,
		"type": depot.warehouse_type or None,
		"desactive": cint(depot.disabled),
		"articles": total["articles"] if totaux is not None else None,
		"valeur": total["valeur"] if totaux is not None else None,
	}


def order_depots(rows, sort=None, direction=None):
	key = sort if sort in SORT_KEYS else "depot"
	descending = cstr(direction) == "desc" and sort in SORT_KEYS
	ordered = sorted(rows, key=lambda row: cstr(row["depot"]).casefold())
	filled = [row for row in ordered if row.get(key) not in (None, "")]
	empty = [row for row in ordered if row.get(key) in (None, "")]

	def value(row):
		item = row[key]
		return item if isinstance(item, (int, float)) else cstr(item).casefold()

	return sorted(filled, key=value, reverse=descending) + empty


@frappe.whitelist()
def get_depots(view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), WAREHOUSE)
	depots = frappe.get_list(
		WAREHOUSE,
		filters=[["company", "=", company()], ["is_group", "=", 0], *conditions],
		distinct=has_child_filter(conditions, WAREHOUSE),
		or_filters=[["warehouse_name", "like", pattern], ["name", "like", pattern], ["parent_warehouse", "like", pattern]]
		if value
		else None,
		fields=LIST_FIELDS,
		limit_page_length=0,
	)
	totaux = _totaux([row.name for row in depots])
	rows = [_list_row(row, totaux) for row in depots]
	counts = {name: sum(1 for row in rows if test(row)) for name, test in VIEWS.items()}
	ordered = order_depots([row for row in rows if VIEWS[view](row)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"depots": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


def _groupes():
	return frappe.get_all(
		WAREHOUSE, filters={"company": company(), "is_group": 1, "disabled": 0}, order_by="name asc", pluck="name"
	)


def _types():
	return frappe.get_all("Warehouse Type", order_by="name asc", pluck="name")


@frappe.whitelist()
def get_depot_options():
	require_bureau()
	groupes = _groupes()
	return {
		"groupes": groupes,
		"types": _types(),
		"filter_fields": doctype_filter_fields(
			WAREHOUSE, {"parent_warehouse": [{"value": name, "label": name} for name in groupes]}
		),
	}


def _stock(name):
	"""Le stock du dépôt par article, avec la désignation. `None` sans droit sur le stock."""
	if not readable(BIN):
		return None
	rows = bins(warehouse=name)
	names = {row.item_code for row in rows}
	labels = dict(frappe.get_all("Item", filters={"name": ["in", list(names) or [""]]}, fields=["name", "item_name"], as_list=True))
	return [
		{
			"article": row.item_code,
			"designation": labels.get(row.item_code) or row.item_code,
			"quantite": row.actual_qty,
			"reserve": row.reserved_qty,
			"projete": row.projected_qty,
			"unite": row.stock_uom,
			"valeur": row.stock_value,
		}
		for row in rows
		if row.actual_qty or row.reserved_qty or row.projected_qty
	]


def _depot_payload(doc, full=False):
	totaux = _totaux([doc.name])
	total = (totaux or {}).get(doc.name, {"articles": 0, "valeur": 0})
	payload = {
		"name": doc.name,
		"modified": str(doc.modified),
		"tags": row_tags(doc.as_dict()),
		"depot": doc.warehouse_name or doc.name,
		"parent": doc.parent_warehouse or None,
		"type": doc.warehouse_type or None,
		"desactive": cint(doc.disabled),
		"groupe": cint(doc.is_group),
		"compte": doc.account or None,
		"articles": total["articles"] if totaux is not None else None,
		"valeur": total["valeur"] if totaux is not None else None,
		"can_edit": bool(doc.has_permission("write")),
		"can_delete": bool(doc.has_permission("delete")),
	}
	if full:
		payload.update(
			{
				"stock": _stock(doc.name),
				"mouvements": ledger(warehouse=doc.name) if readable("Stock Ledger Entry") else None,
				"comments": activity.comment_summary(WAREHOUSE, doc.name),
			}
		)
	return payload


@frappe.whitelist()
def get_depot(name, full=0):
	require_bureau()
	doc = frappe.get_doc(WAREHOUSE, name)
	doc.check_permission("read")
	return _depot_payload(doc, full=cint(full))


def _depot_for_write(name, modified):
	require_bureau()
	doc = frappe.get_doc(WAREHOUSE, name)
	doc.check_permission("write")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_("Ce dépôt vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."),
			frappe.TimestampMismatchError,
		)
	return doc


def _clean(values):
	values = _parse(values) or {}
	cleaned = {}
	if "parent" in values:
		parent = cstr(values["parent"]).strip()
		if parent and parent not in _groupes():
			frappe.throw(_("Choisissez un groupe de dépôts de la liste."))
		cleaned["parent_warehouse"] = parent or None
	if "type" in values:
		kind = cstr(values["type"]).strip()
		if kind and kind not in _types():
			frappe.throw(_("Type de dépôt inconnu."))
		cleaned["warehouse_type"] = kind or None
	if "desactive" in values:
		cleaned["disabled"] = cint(values["desactive"])
	return cleaned, cstr(values.get("depot")).strip()


@frappe.whitelist(methods=["POST"])
def create_depot(values=None):
	"""Crée un dépôt de la société. Frappe le nomme « Nom - abréviation »."""
	require_bureau()
	frappe.has_permission(WAREHOUSE, "create", throw=True)
	cleaned, label = _clean(values)
	if not label:
		frappe.throw(_("Saisissez le nom du dépôt."))
	doc = frappe.new_doc(WAREHOUSE)
	doc.update({"warehouse_name": label, "company": company(), "is_group": 0, **cleaned})
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_depot(name, modified, values=None):
	"""Groupe parent, type et désactivation. Le nom d'un dépôt ne change pas ici : il est dans ses écritures."""
	doc = _depot_for_write(name, modified)
	cleaned, _label = _clean(values)
	if cleaned.get("disabled") and not doc.disabled:
		stock = frappe.db.sql("select sum(actual_qty) from `tabBin` where warehouse = %s", doc.name)[0][0]
		if flt(stock):
			frappe.throw(_("Ce dépôt a encore du stock : videz-le avant de le désactiver."))
	doc.update(cleaned)
	doc.save()
	return _depot_payload(doc, full=True)


@frappe.whitelist(methods=["POST"])
def delete_depot(name, modified):
	"""Supprime le dépôt, comme sur le Desk : Frappe refuse s'il a du stock ou des écritures."""
	doc = _depot_for_write(name, modified)
	doc.check_permission("delete")
	frappe.delete_doc(WAREHOUSE, doc.name)
	return {"deleted": doc.name}


def depot_for_bulk(name, modified):
	return _depot_for_write(name, modified)


@frappe.whitelist()
def get_depot_activity(name):
	require_bureau()
	return activity.get_feed(WAREHOUSE, name)


@frappe.whitelist(methods=["POST"])
def add_depot_comment(name, text, mentions=None):
	require_bureau()
	return activity.add_comment(WAREHOUSE, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_depot_comment(name, comment, text, mentions=None):
	require_bureau()
	return activity.update_comment(WAREHOUSE, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_depot_comment(name, comment):
	require_bureau()
	return activity.delete_comment(WAREHOUSE, name, comment)
