# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Bons de livraison du poste de bureau (/bureau/livraisons) : liste, aperçu, fiche, préparation et cycle.

Un bon naît d'une commande (`bureau_commandes.create_suivante`), jamais seul : le stock réservé et le suivi livré /
facturé restent ceux d'ERPNext. Sur le brouillon, chaque ligne se prépare ici : dépôt, lot (le plus proche de sa
péremption proposé d'abord) et quantité. Un bon validé sort le stock ; il donne sa facture ou un bon de retour,
qui est lui-même un bon de livraison (quantités négatives) préparé et validé de la même façon.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_fullname, strip_html

from unicare.api import activity
from unicare.api.bureau_devis import _day, _status
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

LIVRAISON = "Delivery Note"
LIGNES = "Delivery Note Item"
FACTURE = "Sales Invoice"

FIELDS = [
	"name",
	"modified",
	"creation",
	"status",
	"docstatus",
	"customer",
	"customer_name",
	"posting_date",
	"is_return",
	"return_against",
	"grand_total",
	"per_billed",
	"lr_no",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "brouillons", "a_facturer", "facturees", "retours", "clos")
SORT_KEYS = {
	"name",
	"client_label",
	"date",
	"status",
	"total_ttc",
	"facture",
	"lignes",
	"creation",
	"modified",
}


def in_view(view, row):
	if view == "all":
		return True
	status = row["status"]
	if view == "brouillons":
		return status == "Draft"
	if view == "retours":
		return bool(row["retour"])
	if view == "a_facturer":
		return status == "To Bill" and not row["retour"]
	if view == "facturees":
		return status == "Completed" and not row["retour"]
	return status in ("Cancelled", "Closed", "Return Issued")


def _lines_by_livraison(names):
	if not names:
		return {}
	rows = frappe.get_all(
		LIGNES,
		filters={"parent": ["in", names], "parenttype": LIVRAISON},
		fields=["parent", "item_name", "item_code", "against_sales_order"],
		order_by="idx asc",
	)
	lines = {}
	for row in rows:
		entry = lines.setdefault(row.parent, {"articles": [], "commandes": []})
		entry["articles"].append(row.item_name or row.item_code)
		if row.against_sales_order and row.against_sales_order not in entry["commandes"]:
			entry["commandes"].append(row.against_sales_order)
	return lines


def _list_row(livraison, lines):
	entry = lines.get(livraison.name, {"articles": [], "commandes": []})
	articles = entry["articles"]
	return {
		"name": livraison.name,
		"modified": livraison.modified,
		"creation": str(livraison.creation),
		"tags": row_tags(livraison),
		"cloche": row_bell(livraison),
		"client": livraison.customer,
		"client_label": livraison.customer_name or livraison.customer,
		"date": _day(livraison.posting_date),
		"status": _status(livraison),
		"retour": cint(livraison.is_return),
		"retour_de": livraison.return_against or None,
		"total_ttc": flt(livraison.grand_total),
		"facture": flt(livraison.per_billed, 1),
		"transport": livraison.lr_no or None,
		"commandes": ", ".join(entry["commandes"]) or None,
		"lignes": len(articles),
		"articles": ", ".join(articles[:3]) + (f" (+{len(articles) - 3})" if len(articles) > 3 else ""),
	}


