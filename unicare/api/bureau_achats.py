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
PRICE_LIST = "Price List"
TAXES_ACHAT = "Purchase Taxes and Charges Template"
ARTICLE_SEARCH_LIMIT = 12
EXCLU = "Exclu"


def buying_price_list():
	return frappe.db.get_single_value("Buying Settings", "buying_price_list") or frappe.db.get_value(
		"Price List", {"buying": 1, "enabled": 1}, "name"
	)


def buying_lists():
	"""Listes de prix d'achat actives, proposées dans les fenêtres."""
	return frappe.get_all(PRICE_LIST, filters={"buying": 1, "enabled": 1}, pluck="name", order_by="name asc")


def liste_achat(value=None, fournisseur=None):
	"""La liste de prix d'une pièce d'achat : celle choisie, sinon celle du fournisseur, sinon celle par défaut."""
	value = cstr(value).strip()
	if value:
		if not frappe.db.exists(PRICE_LIST, {"name": value, "buying": 1, "enabled": 1}):
			frappe.throw(_("Choisissez une liste de prix d'achat active."))
		return value
	own = frappe.db.get_value(SUPPLIER, fournisseur, "default_price_list") if fournisseur else None
	if own and frappe.db.exists(PRICE_LIST, {"name": own, "buying": 1, "enabled": 1}):
		return own
	return buying_price_list()


def buying_prices(item_codes, fournisseur=None, date=None, liste=None, dernier=True):
	"""Prix d'achat en vigueur dans le tarif `liste` (par défaut : celui des réglages), pour ce fournisseur à cette date.

	Voir prix_en_vigueur.

	Sans prix en vigueur : le dernier prix d'achat de l'article (sauf `dernier` faux). Sans l'un ni l'autre : absent.
	"""
	from unicare.api.prix_en_vigueur import prix_en_vigueur

	if not item_codes:
		return {}
	prices = {}
	price_list = liste or buying_price_list()
	if price_list:
		for code, row in prix_en_vigueur(price_list, item_codes, date, fournisseur=fournisseur).items():
			prices[code] = flt(row.price_list_rate)
	missing = [code for code in item_codes if code not in prices] if dernier else []
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
		"listes_prix": buying_lists(),
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
	prices = buying_prices(
		[article for article, _quantite, _prix in lignes],
		doc.get("supplier"),
		doc.get("transaction_date") or doc.get("posting_date"),
		doc.get("buying_price_list"),
	)
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
def search_achat_articles(search=None, liste_prix=None, fournisseur=None):
	"""Articles d'achat actifs, avec leur unité, leur prix d'achat dans la liste choisie (pour ce fournisseur) et leur stock."""
	from unicare.api.bureau_devis import article_search

	require_bureau()
	fournisseur = cstr(fournisseur).strip() or None
	liste = liste_achat(liste_prix, fournisseur)
	found = article_search(search, "is_purchase_item", lambda codes: buying_prices(codes, fournisseur, None, liste))
	# Le prix de la liste seule (sans le dernier prix payé) : un prix saisi autre que lui se reporte dans la liste.
	dans_liste = buying_prices([row["name"] for row in found], fournisseur, None, liste, dernier=False)
	for row in found:
		row["prix_liste"] = dans_liste.get(row["name"])
	return found


@frappe.whitelist()
def get_prix_achat(articles=None, liste_prix=None, fournisseur=None):
	"""Prix d'achat de ces articles pour ce fournisseur : `prix`, repris par les lignes (la liste, sinon le dernier
	prix payé) ; `liste`, ceux de la liste seule, auxquels se compare un prix saisi."""
	require_bureau()
	codes = [cstr(code) for code in (_parse(articles) or []) if cstr(code)][:LIGNES_MAX]
	fournisseur = cstr(fournisseur).strip() or None
	liste = liste_achat(liste_prix, fournisseur)
	return {
		"prix": buying_prices(codes, fournisseur, None, liste),
		"liste": buying_prices(codes, fournisseur, None, liste, dernier=False),
	}
