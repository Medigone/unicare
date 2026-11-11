# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Commandes client du poste de bureau (/bureau/commandes) : liste, aperçu, fiche, création et cycle.

La commande Unicare est le Sales Order standard d'ERPNext. Elle naît d'un devis (`bureau_devis.create_commande`) ou
se crée ici directement : client, date de livraison, TVA et lignes, au prix du tarif de vente. Un brouillon se
modifie, se valide ou se supprime ; une commande validée donne ses bons de livraison et ses factures (en brouillon,
par les outils d'ERPNext), se met en attente, se clôture ou s'annule. Les règles restent celles d'ERPNext : chaque
écriture passe par `insert`, `save`, `submit`, `cancel` ou `update_status`, avec la date `modified` affichée à l'écran.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_fullname, getdate, today

from unicare.api import activity
from unicare.api.bureau_devis import (
	CUSTOMER,
	TAXES,
	_clean_lines,
	_company,
	_day,
	_price_list,
	_prices,
	_status,
	_taxes_templates,
	line_description,
	tax_lines,
)
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

COMMANDE = "Sales Order"
LIGNES = "Sales Order Item"
LIVRAISON = "Delivery Note"
FACTURE = "Sales Invoice"

A_LIVRER = ("To Deliver and Bill", "To Deliver")
A_FACTURER = ("To Deliver and Bill", "To Bill")
EN_COURS = ("To Deliver and Bill", "To Deliver", "To Bill")
CLOS = ("Completed", "Closed", "Cancelled")

FIELDS = [
	"name",
	"modified",
	"creation",
	"owner",
	"status",
	"docstatus",
	"customer",
	"customer_name",
	"transaction_date",
	"delivery_date",
	"po_no",
	"net_total",
	"grand_total",
	"per_delivered",
	"per_billed",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "brouillons", "a_livrer", "a_facturer", "en_retard", "en_attente", "clos")
SORT_KEYS = {
	"name",
	"client_label",
	"date",
	"livraison",
	"status",
	"total",
	"total_ttc",
	"livre",
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
	if view == "a_livrer":
		return status in A_LIVRER
	if view == "a_facturer":
		return status in A_FACTURER
	if view == "en_retard":
		livraison = row.get("livraison")
		return status in A_LIVRER and bool(livraison) and getdate(livraison) < getdate(current_day or today())
	if view == "en_attente":
		return status == "On Hold"
	return status in CLOS


def _lines_by_commande(names):
	"""Articles et devis d'origine de chaque commande lisible, dans l'ordre des lignes."""
	if not names:
		return {}
	rows = frappe.get_all(
		LIGNES,
		filters={"parent": ["in", names], "parenttype": COMMANDE},
		fields=["parent", "item_name", "item_code", "prevdoc_docname"],
		order_by="idx asc",
	)
	lines = {}
	for row in rows:
		entry = lines.setdefault(row.parent, {"articles": [], "devis": []})
		entry["articles"].append(row.item_name or row.item_code)
		if row.prevdoc_docname and row.prevdoc_docname not in entry["devis"]:
			entry["devis"].append(row.prevdoc_docname)
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
		"client": commande.customer,
		"client_label": commande.customer_name or commande.customer,
		"date": _day(commande.transaction_date),
		"livraison": _day(commande.delivery_date),
		"status": _status(commande),
		"total": flt(commande.net_total),
		"total_ttc": flt(commande.grand_total),
		"livre": flt(commande.per_delivered, 1),
		"facture": flt(commande.per_billed, 1),
		"reference": commande.po_no or None,
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
def get_commandes(
	view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None
):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), COMMANDE)
	commandes = frappe.get_list(
		COMMANDE,
		filters=conditions,
		distinct=has_child_filter(conditions, COMMANDE),
		or_filters=[
			["name", "like", pattern],
			["customer_name", "like", pattern],
			["customer", "like", pattern],
			["po_no", "like", pattern],
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
def get_commande_options():
	"""Valeurs proposées dans les filtres et dans la fenêtre de la commande."""
	require_bureau()
	templates = _taxes_templates()
	return {
		"taxes": [{"value": row.name, "label": row.title or row.name} for row in templates],
		"taxes_defaut": next((row.name for row in templates if row.is_default), None),
		"liste_prix": _price_list(),
		"filter_fields": doctype_filter_fields(COMMANDE),
	}


def _suivantes(doctype, child, link_field, name):
	"""Bons de livraison ou factures faits depuis cette commande, par leurs lignes. `None` sans droit de lecture."""
	if not frappe.has_permission(doctype, "read"):
		return None
	rows = frappe.get_list(
		doctype,
		filters=[[child, link_field, "=", name], [doctype, "docstatus", "<", 2]],
		fields=["name", "status", "docstatus", "posting_date", "grand_total"],
		order_by=f"`tab{doctype}`.posting_date desc",
		distinct=True,
	)
	return [
		{
			"name": row.name,
			"status": _status(row),
			"date": _day(row.posting_date),
			"total": flt(row.grand_total),
		}
		for row in rows
	]


def blocked(doc):
	"""Ce qui empêche de valider : aucune ligne, une ligne sans prix, une date de livraison manquante ou passée."""
	reasons = []
	if not doc.items:
		reasons.append(_("La commande n'a aucune ligne."))
	missing = sum(1 for item in doc.items if flt(item.rate) <= 0)
	if missing:
		reasons.append(_("{0} ligne(s) sans prix.").format(missing))
	if not doc.delivery_date:
		reasons.append(_("La date de livraison manque."))
	elif getdate(doc.delivery_date) < getdate(doc.transaction_date):
		reasons.append(_("La date de livraison précède la date de commande."))
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
	active = doc.status not in ("On Hold", "Closed", "Completed")
	if active and flt(doc.per_delivered) < 100 and frappe.has_permission(LIVRAISON, "create"):
		found.append("livraison")
	if active and flt(doc.per_billed) < 100 and frappe.has_permission(FACTURE, "create"):
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
		"livre": flt(item.delivered_qty),
		"unite": item.uom,
		"prix": flt(item.rate),
		"prix_tarif": flt(item.price_list_rate),
		"montant": flt(item.amount),
		"facture": flt(item.billed_amt),
		"livraison": _day(item.delivery_date),
		"depot": item.warehouse,
		"devis": item.prevdoc_docname or None,
	}


def _commande_payload(doc):
	allowed = actions(doc)
	devis = []
	for item in doc.items:
		if item.prevdoc_docname and item.prevdoc_docname not in devis:
			devis.append(item.prevdoc_docname)
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"status": _status(doc),
		"docstatus": cint(doc.docstatus),
		"client": doc.customer,
		"client_label": doc.customer_name or doc.customer,
		"date": _day(doc.transaction_date),
		"livraison": _day(doc.delivery_date),
		"reference": doc.po_no or None,
		"commune": doc.get("custom_nom_commune") or None,
		"wilaya": doc.get("custom_wilaya") or None,
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
		"livre": flt(doc.per_delivered, 1),
		"facture": flt(doc.per_billed, 1),
		"devis": devis,
		"livraisons": _suivantes(LIVRAISON, "Delivery Note Item", "against_sales_order", doc.name),
		"factures": _suivantes(FACTURE, "Sales Invoice Item", "sales_order", doc.name),
		"actions": allowed,
		"blocked": blocked(doc) if "valider" in allowed else [],
		"can_print": bool(doc.has_permission("print")),
		"comments": activity.comment_summary(COMMANDE, doc.name),
	}


