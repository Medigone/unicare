# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Réceptions du poste de bureau (/bureau/receptions) : liste, aperçu, fiche, préparation et cycle.

Le Purchase Receipt standard d'ERPNext, pendant d'achat du bon de livraison (`bureau_livraisons`). Une réception naît
d'une commande d'achat (`bureau_commandes_achat.create_suivante`). Sur le brouillon, chaque ligne se prépare ici :
quantité reçue, dépôt et, pour un article géré par lots, le n° de lot du fournisseur et sa péremption (le lot est créé
au besoin). Une réception validée entre le stock ; elle donne sa facture d'achat ou un retour fournisseur, qui est
lui-même une réception à quantités négatives. Les règles de lot du conditionnement restent dans
`unicare.conditionnement.purchase_receipt_hooks` (dépôt par défaut, lot obligatoire pour les fûts et le conditionnement).
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_fullname, getdate

from unicare.api import activity
from unicare.api.bureau_achats import drop_invoice_batches, replace_disabled_taxes
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
from unicare.conditionnement.purchase_receipt_hooks import CONDITIONNEMENT_RECEIPT_TYPES

RECEPTION = "Purchase Receipt"
LIGNES = "Purchase Receipt Item"
FACTURE_ACHAT = "Purchase Invoice"

FIELDS = [
	"name",
	"modified",
	"creation",
	"status",
	"docstatus",
	"supplier",
	"supplier_name",
	"posting_date",
	"is_return",
	"return_against",
	"grand_total",
	"per_billed",
	"supplier_delivery_note",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "brouillons", "a_facturer", "facturees", "retours", "clos")
