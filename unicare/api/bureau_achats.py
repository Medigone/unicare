# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Socle des pièces d'achat du poste de bureau : tarif d'achat, TVA déductible, lignes et fournisseur.

Le pendant, côté achats, des aides de `bureau_devis` pour les ventes. Les devis fournisseur et les commandes d'achat
s'en servent pour leur saisie ; les règles restent celles d'ERPNext (`insert`, `save`, `submit`).
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

from unicare.api.bureau_devis import LIGNES_MAX
from unicare.api.bureau_list import _parse
from unicare.api.bureau_postes import require_bureau

SUPPLIER = "Supplier"
TAXES_ACHAT = "Purchase Taxes and Charges Template"
ARTICLE_SEARCH_LIMIT = 12
EXCLU = "Exclu"


def buying_price_list():
	return frappe.db.get_single_value("Buying Settings", "buying_price_list") or frappe.db.get_value(
		"Price List", {"buying": 1, "enabled": 1}, "name"
	)


def buying_prices(item_codes):
	"""Prix d'achat du tarif par défaut, sinon le dernier prix d'achat de l'article. Sans l'un ni l'autre : absent."""
	if not item_codes:
		return {}
	prices = {}
	price_list = buying_price_list()
	if price_list:
		rows = frappe.get_all(
			"Item Price",
			filters={"price_list": price_list, "item_code": ["in", item_codes], "buying": 1},
			fields=["item_code", "price_list_rate"],
			order_by="valid_from desc",
		)
		for row in rows:
			prices.setdefault(row.item_code, flt(row.price_list_rate))
	missing = [code for code in item_codes if code not in prices]
	if missing:
		for row in frappe.get_all(
			"Item", filters={"name": ["in", missing]}, fields=["name", "last_purchase_rate"]
		):
			if flt(row.last_purchase_rate) > 0:
				prices[row.name] = flt(row.last_purchase_rate)
	return prices


def purchase_taxes_templates(company):
	return frappe.get_all(
		TAXES_ACHAT,
		filters={"company": company, "disabled": 0},
		fields=["name", "title", "is_default"],
		order_by="is_default desc, title asc",
	)


def taxes_options(company):
	"""Modèles de TVA déductible proposés dans les fenêtres, et celui choisi par défaut."""
	templates = purchase_taxes_templates(company)
	return {
		"taxes": [{"value": row.name, "label": row.title or row.name} for row in templates],
		"taxes_defaut": next((row.name for row in templates if row.is_default), None),
		"liste_prix": buying_price_list(),
	}


def set_purchase_taxes(doc, template):
	"""Le modèle de TVA d'achat et ses lignes, comme le formulaire du Desk au choix du modèle."""
	from erpnext.controllers.accounts_controller import get_taxes_and_charges

	if template and not frappe.db.exists(TAXES_ACHAT, {"name": template, "company": doc.company, "disabled": 0}):
		frappe.throw(_("Choisissez un modèle de TVA de la liste."))
	doc.taxes_and_charges = template or None
	doc.set("taxes", (get_taxes_and_charges(TAXES_ACHAT, template) or []) if template else [])


def replace_disabled_taxes(doc):
	"""Une pièce reprise d'une plus ancienne garde son modèle de TVA ; s'il a été désactivé depuis, ERPNext la refuse.

	Le modèle désactivé est remplacé par le modèle d'achat par défaut de la société (ou retiré s'il n'y en a pas), avec
	ses lignes. Renvoie le message à montrer, ou `None` si rien n'a changé.
	"""
	old = doc.get("taxes_and_charges")
	if not old or not frappe.db.get_value(TAXES_ACHAT, old, "disabled"):
		return None
	default = next((row.name for row in purchase_taxes_templates(doc.company) if row.is_default), None)
	set_purchase_taxes(doc, default)
	if default:
		return _("Le modèle de TVA « {0} » est désactivé : remplacé par « {1} ». Vérifiez la TVA avant de valider.").format(
			old, default
		)
	return _("Le modèle de TVA « {0} » est désactivé : la pièce est sans TVA. Choisissez la TVA avant de valider.").format(
		old
	)


def drop_invoice_batches(doc):
	"""Une facture d'achat qui ne mouvemente pas le stock n'a pas besoin du lot de ses lignes.

	ERPNext le recopie de la réception, puis refuse la facture si ce lot a expiré depuis. Le lot reste sur la
	réception et dans le stock ; seule la facture s'en passe.
	"""
	if doc.doctype != "Purchase Invoice" or cint(doc.get("update_stock")):
		return
	for row in doc.get("items") or []:
		row.batch_no = None
		row.serial_and_batch_bundle = None


def check_supplier(fournisseur):
	"""Le fournisseur d'une nouvelle pièce : lisible, actif et non exclu."""
	fournisseur = cstr(fournisseur).strip()
	if not fournisseur:
		frappe.throw(_("Choisissez le fournisseur."))
	frappe.get_doc(SUPPLIER, fournisseur).check_permission("read")
	disabled, statut = frappe.db.get_value(SUPPLIER, fournisseur, ["disabled", "custom_statut"])
	if disabled:
		frappe.throw(_("Ce fournisseur est désactivé."))
	if statut == EXCLU:
		frappe.throw(_("Ce fournisseur est exclu : on ne lui achète plus."))
	return fournisseur


def clean_lines(lignes):
	"""Lignes saisies → [(article, quantité, prix)]. Une ligne sans article est ignorée ; le reste doit être lisible."""
	lignes = _parse(lignes) or []
	if not isinstance(lignes, list):
		frappe.throw(_("Lignes illisibles."))
	if len(lignes) > LIGNES_MAX:
		frappe.throw(_("Une pièce compte au plus {0} lignes.").format(LIGNES_MAX))
	cleaned = []
	for ligne in lignes:
		article = cstr((ligne or {}).get("article")).strip()
		if not article:
			continue
		if not frappe.db.exists("Item", {"name": article, "disabled": 0, "is_purchase_item": 1}):
			frappe.throw(_("L'article {0} n'est pas un article d'achat actif.").format(article))
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


def set_lines(doc, lignes, **extra):
	"""Remplace les lignes. Un prix vide reprend le prix d'achat connu ; un prix saisi l'emporte.

	`extra` : champs posés sur chaque ligne (date de réception prévue d'une commande).
	"""
	prices = buying_prices([article for article, _quantite, _prix in lignes])
	doc.set("items", [])
	for article, quantite, prix in lignes:
		doc.append(
			"items",
			{
				"item_code": article,
				"qty": quantite,
				"rate": prices.get(article, 0) if prix is None else prix,
				"price_list_rate": prices.get(article, 0),
				**extra,
			},
		)


@frappe.whitelist()
def search_achat_articles(search=None):
	"""Articles d'achat actifs, avec leur unité et leur prix d'achat connu."""
	require_bureau()
	value = cstr(search).strip()
	items = frappe.get_list(
		"Item",
		filters={"disabled": 0, "is_purchase_item": 1, "has_variants": 0},
		or_filters=[["item_name", "like", f"%{value}%"], ["name", "like", f"%{value}%"]] if value else None,
		fields=["name", "item_name", "stock_uom"],
		order_by="item_name asc",
		limit_page_length=ARTICLE_SEARCH_LIMIT,
	)
	prices = buying_prices([item.name for item in items])
	return [
		{
			"name": item.name,
			"label": item.item_name or item.name,
			"uom": item.stock_uom,
			"prix": prices.get(item.name),
		}
		for item in items
	]