@frappe.whitelist()
def get_commande(name):
	require_bureau()
	doc = frappe.get_doc(COMMANDE, name)
	doc.check_permission("read")
	return _commande_payload(doc)


def _for_work(name, modified, action):
	"""La commande à modifier : l'action doit être permise, et l'écran à jour."""
	require_bureau()
	doc = frappe.get_doc(COMMANDE, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Cette commande vient d'être modifiée par ailleurs. Elle a été rechargée : vérifiez-la, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	if action not in actions(doc):
		frappe.throw(_("Cette action n'est pas possible sur cette commande."), frappe.PermissionError)
	return doc


def _check_delivery(livraison, date):
	if not livraison:
		frappe.throw(_("La date de livraison est obligatoire."))
	if getdate(livraison) < getdate(date):
		frappe.throw(_("La date de livraison ne peut pas précéder la date de commande."))
	return getdate(livraison)


def _set_lines(doc, lignes):
	"""Remplace les lignes. Un prix vide reprend celui du tarif ; chaque ligne prend la date de livraison de la commande."""
	prices = _prices([article for article, _quantite, _prix in lignes])
	doc.set("items", [])
	for article, quantite, prix in lignes:
		doc.append(
			"items",
			{
				"item_code": article,
				"qty": quantite,
				"rate": prices.get(article, 0) if prix is None else prix,
				"price_list_rate": prices.get(article, 0),
				"delivery_date": doc.delivery_date,
			},
		)


def _set_taxes(doc, template):
	from erpnext.controllers.accounts_controller import get_taxes_and_charges

	if template and not frappe.db.exists(TAXES, {"name": template, "company": doc.company, "disabled": 0}):
		frappe.throw(_("Choisissez un modèle de TVA de la liste."))
	doc.taxes_and_charges = template or None
	doc.set("taxes", (get_taxes_and_charges(TAXES, template) or []) if template else [])


@frappe.whitelist(methods=["POST"])
def create_commande(values=None):
	"""Crée une commande en brouillon, sans devis : client, livraison, TVA et lignes."""
	require_bureau()
	frappe.has_permission(COMMANDE, "create", throw=True)
	values = _parse(values) or {}
	client = cstr(values.get("client")).strip()
	if not client:
		frappe.throw(_("Choisissez le client."))
	frappe.get_doc(CUSTOMER, client).check_permission("read")
	if frappe.db.get_value(CUSTOMER, client, "disabled"):
		frappe.throw(_("Ce client est désactivé."))
	lignes = _clean_lines(values.get("lignes"))
	date = today()
	doc = frappe.new_doc(COMMANDE)
	doc.update(
		{
			"customer": client,
			"company": _company(),
			"transaction_date": date,
			"delivery_date": _check_delivery(values.get("livraison"), date),
			"selling_price_list": _price_list(),
			"order_type": "Sales",
			"po_no": cstr(values.get("reference")).strip() or None,
		}
	)
	_set_lines(doc, lignes)
	_set_taxes(doc, cstr(values.get("taxes")).strip())
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_commande(name, modified, values=None):
	"""Brouillon seulement : lignes, livraison, TVA et référence client. Les champs absents ne changent pas."""
	doc = _for_work(name, modified, "modifier")
	values = _parse(values) or {}
	if "livraison" in values:
		doc.delivery_date = _check_delivery(values["livraison"], doc.transaction_date)
		for item in doc.items:
			item.delivery_date = doc.delivery_date
	if "lignes" in values:
		if any(item.prevdoc_docname for item in doc.items):
			frappe.throw(
				_("Les lignes reprises d'un devis se modifient sur le Desk, pour garder le lien au devis.")
			)
		_set_lines(doc, _clean_lines(values["lignes"]))
	if "taxes" in values:
		_set_taxes(doc, cstr(values["taxes"]).strip())
	if "reference" in values:
		doc.po_no = cstr(values["reference"]).strip() or None
	doc.save()
	return _commande_payload(doc)


@frappe.whitelist(methods=["POST"])
def validate_commande(name, modified):
	"""Soumet la commande : elle réserve le stock et ne se modifie plus."""
	doc = _for_work(name, modified, "valider")
	reasons = blocked(doc)
	if reasons:
		frappe.throw(" ".join(reasons))
	doc.submit()
	return _commande_payload(doc)


@frappe.whitelist(methods=["POST"])
def cancel_commande(name, modified):
	doc = _for_work(name, modified, "annuler")
	doc.cancel()
	return _commande_payload(doc)


@frappe.whitelist(methods=["POST"])
def delete_commande(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(COMMANDE, doc.name)
	return {"deleted": doc.name}


# Action du bureau → statut passé à `SalesOrder.update_status`, comme les boutons du Desk.
STATUS_ACTIONS = {"attente": "On Hold", "reprendre": "Draft", "cloturer": "Closed", "rouvrir": "Draft"}


@frappe.whitelist(methods=["POST"])
def set_commande_status(name, modified, action):
	"""Mettre en attente, reprendre, clôturer ou rouvrir. « Draft » recalcule le statut d'après livraisons et factures."""
	if action not in STATUS_ACTIONS:
		frappe.throw(_("Action inconnue."))
	doc = _for_work(name, modified, action)
	doc.update_status(STATUS_ACTIONS[action])
	return _commande_payload(frappe.get_doc(COMMANDE, doc.name))


@frappe.whitelist(methods=["POST"])
def create_suivante(name, modified, kind):
	"""Bon de livraison ou facture en brouillon, des quantités restantes, par les outils standard d'ERPNext."""
	from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, make_sales_invoice

	if kind not in ("livraison", "facture"):
		frappe.throw(_("Pièce inconnue."))
	doc = _for_work(name, modified, kind)
	target = make_delivery_note(doc.name) if kind == "livraison" else make_sales_invoice(doc.name)
	if not target.get("items"):
		frappe.throw(
			_("Il ne reste rien à livrer.") if kind == "livraison" else _("Il ne reste rien à facturer.")
		)
	target.insert()
	return {
		"doctype": target.doctype,
		"name": target.name,
		"commande": _commande_payload(frappe.get_doc(COMMANDE, doc.name)),
	}


def commande_for_bulk(name, modified):
	"""Commande d'une action groupée ou d'un tag : lisible, et dans la version affichée à l'écran."""
	require_bureau()
	doc = frappe.get_doc(COMMANDE, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Cette commande vient d'être modifiée par ailleurs. Elle a été rechargée : vérifiez-la, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	return doc


def bulk_guard(doc, operation):
	"""Une commande validée ne se modifie ni ne se supprime en groupe : elle passe par sa fiche."""
	if doc.docstatus != 0:
		return _("Commande validée ou annulée : elle ne change plus.")
	return None


def _check_activity(name):
	require_bureau()
	frappe.get_doc(COMMANDE, name).check_permission("read")


@frappe.whitelist()
def get_commande_activity(name):
	require_bureau()
	return activity.get_feed(COMMANDE, name)


@frappe.whitelist(methods=["POST"])
def add_commande_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(COMMANDE, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_commande_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(COMMANDE, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_commande_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(COMMANDE, name, comment)