SORT_KEYS = {
	"name",
	"fournisseur_label",
	"date",
	"status",
	"bl_fournisseur",
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


def _lines_by_reception(names):
	if not names:
		return {}
	rows = frappe.get_all(
		LIGNES,
		filters={"parent": ["in", names], "parenttype": RECEPTION},
		fields=["parent", "item_name", "item_code", "purchase_order"],
		order_by="idx asc",
	)
	lines = {}
	for row in rows:
		entry = lines.setdefault(row.parent, {"articles": [], "commandes": []})
		entry["articles"].append(row.item_name or row.item_code)
		if row.purchase_order and row.purchase_order not in entry["commandes"]:
			entry["commandes"].append(row.purchase_order)
	return lines


def _list_row(reception, lines):
	entry = lines.get(reception.name, {"articles": [], "commandes": []})
	articles = entry["articles"]
	return {
		"name": reception.name,
		"modified": reception.modified,
		"creation": str(reception.creation),
		"tags": row_tags(reception),
		"cloche": row_bell(reception),
		"fournisseur": reception.supplier,
		"fournisseur_label": reception.supplier_name or reception.supplier,
		"date": _day(reception.posting_date),
		"status": _status(reception),
		"retour": cint(reception.is_return),
		"retour_de": reception.return_against or None,
		"bl_fournisseur": reception.supplier_delivery_note or None,
		"total_ttc": flt(reception.grand_total),
		"facture": flt(reception.per_billed, 1),
		"commandes": ", ".join(entry["commandes"]) or None,
		"lignes": len(articles),
		"articles": ", ".join(articles[:3]) + (f" (+{len(articles) - 3})" if len(articles) > 3 else ""),
	}


def order_receptions(rows, sort=None, direction=None):
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
def get_receptions(
	view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None
):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), RECEPTION)
	receptions = frappe.get_list(
		RECEPTION,
		filters=conditions,
		distinct=has_child_filter(conditions, RECEPTION),
		or_filters=[
			["name", "like", pattern],
			["supplier_name", "like", pattern],
			["supplier", "like", pattern],
			["supplier_delivery_note", "like", pattern],
		]
		if value
		else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	lines = _lines_by_reception([row.name for row in receptions])
	rows = [_list_row(row, lines) for row in receptions]
	counts = {name: sum(1 for row in rows if in_view(name, row)) for name in VIEWS}
	ordered = order_receptions([row for row in rows if in_view(view, row)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"receptions": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


@frappe.whitelist()
def get_reception_options():
	require_bureau()
	return {"filter_fields": doctype_filter_fields(RECEPTION)}


def _item(item_code):
	values = frappe.get_cached_value(
		"Item", item_code, ["is_stock_item", "has_batch_no", "custom_type_conditionnement"], as_dict=True
	)
	return values or frappe._dict()


def _depots(company):
	"""Dépôts où recevoir : ceux de la société, hors groupes."""
	return frappe.get_all(
		"Warehouse", filters={"company": company, "is_group": 0, "disabled": 0}, order_by="name asc", pluck="name"
	)


def _lot(batch_no):
	if not batch_no:
		return None, None
	values = frappe.db.get_value("Batch", batch_no, ["expiry_date"], as_dict=True)
	return batch_no, _day(values.expiry_date) if values else None


def _line(item):
	meta = _item(item.item_code)
	lot, peremption = _lot(item.batch_no)
	return {
		"name": item.name,
		"article": item.item_code,
		"designation": item.item_name or item.item_code,
		"quantite": flt(item.qty),
		"unite": item.uom,
		"depot": item.warehouse or None,
		"lot": lot,
		"peremption": peremption,
		"avec_lot": cint(meta.has_batch_no),
		# Les fûts et le conditionnement exigent le lot du fournisseur (purchase_receipt_hooks).
		"lot_obligatoire": int(cint(meta.has_batch_no) and meta.custom_type_conditionnement in CONDITIONNEMENT_RECEIPT_TYPES),
		"stock": cint(meta.is_stock_item),
		"prix": flt(item.rate),
		"montant": flt(item.amount),
		"commande": item.purchase_order or None,
	}


def blocked(doc):
	"""Ce qui empêche de valider : aucune ligne, une ligne de stock sans dépôt, un lot attendu et non saisi."""
	if doc.docstatus != 0:
		return []
	reasons = []
	if not doc.items:
		reasons.append(_("La réception n'a aucune ligne."))
	for index, item in enumerate(doc.items, start=1):
		meta = _item(item.item_code)
		if not cint(meta.is_stock_item):
			continue
		label = _("Ligne {0} ({1})").format(index, item.item_name or item.item_code)
		if not item.warehouse and not doc.set_warehouse:
			reasons.append(_("{0} : choisissez le dépôt.").format(label))
		if not cint(doc.is_return) and cint(meta.has_batch_no) and not item.batch_no:
			reasons.append(_("{0} : saisissez le n° de lot du fournisseur.").format(label))
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
		and frappe.has_permission(FACTURE_ACHAT, "create")
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
	"""Factures d'achat et retours faits depuis cette réception."""
	factures = None
	if frappe.has_permission(FACTURE_ACHAT, "read"):
		factures = [
			{"name": row.name, "status": _status(row), "date": _day(row.posting_date), "total": flt(row.grand_total)}
			for row in frappe.get_list(
				FACTURE_ACHAT,
				filters=[
					["Purchase Invoice Item", "purchase_receipt", "=", doc.name],
					[FACTURE_ACHAT, "docstatus", "<", 2],
				],
				fields=["name", "status", "docstatus", "posting_date", "grand_total"],
				order_by=f"`tab{FACTURE_ACHAT}`.posting_date desc",
				distinct=True,
			)
		]
	retours = [
		{"name": row.name, "status": _status(row), "date": _day(row.posting_date), "total": flt(row.grand_total)}
		for row in frappe.get_list(
			RECEPTION,
			filters={"return_against": doc.name, "docstatus": ["<", 2]},
			fields=["name", "status", "docstatus", "posting_date", "grand_total"],
			order_by="posting_date desc",
		)
	]
	return factures, retours


def _reception_payload(doc):
	allowed = actions(doc)
	factures, retours = _suivantes(doc)
	commandes = []
	for item in doc.items:
		if item.purchase_order and item.purchase_order not in commandes:
			commandes.append(item.purchase_order)
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"status": _status(doc),
		"docstatus": cint(doc.docstatus),
		"retour": cint(doc.is_return),
		"retour_de": doc.return_against or None,
		"fournisseur": doc.supplier,
		"fournisseur_label": doc.supplier_name or doc.supplier,
		"date": _day(doc.posting_date),
		"bl_fournisseur": doc.supplier_delivery_note or None,
		"transport": doc.lr_no or None,
		"transporteur": doc.get("transporter_name") or None,
		"depot": doc.set_warehouse or None,
		"depots": _depots(doc.company) if "preparer" in allowed else [],
		"cree_par": get_fullname(doc.owner),
		"lignes": [_line(item) for item in doc.items],
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
		"comments": activity.comment_summary(RECEPTION, doc.name),
	}


@frappe.whitelist()
def get_reception(name):
	require_bureau()
	doc = frappe.get_doc(RECEPTION, name)
	doc.check_permission("read")
	return _reception_payload(doc)


def _load(name, modified):
	require_bureau()
	doc = frappe.get_doc(RECEPTION, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Cette réception vient d'être modifiée par ailleurs. Elle a été rechargée : vérifiez-la, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	return doc


def _for_work(name, modified, action):
	doc = _load(name, modified)
	if action not in actions(doc):
		frappe.throw(_("Cette action n'est pas possible sur cette réception."), frappe.PermissionError)
	return doc


def _set_lot(doc, row, lot, peremption):
	"""Le lot du fournisseur : repris s'il existe pour cet article, sinon créé avec sa péremption."""
	from unicare.conditionnement.stock import ensure_batch

	if not lot:
		row.batch_no = None
		return
	existing_item = frappe.db.get_value("Batch", lot, "item")
	if existing_item and existing_item != row.item_code:
		frappe.throw(_("Le lot {0} appartient à l'article {1}, pas à {2}.").format(lot, existing_item, row.item_code))
	if not frappe.has_permission("Batch", "create" if not existing_item else "write"):
		frappe.throw(_("Votre rôle ne peut pas enregistrer de lot."), frappe.PermissionError)
	row.batch_no = ensure_batch(
		item_code=row.item_code,
		batch_no=lot,
		expiry_date=peremption,
		supplier=doc.supplier,
		lot_fournisseur=lot,
		origine="Réception",
	)
	row.use_serial_batch_fields = 1


@frappe.whitelist(methods=["POST"])
def prepare_reception(name, modified, lignes=None, bl_fournisseur=None, transport=None):
	"""Brouillon : quantité reçue, dépôt, lot et péremption de chaque ligne, plus le BL du fournisseur.

	Une ligne à quantité nulle est retirée : elle reste à recevoir sur la commande.
	"""
	doc = _for_work(name, modified, "preparer")
	lignes = _parse(lignes) or []
	if not isinstance(lignes, list):
		frappe.throw(_("Lignes illisibles."))
	rows = {row.name: row for row in doc.items}
	depots = set(_depots(doc.company))
	removed = set()
	for ligne in lignes:
		row = rows.get(cstr((ligne or {}).get("name")))
		if not row:
			frappe.throw(_("Cette ligne n'est plus dans la réception : rechargez-la."))
		if "quantite" in ligne:
			quantite = flt(ligne["quantite"])
			if cint(doc.is_return):
				if quantite >= 0:
					frappe.throw(_("Une ligne de retour se saisit en quantité négative."))
			elif quantite < 0:
				frappe.throw(_("Une quantité reçue ne peut pas être négative."))
			if quantite == 0:
				removed.add(row.name)
				continue
			row.qty = quantite
			row.received_qty = quantite
			row.rejected_qty = 0
		if "depot" in ligne:
			depot = cstr(ligne["depot"]).strip()
			if depot and depot not in depots:
				frappe.throw(_("Dépôt inconnu : {0}.").format(depot))
			row.warehouse = depot or None
		if "lot" in ligne or "peremption" in ligne:
			lot = cstr(ligne.get("lot", row.batch_no)).strip()
			peremption = ligne.get("peremption") or None
			if peremption:
				peremption = getdate(peremption)
			if lot and not cint(_item(row.item_code).has_batch_no):
				frappe.throw(_("L'article {0} n'est pas géré par lots.").format(row.item_code))
			if not cint(doc.is_return):
				_set_lot(doc, row, lot, peremption)
	if removed:
		doc.set("items", [row for row in doc.items if row.name not in removed])
		if not doc.items:
			frappe.throw(_("La réception doit garder au moins une ligne : supprimez le brouillon plutôt."))
	if bl_fournisseur is not None:
		doc.supplier_delivery_note = cstr(bl_fournisseur).strip() or None
	if transport is not None:
		doc.lr_no = cstr(transport).strip() or None
	doc.save()
	return _reception_payload(doc)


@frappe.whitelist(methods=["POST"])
def validate_reception(name, modified):
	"""Soumet la réception : le stock entre (ou sort, pour un retour) et la commande avance."""
	doc = _for_work(name, modified, "valider")
	reasons = blocked(doc)
	if reasons:
		frappe.throw(" ".join(reasons))
	doc.submit()
	return _reception_payload(doc)


@frappe.whitelist(methods=["POST"])
def cancel_reception(name, modified):
	doc = _for_work(name, modified, "annuler")
	doc.cancel()
	return _reception_payload(doc)


@frappe.whitelist(methods=["POST"])
def delete_reception(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(RECEPTION, doc.name)
	return {"deleted": doc.name}


@frappe.whitelist(methods=["POST"])
def create_suivante(name, modified, kind):
	"""Facture d'achat ou retour fournisseur en brouillon, par les outils standard d'ERPNext."""
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
		make_purchase_invoice,
		make_purchase_return,
	)

	if kind not in ("facture", "retour"):
		frappe.throw(_("Pièce inconnue."))
	doc = _for_work(name, modified, kind)
	target = make_purchase_invoice(doc.name) if kind == "facture" else make_purchase_return(doc.name)
	if not target.get("items"):
		frappe.throw(
			_("Il ne reste rien à facturer.") if kind == "facture" else _("Il ne reste rien à retourner.")
		)
	note = replace_disabled_taxes(target)
	drop_invoice_batches(target)
	target.insert()
	return {
		"doctype": target.doctype,
		"note": note,
		"name": target.name,
		"reception": _reception_payload(frappe.get_doc(RECEPTION, doc.name)),
	}


def reception_for_bulk(name, modified):
	return _load(name, modified)


def bulk_guard(doc, operation):
	if doc.docstatus != 0:
		return _("Réception validée ou annulée : elle ne change plus.")
	return None


def _check_activity(name):
	require_bureau()
	frappe.get_doc(RECEPTION, name).check_permission("read")


@frappe.whitelist()
def get_reception_activity(name):
	require_bureau()
	return activity.get_feed(RECEPTION, name)


@frappe.whitelist(methods=["POST"])
def add_reception_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(RECEPTION, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_reception_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(RECEPTION, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_reception_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(RECEPTION, name, comment)
