# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Devis du poste de bureau (/bureau/devis) : liste, aperçu, fiche, création et cycle.

Le devis Unicare est le Quotation standard d'ERPNext, sans circuit amont : il se crée ici avec son client, ses lignes
(article, quantité, prix prérempli du tarif de vente) et son modèle de TVA. Un brouillon se modifie, se valide ou
s'annule ; un devis validé donne sa commande client ou se déclare perdu. Chaque écriture passe par `insert`, `save`,
`submit` ou `cancel` pour garder les règles d'ERPNext, et reçoit la date `modified` affichée à l'écran.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, cstr, flt, get_fullname, getdate, today

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
from unicare.api.bureau_versions import amend, cancelled_actions, versions

DEVIS = "Quotation"
LIGNES = "Quotation Item"
COMMANDE = "Sales Order"
CUSTOMER = "Customer"
TAXES = "Sales Taxes and Charges Template"
LOST_REASON = "Quotation Lost Reason"

OUVERTS = ("Open", "Replied", "Partially Ordered")
CLOS = ("Lost", "Expired", "Cancelled")
EXPIRE_SOUS = 7
VALIDITE_PAR_DEFAUT = 30
LIGNES_MAX = 200
ARTICLE_SEARCH_LIMIT = 12

FIELDS = [
	"name",
	"modified",
	"creation",
	"owner",
	"status",
	"docstatus",
	"party_name",
	"customer_name",
	"transaction_date",
	"valid_till",
	"net_total",
	"grand_total",
	"currency",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "brouillons", "ouverts", "expirent", "commandes", "clos")
SORT_KEYS = {
	"name",
	"client_label",
	"date",
	"valable",
	"status",
	"total",
	"total_ttc",
	"lignes",
	"creation",
	"modified",
}


def _day(value):
	return str(value) if value else None


def _status(row):
	"""Un brouillon s'affiche « Draft » quel que soit le statut calculé par ERPNext."""
	return "Draft" if cint(row.get("docstatus")) == 0 else row.get("status")


def line_description(item):
	"""La description d'une ligne, en texte, quand elle dit autre chose que la désignation. ERPNext la stocke en HTML."""
	from frappe.utils import strip_html

	text = strip_html(cstr(item.description)).strip()
	return None if text in ("", cstr(item.item_name).strip()) else text


def tax_lines(doc):
	"""Les taxes d'une pièce telles qu'affichées : une seule ligne « TVA », quel que soit le modèle ou le taux.

	Le droit de timbre (compte du barème algérien) reste à part, sous son propre libellé.
	"""
	from unicare.setup.algeria import bareme_timbre, get_account

	timbre = get_account(doc.company, bareme_timbre()["compte"]) if doc.get("company") else None
	tva = 0
	lines = []
	for row in doc.get("taxes") or []:
		if timbre and row.account_head == timbre:
			lines.append({"description": row.description or _("Droit de timbre"), "montant": flt(row.tax_amount)})
		else:
			tva += flt(row.tax_amount)
	if doc.get("taxes") and (tva or not lines):
		lines.insert(0, {"description": _("TVA"), "montant": flt(tva, 2)})
	return lines


def in_view(view, row, current_day=None):
	if view == "all":
		return True
	status = row["status"]
	if view == "brouillons":
		return status == "Draft"
	if view == "ouverts":
		return status in OUVERTS
	if view == "expirent":
		day = getdate(current_day or today())
		valable = row.get("valable")
		return status in OUVERTS and bool(valable) and day <= getdate(valable) <= add_days(day, EXPIRE_SOUS)
	if view == "commandes":
		return status == "Ordered"
	return status in CLOS


def _lines_by_devis(names):
	"""Articles de chaque devis lisible, dans l'ordre des lignes, pour la colonne « Articles »."""
	if not names:
		return {}
	rows = frappe.get_all(
		LIGNES,
		filters={"parent": ["in", names], "parenttype": DEVIS},
		fields=["parent", "item_name", "item_code"],
		order_by="idx asc",
	)
	lines = {}
	for row in rows:
		lines.setdefault(row.parent, []).append(row.item_name or row.item_code)
	return lines


