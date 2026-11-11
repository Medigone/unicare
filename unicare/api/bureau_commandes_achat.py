# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Commandes d'achat du poste de bureau (/bureau/commandes-achat) : liste, aperçu, fiche, création et cycle.

Le Purchase Order standard d'ERPNext, pendant d'achat de la commande client (`bureau_commandes`). Elle naît d'un devis
fournisseur (`bureau_devis_fournisseur.create_commande_achat`) ou se crée ici : fournisseur, réception prévue, TVA
déductible et lignes au prix d'achat connu. Un brouillon se modifie, se valide ou se supprime ; une commande validée
donne ses réceptions et ses factures d'achat (en brouillon, par les outils d'ERPNext), se met en attente, se clôture
ou s'annule. Chaque écriture reçoit la date `modified` affichée à l'écran.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_fullname, getdate, today

from unicare.api import activity
from unicare.api.bureau_achats import (
	drop_invoice_batches,
	replace_disabled_taxes,
	buying_price_list,
	check_supplier,
	clean_lines,
	set_lines,
	set_purchase_taxes,
	taxes_options,
)
from unicare.api.bureau_devis import _company, _day, _status, line_description, tax_lines
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

COMMANDE_ACHAT = "Purchase Order"
LIGNES = "Purchase Order Item"
RECEPTION = "Purchase Receipt"
FACTURE_ACHAT = "Purchase Invoice"

A_RECEVOIR = ("To Receive and Bill", "To Receive")
A_FACTURER = ("To Receive and Bill", "To Bill")
EN_COURS = ("To Receive and Bill", "To Receive", "To Bill")
CLOS = ("Completed", "Closed", "Cancelled", "Delivered")

FIELDS = [
	"name",
	"modified",
	"creation",
	"owner",
	"status",
	"docstatus",
	"supplier",
	"supplier_name",
	"transaction_date",
	"schedule_date",
	"net_total",
	"grand_total",
	"per_received",
	"per_billed",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "brouillons", "a_recevoir", "a_facturer", "en_retard", "en_attente", "clos")
SORT_KEYS = {
	"name",
	"fournisseur_label",
	"date",
	"reception",
	"status",
	"total",
	"total_ttc",
	"recu",
	"facture",
	"lignes",
	"creation",
	"modified",
}


def in_view(view, row, current_day=None):
	if view == "all":
		return True
	status = row["status"]
	if view == "brouillons":
		return status == "Draft"
	if view == "a_recevoir":
		return status in A_RECEVOIR
	if view == "a_facturer":
		return status in A_FACTURER
	if view == "en_retard":
		reception = row.get("reception")
		return status in A_RECEVOIR and bool(reception) and getdate(reception) < getdate(current_day or today())
	if view == "en_attente":
		return status == "On Hold"
	return status in CLOS


def _lines_by_commande(names):
	"""Articles et devis fournisseur d'origine de chaque commande lisible, dans l'ordre des lignes."""
	if not names:
		return {}
	rows = frappe.get_all(
		LIGNES,
		filters={"parent": ["in", names], "parenttype": COMMANDE_ACHAT},
		fields=["parent", "item_name", "item_code", "supplier_quotation"],
		order_by="idx asc",
	)
	lines = {}
	for row in rows:
		entry = lines.setdefault(row.parent, {"articles": [], "devis": []})
		entry["articles"].append(row.item_name or row.item_code)
		if row.supplier_quotation and row.supplier_quotation not in entry["devis"]:
			entry["devis"].append(row.supplier_quotation)
	return lines


def _list_row(commande, lines):
	entry = lines.get(commande.name, {"articles": [], "devis": []})
	articles = entry["articles"]
	return {
		"name": commande.name,
		"modified": commande.modified,
		"creation": str(commande.creation),
		"tags": row_tags(commande),
		"cloche": row_bell(commande),
		"fournisseur": commande.supplier,
		"fournisseur_label": commande.supplier_name or commande.supplier,
		"date": _day(commande.transaction_date),
		"reception": _day(commande.schedule_date),
		"status": _status(commande),
		"total": flt(commande.net_total),
		"total_ttc": flt(commande.grand_total),
		"recu": flt(commande.per_received, 1),
		"facture": flt(commande.per_billed, 1),
		"devis": ", ".join(entry["devis"]) or None,
		"lignes": len(articles),
		"articles": ", ".join(articles[:3]) + (f" (+{len(articles) - 3})" if len(articles) > 3 else ""),
	}


