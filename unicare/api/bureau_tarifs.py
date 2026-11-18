# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Réglages, page Tarifs et prix (/bureau/tarifs) : les tarifs de vente et d'achat, et le prix de chaque article.

Le prix affiché est celui que les devis et commandes reprennent : pour un article, la ligne « Item Price » du tarif la
plus récente (`valid_from`), comme `_prices` (bureau_devis.py) et `buying_prices` (bureau_achats.py). Modifier un prix
modifie cette ligne ; un article sans prix en reçoit une, à son unité de stock. Les tarifs par défaut sont ceux des
paramètres de vente et d'achat, lus par `_price_list()` et `buying_price_list()`. Droits : ceux d'ERPNext.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

from unicare.api.bureau_achats import buying_price_list
from unicare.api.bureau_devis import _company, _price_list, filter_words
from unicare.api.bureau_postes import require_bureau

PRIX = "Item Price"
TARIF = "Price List"
REGLAGES = {
	"vente": ("Selling Settings", "selling_price_list"),
	"achat": ("Buying Settings", "buying_price_list"),
}
VUES = ("tous", "sans_prix", "avec_prix")
PAGE = 50


def _sens(doc):
	return "vente" if cint(doc.get("selling")) else "achat"


def _tarif(name):
	"""Un tarif actif, ou une erreur lisible."""
	doc = frappe.db.get_value(
		TARIF, {"name": name, "enabled": 1}, ["name", "selling", "buying", "currency"], as_dict=True
	)
	if not doc:
		frappe.throw(_("Tarif inconnu ou désactivé : {0}.").format(name))
	return doc


@frappe.whitelist()
def get_tarifs():
	"""Les tarifs actifs, ceux qui servent par défaut, et ce que ce compte peut y changer."""
	require_bureau()
	frappe.has_permission(PRIX, "read", throw=True)
	rows = frappe.get_all(
		TARIF, filters={"enabled": 1}, fields=["name", "selling", "buying", "currency"], order_by="name asc"
	)
	counts = {
		row.price_list: row.n
		for row in frappe.get_all(
			PRIX, fields=["price_list", "count(distinct item_code) as n"], group_by="price_list"
		)
	}
	defauts = {"vente": _price_list(), "achat": buying_price_list()}
	return {
		"tarifs": [
			{
				"name": row.name,
				"sens": _sens(row),
				"devise": row.currency,
				"prix": counts.get(row.name, 0),
				"defaut": defauts[_sens(row)] == row.name,
			}
			for row in rows
			if cint(row.selling) or cint(row.buying)
		],
		"defauts": defauts,
		"can_edit_prix": bool(frappe.has_permission(PRIX, "write"))
		and bool(frappe.has_permission(PRIX, "create")),
		"can_create_tarif": bool(frappe.has_permission(TARIF, "create")),
		"can_set_defaut": {
			sens: bool(frappe.has_permission(doctype, "write"))
			for sens, (doctype, _field) in REGLAGES.items()
		},
	}


def _lignes_prix(liste, codes):
	"""La ligne de prix lue par les pièces, par article : la plus récente du tarif."""
	if not codes:
		return {}
	rows = frappe.get_all(
		PRIX,
		filters={"price_list": liste, "item_code": ["in", list(codes)]},
		fields=["name", "item_code", "price_list_rate", "uom", "modified"],
		order_by="valid_from desc, modified desc",
	)
	found = {}
	for row in rows:
		found.setdefault(row.item_code, row)
	return found


def _ligne(item, prix, sens):
	return {
		"article": item.name,
		"designation": item.item_name or item.name,
		"unite": item.stock_uom,
		"prix": flt(prix.price_list_rate) if prix else None,
		"unite_prix": prix.uom if prix else None,
		"ligne": prix.name if prix else None,
		"modified": str(prix.modified) if prix else None,
		"dernier_achat": flt(item.last_purchase_rate) or None if sens == "achat" else None,
	}


@frappe.whitelist()
def get_prix(liste, search=None, vue="tous", start=0):
	"""Une ligne par article actif du sens du tarif (vendu ou acheté), avec son prix ou rien."""
	require_bureau()
	frappe.has_permission(PRIX, "read", throw=True)
	if vue not in VUES:
		frappe.throw(_("Vue inconnue."))
	tarif = _tarif(liste)
	sens = _sens(tarif)
	flag = "is_sales_item" if sens == "vente" else "is_purchase_item"
	items = frappe.get_all(
		"Item",
		filters={"disabled": 0, flag: 1, "has_variants": 0},
		fields=["name", "item_name", "stock_uom", "last_purchase_rate"],
		order_by="item_name asc",
	)
	if cstr(search).strip():
		items = filter_words(items, search)
	prix = _lignes_prix(liste, [item.name for item in items])
	compte = {"tous": len(items), "sans_prix": sum(1 for item in items if item.name not in prix)}
	compte["avec_prix"] = compte["tous"] - compte["sans_prix"]
	if vue == "sans_prix":
		items = [item for item in items if item.name not in prix]
	elif vue == "avec_prix":
		items = [item for item in items if item.name in prix]
	start = max(cint(start), 0)
	return {
		"tarif": {"name": tarif.name, "sens": sens, "devise": tarif.currency},
		"lignes": [_ligne(item, prix.get(item.name), sens) for item in items[start : start + PAGE]],
		"total": len(items),
		"compte": compte,
		"start": start,
		"page": PAGE,
	}