def _list_row(devis, lines):
	articles = lines.get(devis.name, [])
	return {
		"name": devis.name,
		"modified": devis.modified,
		"creation": str(devis.creation),
		"tags": row_tags(devis),
		"cloche": row_bell(devis),
		"client": devis.party_name,
		"client_label": devis.customer_name or devis.party_name,
		"date": _day(devis.transaction_date),
		"valable": _day(devis.valid_till),
		"status": _status(devis),
		"total": flt(devis.net_total),
		"total_ttc": flt(devis.grand_total),
		"lignes": len(articles),
		"articles": ", ".join(articles[:3]) + (f" (+{len(articles) - 3})" if len(articles) > 3 else ""),
	}


def order_devis(rows, sort=None, direction=None):
	"""Les plus récents d'abord, ou par la colonne demandée. Une ligne sans valeur reste à la fin."""
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
def get_devis_list(
	view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None
):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), DEVIS)
	devis = frappe.get_list(
		DEVIS,
		filters=[["quotation_to", "=", CUSTOMER], *conditions],
		distinct=has_child_filter(conditions, DEVIS),
		or_filters=[
			["name", "like", pattern],
			["customer_name", "like", pattern],
			["party_name", "like", pattern],
		]
		if value
		else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	lines = _lines_by_devis([row.name for row in devis])
	rows = [_list_row(row, lines) for row in devis]
	current_day = today()
	counts = {name: sum(1 for row in rows if in_view(name, row, current_day)) for name in VIEWS}
	ordered = order_devis([row for row in rows if in_view(view, row, current_day)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"devis": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


def _company():
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)


def _price_list():
	return frappe.db.get_single_value("Selling Settings", "selling_price_list") or frappe.db.get_value(
		"Price List", {"selling": 1, "enabled": 1}, "name"
	)


def _taxes_templates():
	return frappe.get_all(
		TAXES,
		filters={"company": _company(), "disabled": 0},
		fields=["name", "title", "is_default"],
		order_by="is_default desc, title asc",
	)


@frappe.whitelist()
def get_devis_options():
	"""Valeurs proposées dans les filtres et dans la fenêtre du devis."""
	require_bureau()
	templates = _taxes_templates()
	return {
		"taxes": [{"value": row.name, "label": row.title or row.name} for row in templates],
		"taxes_defaut": next((row.name for row in templates if row.is_default), None),
		"validite_jours": VALIDITE_PAR_DEFAUT,
		"liste_prix": _price_list(),
		"filter_fields": doctype_filter_fields(DEVIS),
	}


def _prices(item_codes):
	"""Prix de vente du tarif par défaut. Un article sans prix part à zéro : la validation le refusera."""
	price_list = _price_list()
	if not item_codes or not price_list:
		return {}
	rows = frappe.get_all(
		"Item Price",
		filters={"price_list": price_list, "item_code": ["in", item_codes], "selling": 1},
		fields=["item_code", "price_list_rate", "uom"],
		order_by="valid_from desc",
	)
	prices = {}
	for row in rows:
		prices.setdefault(row.item_code, flt(row.price_list_rate))
	return prices


def article_search(search, flag, prices_of, limit=ARTICLE_SEARCH_LIMIT):
	"""Articles actifs marqués `flag` (vente ou achat), avec unité, prix (`prices_of`) et stock des dépôts.

	Chaque mot tapé doit se trouver dans la désignation ou le code, dans n'importe quel ordre et sans tenir compte des
	accents (« 250 bouteille » trouve « Bouteille … 250 Ml »). Le stock n'est envoyé qu'à qui lit les quantités par dépôt.
	"""
	import unicodedata

	words = cstr(search).split()

	def plain(text):
		return "".join(c for c in unicodedata.normalize("NFD", cstr(text).casefold()) if unicodedata.category(c) != "Mn")

	first = words[0] if words else ""
	items = frappe.get_list(
		"Item",
		filters={"disabled": 0, flag: 1, "has_variants": 0},
		or_filters=[["item_name", "like", f"%{first}%"], ["name", "like", f"%{first}%"]] if first else None,
		fields=["name", "item_name", "stock_uom", "item_group", "is_stock_item"],
		order_by="item_name asc",
		limit_page_length=200 if len(words) > 1 else limit,
	)
	wanted = [plain(word) for word in words]
	items = [item for item in items if all(word in plain(f"{item.item_name} {item.name}") for word in wanted)][:limit]
	prices = prices_of([item.name for item in items])
	stock_lisible = bool(frappe.has_permission("Bin", "read"))
	stocks = {}
	if items and stock_lisible:
		from unicare.api.bureau_stock import depots

		for row in frappe.get_all(
			"Bin",
			filters={"item_code": ["in", [item.name for item in items]], "warehouse": ["in", depots() or [""]]},
			fields=["item_code", "actual_qty"],
		):
			stocks[row.item_code] = stocks.get(row.item_code, 0) + flt(row.actual_qty)
	return [
		{
			"name": item.name,
			"label": item.item_name or item.name,
			"uom": item.stock_uom,
			"prix": prices.get(item.name),
			"groupe": item.item_group,
			# null : article non stocké (service), ou stock non lisible pour ce rôle.
			"stock": flt(stocks.get(item.name, 0), 3) if cint(item.is_stock_item) and stock_lisible else None,
		}
		for item in items
	]


@frappe.whitelist()
def search_devis_articles(search=None):
	"""Articles vendables actifs, avec leur unité, leur prix de vente du tarif par défaut et leur stock."""
	require_bureau()
	return article_search(search, "is_sales_item", _prices)


def blocked(doc):
	"""Ce qui empêche de valider : aucune ligne, une ligne sans prix, une validité manquante ou passée."""
	reasons = []
	if not doc.items:
		reasons.append(_("Le devis n'a aucune ligne."))
	missing = sum(1 for item in doc.items if flt(item.rate) <= 0)
	if missing:
		reasons.append(_("{0} ligne(s) sans prix.").format(missing))
	if not doc.valid_till:
		reasons.append(_("La date de validité manque."))
	elif getdate(doc.valid_till) < getdate(today()):
		reasons.append(_("La date de validité est passée."))
	return reasons


def _commandes(doc):
	"""Commandes faites depuis ce devis, par leurs lignes (`prevdoc_docname`), comme le tableau de bord du Desk."""
	if not frappe.has_permission(COMMANDE, "read"):
		return None
	rows = frappe.get_list(
		COMMANDE,
		filters=[["Sales Order Item", "prevdoc_docname", "=", doc.name], [COMMANDE, "docstatus", "<", 2]],
		fields=["name", "status", "docstatus", "transaction_date", "delivery_date", "grand_total"],
		order_by=f"`tab{COMMANDE}`.transaction_date desc",
		distinct=True,
	)
	return [
		{
			"name": row.name,
			"status": _status(row),
			"date": _day(row.transaction_date),
			"livraison": _day(row.delivery_date),
			"total": flt(row.grand_total),
		}
		for row in rows
	]


def actions(doc):
	"""Ce que cette personne peut faire sur ce devis, maintenant. Le serveur reste seul juge à l'exécution."""
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
	elif doc.docstatus == 1:
		if doc.status in OUVERTS and frappe.has_permission(COMMANDE, "create"):
			found.append("commande")
		if doc.status in ("Open", "Replied", "Expired") and doc.has_permission("write"):
			found.append("perdu")
		if doc.status not in ("Ordered", "Partially Ordered") and doc.has_permission("cancel"):
			found.append("annuler")
	return found


def _line(item):
	return {
		"name": item.name,
		"article": item.item_code,
		"designation": item.item_name or item.item_code,
		"description": line_description(item),
		"quantite": flt(item.qty),
		"unite": item.uom,
		"prix": flt(item.rate),
		"prix_tarif": flt(item.price_list_rate),
		"remise": flt(item.discount_percentage),
		"montant": flt(item.amount),
	}


def _lost(doc):
	if doc.status != "Lost":
		return None
	return {
		"raisons": [row.lost_reason for row in doc.get("lost_reasons") or []],
		"precisions": doc.get("order_lost_reason") or None,
	}


def _devis_payload(doc):
	allowed = actions(doc)
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"status": _status(doc),
		"docstatus": cint(doc.docstatus),
		"client": doc.party_name,
		"client_label": doc.customer_name or doc.party_name,
		"date": _day(doc.transaction_date),
		"valable": _day(doc.valid_till),
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
		"commandes": _commandes(doc),
		"version_de": doc.get("amended_from") or None,
		"versions": versions(doc),
		"actions": allowed,
		"blocked": blocked(doc) if "valider" in allowed else [],
		"raisons_perte": frappe.get_all(LOST_REASON, pluck="name", order_by="name asc")
		if "perdu" in allowed
		else [],
		"perte": _lost(doc),
		"can_print": bool(doc.has_permission("print")),
		"comments": activity.comment_summary(DEVIS, doc.name),
	}


@frappe.whitelist()
def get_devis(name):
	require_bureau()
	doc = frappe.get_doc(DEVIS, name)
	doc.check_permission("read")
	return _devis_payload(doc)


def _for_work(name, modified, action):
	"""Le devis à modifier : l'action doit être permise, et l'écran à jour."""
	require_bureau()
	doc = frappe.get_doc(DEVIS, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Ce devis vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	if action not in actions(doc):
		frappe.throw(_("Cette action n'est pas possible sur ce devis."), frappe.PermissionError)
	return doc


def _clean_lines(lignes):
	"""Lignes saisies → [(article, quantité, prix)]. Une ligne sans article est ignorée ; le reste doit être lisible."""
	lignes = _parse(lignes) or []
	if not isinstance(lignes, list):
		frappe.throw(_("Lignes illisibles."))
	if len(lignes) > LIGNES_MAX:
		frappe.throw(_("Un devis compte au plus {0} lignes.").format(LIGNES_MAX))
	cleaned = []
	for ligne in lignes:
		article = cstr((ligne or {}).get("article")).strip()
		if not article:
			continue
		if not frappe.db.exists("Item", {"name": article, "disabled": 0, "is_sales_item": 1}):
			frappe.throw(_("L'article {0} n'est pas un article vendable actif.").format(article))
		quantite = flt(ligne.get("quantite"))
		if quantite <= 0:
			frappe.throw(_("La quantité de {0} doit être positive.").format(article))
		prix = ligne.get("prix")
		if prix not in (None, "") and flt(prix) < 0:
			frappe.throw(_("Le prix de {0} ne peut pas être négatif.").format(article))
		cleaned.append((article, quantite, None if prix in (None, "") else flt(prix)))
	if not cleaned:
		frappe.throw(_("Ajoutez au moins une ligne."))
	return cleaned


def _set_lines(doc, lignes):
	"""Remplace les lignes. Un prix vide reprend celui du tarif ; un prix saisi l'emporte."""
	prices = _prices([article for article, _quantite, _prix in lignes])
	doc.set("items", [])
	for article, quantite, prix in lignes:
		rate = prices.get(article, 0) if prix is None else prix
		doc.append(
			"items",
			{"item_code": article, "qty": quantite, "rate": rate, "price_list_rate": prices.get(article, 0)},
		)


def _set_taxes(doc, template):
	"""Le modèle de TVA et ses lignes, comme le fait le formulaire du Desk au choix du modèle."""
	from erpnext.controllers.accounts_controller import get_taxes_and_charges

	if template and not frappe.db.exists(TAXES, {"name": template, "company": doc.company, "disabled": 0}):
		frappe.throw(_("Choisissez un modèle de TVA de la liste."))
	doc.taxes_and_charges = template or None
	doc.set("taxes", get_taxes_and_charges(TAXES, template) or [] if template else [])


def _check_validity(valable, date):
	if not valable:
		frappe.throw(_("La date de validité est obligatoire."))
	if getdate(valable) < getdate(date):
		frappe.throw(_("La validité ne peut pas précéder la date du devis."))
	return getdate(valable)


@frappe.whitelist(methods=["POST"])
def create_devis(values=None):
	"""Crée un devis en brouillon : client, validité, TVA et lignes."""
	require_bureau()
	frappe.has_permission(DEVIS, "create", throw=True)
	values = _parse(values) or {}
	client = cstr(values.get("client")).strip()
	if not client:
		frappe.throw(_("Choisissez le client."))
	frappe.get_doc(CUSTOMER, client).check_permission("read")
	if frappe.db.get_value(CUSTOMER, client, "disabled"):
		frappe.throw(_("Ce client est désactivé."))
	lignes = _clean_lines(values.get("lignes"))
	date = today()
	doc = frappe.new_doc(DEVIS)
	doc.update(
		{
			"quotation_to": CUSTOMER,
			"party_name": client,
			"company": _company(),
			"transaction_date": date,
			"valid_till": _check_validity(values.get("valable"), date),
			"selling_price_list": _price_list(),
			"order_type": "Sales",
		}
	)
	_set_lines(doc, lignes)
	_set_taxes(doc, cstr(values.get("taxes")).strip())
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_devis(name, modified, values=None):
	"""Brouillon seulement : lignes, validité et TVA. Les champs absents ne changent pas."""
	doc = _for_work(name, modified, "modifier")
	values = _parse(values) or {}
	if "lignes" in values:
		_set_lines(doc, _clean_lines(values["lignes"]))
	if "valable" in values:
		doc.valid_till = _check_validity(values["valable"], doc.transaction_date)
	if "taxes" in values:
		_set_taxes(doc, cstr(values["taxes"]).strip())
	doc.save()
	return _devis_payload(doc)


@frappe.whitelist(methods=["POST"])
def validate_devis(name, modified):
	"""Soumet le devis : il ne se modifie plus."""
	doc = _for_work(name, modified, "valider")
	reasons = blocked(doc)
	if reasons:
		frappe.throw(" ".join(reasons))
	doc.submit()
	return _devis_payload(doc)


@frappe.whitelist(methods=["POST"])
def cancel_devis(name, modified):
	doc = _for_work(name, modified, "annuler")
	doc.cancel()
	return _devis_payload(doc)


@frappe.whitelist(methods=["POST"])
def delete_devis(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(DEVIS, doc.name)
	return {"deleted": doc.name}


@frappe.whitelist(methods=["POST"])
def create_version(name, modified):
	"""Nouvelle version (brouillon `NOM-1`) d'une pièce annulée, comme « Modifier » sur le Desk."""
	doc = _for_work(name, modified, "nouvelle_version")
	return amend(doc)


@frappe.whitelist(methods=["POST"])
def mark_lost(name, modified, raison, precisions=None):
	"""Perdu, avec sa raison, comme le bouton du Desk."""
	doc = _for_work(name, modified, "perdu")
	raison = cstr(raison).strip()
	if not raison or not frappe.db.exists(LOST_REASON, raison):
		frappe.throw(_("Choisissez une raison de perte."))
	doc.declare_enquiry_lost([{"lost_reason": raison}], [], cstr(precisions).strip() or None)
	return _devis_payload(frappe.get_doc(DEVIS, doc.name))


@frappe.whitelist(methods=["POST"])
def create_commande(name, modified, livraison):
	"""Commande client en brouillon, des quantités restant à commander, par l'outil standard d'ERPNext."""
	from erpnext.selling.doctype.quotation.quotation import make_sales_order

	doc = _for_work(name, modified, "commande")
	if not livraison:
		frappe.throw(_("Choisissez la date de livraison."))
	if getdate(livraison) < getdate(today()):
		frappe.throw(_("La date de livraison ne peut pas être passée."))
	frappe.has_permission(COMMANDE, "create", throw=True)
	commande = make_sales_order(doc.name)
	commande.transaction_date = today()
	commande.delivery_date = getdate(livraison)
	for item in commande.items:
		item.delivery_date = commande.delivery_date
	commande.insert()
	return {"commande": commande.name, "devis": _devis_payload(frappe.get_doc(DEVIS, doc.name))}


def devis_for_bulk(name, modified):
	"""Devis d'une action groupée ou d'un tag : lisible, et dans la version affichée à l'écran."""
	require_bureau()
	doc = frappe.get_doc(DEVIS, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Ce devis vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	return doc


def bulk_guard(doc, operation):
	"""Un devis validé ne se modifie ni ne se supprime en groupe : il passe par sa fiche (perdu, annuler)."""
	# Une pièce annulée peut se supprimer en groupe ; seuls les brouillons se modifient.
	if doc.docstatus != 0 and not (operation == "delete" and doc.docstatus == 2):
		return _("Devis validé ou annulé : il ne change plus.")
	return None


def _check_activity(name):
	require_bureau()
	frappe.get_doc(DEVIS, name).check_permission("read")


@frappe.whitelist()
def get_devis_activity(name):
	require_bureau()
	return activity.get_feed(DEVIS, name)


@frappe.whitelist(methods=["POST"])
def add_devis_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(DEVIS, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_devis_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(DEVIS, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_devis_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(DEVIS, name, comment)