def order_commandes(rows, sort=None, direction=None):
	"""Les plus récentes d'abord, ou par la colonne demandée. Une ligne sans valeur reste à la fin."""
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
def get_commandes_achat(
	view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None
):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), COMMANDE_ACHAT)
	commandes = frappe.get_list(
		COMMANDE_ACHAT,
		filters=conditions,
		distinct=has_child_filter(conditions, COMMANDE_ACHAT),
		or_filters=[
			["name", "like", pattern],
			["supplier_name", "like", pattern],
			["supplier", "like", pattern],
		]
		if value
		else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	lines = _lines_by_commande([row.name for row in commandes])
	rows = [_list_row(row, lines) for row in commandes]
	current_day = today()
	counts = {name: sum(1 for row in rows if in_view(name, row, current_day)) for name in VIEWS}
	ordered = order_commandes([row for row in rows if in_view(view, row, current_day)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"commandes": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


@frappe.whitelist()
def get_commande_achat_options():
	"""Valeurs proposées dans les filtres et dans la fenêtre de la commande d'achat."""
	require_bureau()
	return {**taxes_options(_company()), "filter_fields": doctype_filter_fields(COMMANDE_ACHAT)}


def _suivantes(doctype, child, name):
	"""Réceptions ou factures faites depuis cette commande, par leurs lignes. `None` sans droit de lecture."""
	if not frappe.has_permission(doctype, "read"):
		return None
	rows = frappe.get_list(
		doctype,
		filters=[[child, "purchase_order", "=", name], [doctype, "docstatus", "<", 2]],
		fields=["name", "status", "docstatus", "posting_date", "grand_total"],
		order_by=f"`tab{doctype}`.posting_date desc",
		distinct=True,
	)
	return [
		{"name": row.name, "status": _status(row), "date": _day(row.posting_date), "total": flt(row.grand_total)}
		for row in rows
	]


def blocked(doc):
	"""Ce qui empêche de valider : aucune ligne, une ligne sans prix, une réception prévue manquante ou trop tôt."""
	reasons = []
	if not doc.items:
		reasons.append(_("La commande n'a aucune ligne."))
	missing = sum(1 for item in doc.items if flt(item.rate) <= 0)
	if missing:
		reasons.append(_("{0} ligne(s) sans prix.").format(missing))
	if not doc.schedule_date:
		reasons.append(_("La date de réception prévue manque."))
	elif getdate(doc.schedule_date) < getdate(doc.transaction_date):
		reasons.append(_("La réception prévue précède la date de commande."))
	return reasons


def actions(doc):
	"""Ce que cette personne peut faire sur cette commande, maintenant. Le serveur reste seul juge à l'exécution."""
	found = []
	if doc.docstatus == 0:
		if doc.has_permission("write"):
			found.append("modifier")
		if doc.has_permission("submit"):
			found.append("valider")
		if doc.has_permission("delete"):
			found.append("supprimer")
		return found
	if doc.docstatus != 1:
		return found
	active = doc.status not in ("On Hold", "Closed", "Completed", "Delivered")
	if active and flt(doc.per_received) < 100 and frappe.has_permission(RECEPTION, "create"):
		found.append("reception")
	if active and flt(doc.per_billed) < 100 and frappe.has_permission(FACTURE_ACHAT, "create"):
		found.append("facture")
	if doc.has_permission("submit"):
		if doc.status in EN_COURS:
			found.extend(["attente", "cloturer"])
		elif doc.status == "On Hold":
			found.append("reprendre")
		elif doc.status == "Closed":
			found.append("rouvrir")
	if doc.has_permission("cancel") and doc.status not in ("Closed", "Completed"):
		found.append("annuler")
	return found


def _line(item):
	return {
		"name": item.name,
		"article": item.item_code,
		"designation": item.item_name or item.item_code,
		"description": line_description(item),
		"quantite": flt(item.qty),
		"recu": flt(item.received_qty),
		"unite": item.uom,
		"prix": flt(item.rate),
		"prix_tarif": flt(item.price_list_rate),
		"montant": flt(item.amount),
		"facture": flt(item.billed_amt),
		"reception": _day(item.schedule_date),
		"depot": item.warehouse,
		"devis": item.supplier_quotation or None,
	}


def _commande_payload(doc):
	allowed = actions(doc)
	devis = []
	for item in doc.items:
		if item.supplier_quotation and item.supplier_quotation not in devis:
			devis.append(item.supplier_quotation)
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"status": _status(doc),
		"docstatus": cint(doc.docstatus),
		"fournisseur": doc.supplier,
		"fournisseur_label": doc.supplier_name or doc.supplier,
		"date": _day(doc.transaction_date),
		"reception": _day(doc.schedule_date),
		"depot": doc.set_warehouse or None,
		"cree_par": get_fullname(doc.owner),
		"devise": doc.currency,
		"taxes_modele": doc.taxes_and_charges,
		"lignes": [_line(item) for item in doc.items],
		"taxes": tax_lines(doc),
		"total": flt(doc.net_total),
		"total_taxes": flt(doc.total_taxes_and_charges),
		"total_ttc": flt(doc.grand_total),
		"arrondi": flt(doc.rounded_total) or None,
		"en_lettres": doc.in_words or None,
		"recu": flt(doc.per_received, 1),
		"facture": flt(doc.per_billed, 1),
		"devis": devis,
		"receptions": _suivantes(RECEPTION, "Purchase Receipt Item", doc.name),
		"factures": _suivantes(FACTURE_ACHAT, "Purchase Invoice Item", doc.name),
		"actions": allowed,
		"blocked": blocked(doc) if "valider" in allowed else [],
		"can_print": bool(doc.has_permission("print")),
		"comments": activity.comment_summary(COMMANDE_ACHAT, doc.name),
	}


@frappe.whitelist()
def get_commande_achat(name):
	require_bureau()
	doc = frappe.get_doc(COMMANDE_ACHAT, name)
	doc.check_permission("read")
	return _commande_payload(doc)


def _load(name, modified):
	require_bureau()
	doc = frappe.get_doc(COMMANDE_ACHAT, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Cette commande vient d'être modifiée par ailleurs. Elle a été rechargée : vérifiez-la, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	return doc


def _for_work(name, modified, action):
	"""La commande à modifier : l'action doit être permise, et l'écran à jour."""
	doc = _load(name, modified)
	if action not in actions(doc):
		frappe.throw(_("Cette action n'est pas possible sur cette commande."), frappe.PermissionError)
	return doc


def _check_reception(reception, date):
	if not reception:
		frappe.throw(_("La date de réception prévue est obligatoire."))
	if getdate(reception) < getdate(date):
		frappe.throw(_("La réception prévue ne peut pas précéder la date de commande."))
	return getdate(reception)


def _default_warehouse():
	"""Le dépôt de réception par défaut des réglages de stock, s'il reçoit du stock (pas un groupe)."""
	warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
	if warehouse and not frappe.db.get_value("Warehouse", warehouse, "is_group"):
		return warehouse
	return None


@frappe.whitelist(methods=["POST"])
def create_commande_achat(values=None):
	"""Crée une commande d'achat en brouillon, sans devis : fournisseur, réception prévue, TVA et lignes."""
	require_bureau()
	frappe.has_permission(COMMANDE_ACHAT, "create", throw=True)
	values = _parse(values) or {}
	fournisseur = check_supplier(values.get("fournisseur"))
	lignes = clean_lines(values.get("lignes"))
	date = today()
	reception = _check_reception(values.get("reception"), date)
	doc = frappe.new_doc(COMMANDE_ACHAT)
	doc.update(
		{
			"supplier": fournisseur,
			"company": _company(),
			"transaction_date": date,
			"schedule_date": reception,
			"buying_price_list": buying_price_list(),
			"set_warehouse": _default_warehouse(),
		}
	)
	set_lines(doc, lignes, schedule_date=reception)
	set_purchase_taxes(doc, cstr(values.get("taxes")).strip())
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_commande_achat(name, modified, values=None):
	"""Brouillon seulement : lignes, réception prévue et TVA. Les champs absents ne changent pas."""
	doc = _for_work(name, modified, "modifier")
	values = _parse(values) or {}
	if "reception" in values:
		doc.schedule_date = _check_reception(values["reception"], doc.transaction_date)
		for item in doc.items:
			item.schedule_date = doc.schedule_date
	if "lignes" in values:
		if any(item.supplier_quotation for item in doc.items):
			frappe.throw(
				_(
					"Les lignes reprises d'un devis fournisseur se modifient sur le Desk, pour garder le lien au devis."
				)
			)
		set_lines(doc, clean_lines(values["lignes"]), schedule_date=doc.schedule_date)
	if "taxes" in values:
		set_purchase_taxes(doc, cstr(values["taxes"]).strip())
	doc.save()
	return _commande_payload(doc)


@frappe.whitelist(methods=["POST"])
def validate_commande_achat(name, modified):
	"""Soumet la commande : elle ne se modifie plus et attend sa réception."""
	doc = _for_work(name, modified, "valider")
	reasons = blocked(doc)
	if reasons:
		frappe.throw(" ".join(reasons))
	doc.submit()
	return _commande_payload(doc)


@frappe.whitelist(methods=["POST"])
def cancel_commande_achat(name, modified):
	doc = _for_work(name, modified, "annuler")
	doc.cancel()
	return _commande_payload(doc)


@frappe.whitelist(methods=["POST"])
def delete_commande_achat(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(COMMANDE_ACHAT, doc.name)
	return {"deleted": doc.name}


# Action du bureau → statut passé à `PurchaseOrder.update_status`, comme les boutons du Desk.
STATUS_ACTIONS = {"attente": "On Hold", "reprendre": "Draft", "cloturer": "Closed", "rouvrir": "Draft"}


@frappe.whitelist(methods=["POST"])
def set_commande_achat_status(name, modified, action):
	"""Mettre en attente, reprendre, clôturer ou rouvrir. « Draft » recalcule le statut d'après réceptions et factures."""
	if action not in STATUS_ACTIONS:
		frappe.throw(_("Action inconnue."))
	doc = _for_work(name, modified, action)
	doc.update_status(STATUS_ACTIONS[action])
	return _commande_payload(frappe.get_doc(COMMANDE_ACHAT, doc.name))


@frappe.whitelist(methods=["POST"])
def create_suivante(name, modified, kind):
	"""Réception ou facture d'achat en brouillon, des quantités restantes, par les outils standard d'ERPNext."""
	from erpnext.buying.doctype.purchase_order.purchase_order import (
		make_purchase_invoice,
		make_purchase_receipt,
	)

	if kind not in ("reception", "facture"):
		frappe.throw(_("Pièce inconnue."))
	doc = _for_work(name, modified, kind)
	target = make_purchase_receipt(doc.name) if kind == "reception" else make_purchase_invoice(doc.name)
	if not target.get("items"):
		frappe.throw(
			_("Il ne reste rien à recevoir.") if kind == "reception" else _("Il ne reste rien à facturer.")
		)
	note = replace_disabled_taxes(target)
	drop_invoice_batches(target)
	target.insert()
	return {
		"doctype": target.doctype,
		"note": note,
		"name": target.name,
		"commande": _commande_payload(frappe.get_doc(COMMANDE_ACHAT, doc.name)),
	}


def commande_achat_for_bulk(name, modified):
	"""Commande d'une action groupée ou d'un tag : lisible, et dans la version affichée à l'écran."""
	return _load(name, modified)


def bulk_guard(doc, operation):
	"""Une commande validée ne se modifie ni ne se supprime en groupe : elle passe par sa fiche."""
	if doc.docstatus != 0:
		return _("Commande validée ou annulée : elle ne change plus.")
	return None


def _check_activity(name):
	require_bureau()
	frappe.get_doc(COMMANDE_ACHAT, name).check_permission("read")


@frappe.whitelist()
def get_commande_achat_activity(name):
	require_bureau()
	return activity.get_feed(COMMANDE_ACHAT, name)


@frappe.whitelist(methods=["POST"])
def add_commande_achat_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(COMMANDE_ACHAT, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_commande_achat_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(COMMANDE_ACHAT, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_commande_achat_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(COMMANDE_ACHAT, name, comment)