def _prix_valeur(prix):
	text = cstr(prix).strip().replace(" ", "").replace(",", ".")
	if not text:
		return None
	try:
		value = float(text)
	except ValueError:
		frappe.throw(_("Prix illisible : {0}.").format(prix))
	if value <= 0:
		frappe.throw(_("Un prix doit être supérieur à zéro. Pour retirer le prix, videz le champ."))
	return value


@frappe.whitelist(methods=["POST"])
def set_prix(liste, article, prix=None, modified=None):
	"""Pose, change ou retire (prix vide) le prix d'un article dans un tarif. Renvoie la ligne à jour."""
	require_bureau()
	tarif = _tarif(liste)
	sens = _sens(tarif)
	item = frappe.db.get_value(
		"Item", article, ["name", "item_name", "stock_uom", "last_purchase_rate", "disabled"], as_dict=True
	)
	if not item or cint(item.disabled):
		frappe.throw(_("Article inconnu ou désactivé : {0}.").format(article))
	value = _prix_valeur(prix)
	current = _lignes_prix(liste, [article]).get(article)
	if current and cstr(modified) != str(current.modified):
		frappe.throw(
			_(
				"Ce prix vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	if not current and modified:
		frappe.throw(
			_("Ce prix vient d'être retiré par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."),
			frappe.TimestampMismatchError,
		)
	if current:
		doc = frappe.get_doc(PRIX, current.name)
		if value is None:
			doc.check_permission("delete")
			doc.delete()
		else:
			doc.check_permission("write")
			doc.price_list_rate = value
			doc.save()
	elif value is not None:
		doc = frappe.new_doc(PRIX)
		doc.update(
			{"price_list": liste, "item_code": article, "uom": item.stock_uom, "price_list_rate": value}
		)
		doc.check_permission("create")
		doc.insert()
	return _ligne(item, _lignes_prix(liste, [article]).get(article), sens)


@frappe.whitelist(methods=["POST"])
def create_tarif(nom, sens):
	"""Nouveau tarif de vente ou d'achat, dans la devise de la société."""
	require_bureau()
	frappe.has_permission(TARIF, "create", throw=True)
	if sens not in REGLAGES:
		frappe.throw(_("Choisissez un tarif de vente ou d'achat."))
	nom = cstr(nom).strip()
	if not nom:
		frappe.throw(_("Donnez un nom au tarif."))
	if frappe.db.exists(TARIF, nom):
		frappe.throw(_("Un tarif s'appelle déjà « {0} ».").format(nom))
	company = _company()
	currency = frappe.db.get_value("Company", company, "default_currency") if company else None
	doc = frappe.new_doc(TARIF)
	doc.update(
		{
			"price_list_name": nom,
			"enabled": 1,
			"selling": int(sens == "vente"),
			"buying": int(sens == "achat"),
			"currency": currency or "DZD",
		}
	)
	doc.insert()
	return get_tarifs()


@frappe.whitelist(methods=["POST"])
def set_tarif_defaut(sens, liste):
	"""Le tarif repris par les nouvelles pièces de vente ou d'achat."""
	require_bureau()
	if sens not in REGLAGES:
		frappe.throw(_("Choisissez un tarif de vente ou d'achat."))
	tarif = _tarif(liste)
	if _sens(tarif) != sens:
		frappe.throw(
			_("Le tarif {0} n'est pas un tarif {1}.").format(
				liste, _("de vente") if sens == "vente" else _("d'achat")
			)
		)
	doctype, field = REGLAGES[sens]
	settings = frappe.get_single(doctype)
	settings.check_permission("write")
	settings.set(field, liste)
	settings.save()
	return get_tarifs()


def prix_article(article):
	"""Prix de l'article dans les tarifs par défaut, pour sa fiche ; None si le compte ne lit pas les prix."""
	if not frappe.has_permission(PRIX, "read"):
		return None
	item = (
		frappe.db.get_value(
			"Item", article, ["is_sales_item", "is_purchase_item", "last_purchase_rate"], as_dict=True
		)
		or {}
	)
	result = {
		"dernier_achat": flt(item.get("last_purchase_rate")) or None,
		"can_edit": bool(frappe.has_permission(PRIX, "write")),
	}
	for sens, liste in (("vente", _price_list()), ("achat", buying_price_list())):
		row = _lignes_prix(liste, [article]).get(article) if liste else None
		concerne = cint(item.get("is_sales_item" if sens == "vente" else "is_purchase_item"))
		result[sens] = {
			"tarif": liste,
			"prix": flt(row.price_list_rate) if row else None,
			"concerne": bool(concerne),
		}
	return result