def order_livraisons(rows, sort=None, direction=None):
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
def get_livraisons(
	view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None
):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), LIVRAISON)
	livraisons = frappe.get_list(
		LIVRAISON,
		filters=conditions,
		distinct=has_child_filter(conditions, LIVRAISON),
		or_filters=[
			["name", "like", pattern],
			["customer_name", "like", pattern],
			["customer", "like", pattern],
			["lr_no", "like", pattern],
		]
		if value
		else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	lines = _lines_by_livraison([row.name for row in livraisons])
	rows = [_list_row(row, lines) for row in livraisons]
	counts = {name: sum(1 for row in rows if in_view(name, row)) for name in VIEWS}
	ordered = order_livraisons([row for row in rows if in_view(view, row)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"livraisons": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


@frappe.whitelist()
def get_livraison_options():
	require_bureau()
	return {"filter_fields": doctype_filter_fields(LIVRAISON)}


def _warehouses(item_code):
	"""Stock réel de l'article par dépôt, le plus fourni d'abord."""
	rows = frappe.get_all(
		"Bin",
		filters={"item_code": item_code, "actual_qty": [">", 0]},
		fields=["warehouse", "actual_qty"],
		order_by="actual_qty desc",
	)
	return [{"depot": row.warehouse, "qty": flt(row.actual_qty, 3)} for row in rows]


def _lots(item_code):
	"""Lots disponibles par dépôt, hors lots périmés, la péremption la plus proche d'abord (FEFO)."""
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	lots = {}
	for row in get_batch_qty(item_code=item_code) or []:
		if flt(row.get("qty")) <= 0:
			continue
		lots.setdefault(row.get("warehouse"), []).append(
			{
				"lot": row.get("batch_no"),
				"qty": flt(row.get("qty"), 3),
				"peremption": _day(row.get("expiry_date")),
			}
		)
	for entries in lots.values():
		entries.sort(key=lambda entry: (entry["peremption"] is None, cstr(entry["peremption"]), entry["lot"]))
	return lots


def _has_batch(item_code):
	return cint(frappe.get_cached_value("Item", item_code, "has_batch_no"))


def _line(item, preparation):
	line = {
		"name": item.name,
		"article": item.item_code,
		"designation": item.item_name or item.item_code,
		"quantite": flt(item.qty),
		"unite": item.uom,
		"depot": item.warehouse or None,
		"lot": item.batch_no or None,
		"avec_lot": _has_batch(item.item_code),
		"stock": cint(frappe.get_cached_value("Item", item.item_code, "is_stock_item")),
		"prix": flt(item.rate),
		"montant": flt(item.amount),
		"commande": item.against_sales_order or None,
	}
	if preparation and line["stock"]:
		line["depots"] = _warehouses(item.item_code)
		line["lots"] = _lots(item.item_code) if line["avec_lot"] else {}
	return line


def blocked(doc):
	"""Ce qui empêche de valider : une ligne sans dépôt, un lot non choisi, une quantité au-delà du disponible."""
	if doc.docstatus != 0:
		return []
	reasons = []
	if not doc.items:
		reasons.append(_("Le bon n'a aucune ligne."))
	for index, item in enumerate(doc.items, start=1):
		if not cint(frappe.get_cached_value("Item", item.item_code, "is_stock_item")):
			continue
		label = _("Ligne {0} ({1})").format(index, item.item_name or item.item_code)
		if not item.warehouse:
			reasons.append(_("{0} : choisissez le dépôt.").format(label))
			continue
		if cint(doc.is_return):
			continue
		if _has_batch(item.item_code) and not item.batch_no:
			reasons.append(_("{0} : choisissez le lot.").format(label))
			continue
		if item.batch_no:
			available = next(
				(
					entry["qty"]
					for entry in _lots(item.item_code).get(item.warehouse, [])
					if entry["lot"] == item.batch_no
				),
				0,
			)
		else:
			available = next(
				(entry["qty"] for entry in _warehouses(item.item_code) if entry["depot"] == item.warehouse), 0
			)
		if flt(item.stock_qty or item.qty) > available:
			reasons.append(
				_("{0} : {1} disponible(s) seulement.").format(
					label, frappe.format(available, {"fieldtype": "Float"})
				)
			)
	return reasons


def actions(doc):
	found = []
	if doc.docstatus == 0:
		if doc.has_permission("write"):
			found.append("preparer")
		if doc.has_permission("submit"):
			found.append("valider")
		if doc.has_permission("delete"):
			found.append("supprimer")
		return found
	if doc.docstatus != 1:
		return found
	if (
		not cint(doc.is_return)
		and flt(doc.per_billed) < 100
		and doc.status not in ("Closed",)
		and frappe.has_permission(FACTURE, "create")
	):
		found.append("facture")
	if (
		not cint(doc.is_return)
		and doc.status not in ("Return Issued", "Closed")
		and doc.has_permission("create")
	):
		found.append("retour")
	if doc.has_permission("cancel"):
		found.append("annuler")
	return found


def _suivantes(doc):
	"""Factures et bons de retour faits depuis ce bon."""
	factures = None
	if frappe.has_permission(FACTURE, "read"):
		factures = [
			{
				"name": row.name,
				"status": _status(row),
				"date": _day(row.posting_date),
				"total": flt(row.grand_total),
			}
			for row in frappe.get_list(
				FACTURE,
				filters=[
					["Sales Invoice Item", "delivery_note", "=", doc.name],
					[FACTURE, "docstatus", "<", 2],
				],
				fields=["name", "status", "docstatus", "posting_date", "grand_total"],
				order_by=f"`tab{FACTURE}`.posting_date desc",
				distinct=True,
			)
		]
	retours = [
		{
			"name": row.name,
			"status": _status(row),
			"date": _day(row.posting_date),
			"total": flt(row.grand_total),
		}
		for row in frappe.get_list(
			LIVRAISON,
			filters={"return_against": doc.name, "docstatus": ["<", 2]},
			fields=["name", "status", "docstatus", "posting_date", "grand_total"],
			order_by="posting_date desc",
		)
	]
	return factures, retours


def _livraison_payload(doc):
	allowed = actions(doc)
	preparation = "preparer" in allowed
	factures, retours = _suivantes(doc)
	commandes = []
	for item in doc.items:
		if item.against_sales_order and item.against_sales_order not in commandes:
			commandes.append(item.against_sales_order)
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"status": _status(doc),
		"docstatus": cint(doc.docstatus),
		"retour": cint(doc.is_return),
		"retour_de": doc.return_against or None,
		"client": doc.customer,
		"client_label": doc.customer_name or doc.customer,
		"date": _day(doc.posting_date),
		"adresse": (doc.address_display and strip_html(doc.address_display).strip()) or None,
		"transport": doc.lr_no or None,
		"vehicule": doc.vehicle_no or None,
		"cree_par": get_fullname(doc.owner),
		"lignes": [_line(item, preparation) for item in doc.items],
		"total": flt(doc.net_total),
		"total_taxes": flt(doc.total_taxes_and_charges),
		"total_ttc": flt(doc.grand_total),
		"facture": flt(doc.per_billed, 1),
		"commandes": commandes,
		"factures": factures,
		"retours": retours,
		"actions": allowed,
		"blocked": blocked(doc) if "valider" in allowed else [],
		"can_print": bool(doc.has_permission("print")),
		"comments": activity.comment_summary(LIVRAISON, doc.name),
	}


@frappe.whitelist()
def get_livraison(name):
	require_bureau()
	doc = frappe.get_doc(LIVRAISON, name)
	doc.check_permission("read")
	return _livraison_payload(doc)


def _for_work(name, modified, action):
	require_bureau()
	doc = frappe.get_doc(LIVRAISON, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_("Ce bon vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."),
			frappe.TimestampMismatchError,
		)
	if action not in actions(doc):
		frappe.throw(_("Cette action n'est pas possible sur ce bon de livraison."), frappe.PermissionError)
	return doc


@frappe.whitelist(methods=["POST"])
def prepare_livraison(name, modified, lignes=None, transport=None, vehicule=None):
	"""Brouillon : dépôt, lot et quantité de chaque ligne, plus le transport. Une ligne absente ne change pas.

	Une ligne à quantité nulle est retirée du bon : elle reste à livrer sur la commande.
	"""
	doc = _for_work(name, modified, "preparer")
	lignes = _parse(lignes) or []
	if not isinstance(lignes, list):
		frappe.throw(_("Lignes illisibles."))
	rows = {row.name: row for row in doc.items}
	removed = set()
	for ligne in lignes:
		row = rows.get(cstr((ligne or {}).get("name")))
		if not row:
			frappe.throw(_("Cette ligne n'est plus dans le bon : rechargez-le."))
		if "quantite" in ligne:
			quantite = flt(ligne["quantite"])
			if cint(doc.is_return):
				if quantite >= 0:
					frappe.throw(_("Une ligne de retour se saisit en quantité négative."))
			elif quantite < 0:
				frappe.throw(_("Une quantité livrée ne peut pas être négative."))
			if quantite == 0:
				removed.add(row.name)
				continue
			row.qty = quantite
		if "depot" in ligne:
			depot = cstr(ligne["depot"]).strip()
			if depot and not frappe.db.exists(
				"Warehouse", {"name": depot, "is_group": 0, "company": doc.company}
			):
				frappe.throw(_("Dépôt inconnu : {0}.").format(depot))
			row.warehouse = depot or None
		if "lot" in ligne:
			lot = cstr(ligne["lot"]).strip()
			if lot and frappe.db.get_value("Batch", lot, "item") != row.item_code:
				frappe.throw(_("Le lot {0} n'appartient pas à l'article {1}.").format(lot, row.item_code))
			row.batch_no = lot or None
			row.use_serial_batch_fields = 1
	if removed:
		doc.set("items", [row for row in doc.items if row.name not in removed])
		if not doc.items:
			frappe.throw(_("Le bon doit garder au moins une ligne : supprimez le brouillon plutôt."))
	if transport is not None:
		doc.lr_no = cstr(transport).strip() or None
	if vehicule is not None:
		doc.vehicle_no = cstr(vehicule).strip() or None
	doc.save()
	return _livraison_payload(doc)


@frappe.whitelist(methods=["POST"])
def validate_livraison(name, modified):
	"""Soumet le bon : le stock sort (ou rentre, pour un retour) et la commande avance."""
	doc = _for_work(name, modified, "valider")
	reasons = blocked(doc)
	if reasons:
		frappe.throw(" ".join(reasons))
	doc.submit()
	return _livraison_payload(doc)


@frappe.whitelist(methods=["POST"])
def cancel_livraison(name, modified):
	doc = _for_work(name, modified, "annuler")
	doc.cancel()
	return _livraison_payload(doc)


@frappe.whitelist(methods=["POST"])
def delete_livraison(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(LIVRAISON, doc.name)
	return {"deleted": doc.name}


@frappe.whitelist(methods=["POST"])
def create_suivante(name, modified, kind):
	"""Facture ou bon de retour en brouillon, par les outils standard d'ERPNext."""
	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice, make_sales_return

	if kind not in ("facture", "retour"):
		frappe.throw(_("Pièce inconnue."))
	doc = _for_work(name, modified, kind)
	target = make_sales_invoice(doc.name) if kind == "facture" else make_sales_return(doc.name)
	if not target.get("items"):
		frappe.throw(
			_("Il ne reste rien à facturer.") if kind == "facture" else _("Il ne reste rien à retourner.")
		)
	target.insert()
	return {
		"doctype": target.doctype,
		"name": target.name,
		"livraison": _livraison_payload(frappe.get_doc(LIVRAISON, doc.name)),
	}


def livraison_for_bulk(name, modified):
	require_bureau()
	doc = frappe.get_doc(LIVRAISON, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_("Ce bon vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."),
			frappe.TimestampMismatchError,
		)
	return doc


def bulk_guard(doc, operation):
	if doc.docstatus != 0:
		return _("Bon validé ou annulé : il ne change plus.")
	return None


def _check_activity(name):
	require_bureau()
	frappe.get_doc(LIVRAISON, name).check_permission("read")


@frappe.whitelist()
def get_livraison_activity(name):
	require_bureau()
	return activity.get_feed(LIVRAISON, name)


@frappe.whitelist(methods=["POST"])
def add_livraison_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(LIVRAISON, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_livraison_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(LIVRAISON, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_livraison_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(LIVRAISON, name, comment)
