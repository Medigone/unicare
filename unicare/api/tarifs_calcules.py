# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Tarifs calculés depuis un autre (« Tarif remise 10 % » à partir du tarif standard).

ERPNext n'a pas de tarif dérivé : les prix sont donc de vraies lignes « Item Price », que les pièces lisent comme les
autres. La règle est gardée sur le tarif (`custom_tarif_base`, `custom_ajustement`, `custom_pourcentage`,
`custom_arrondi`, `custom_calcule_le`) et chaque prix calculé retient sa ligne d'origine (`custom_prix_source`) et le
prix de celle-ci au calcul (`custom_taux_source`).

Un prix est « modifié à la main » quand il ne vaut plus la règle appliquée à son prix d'origine : il n'est jamais
recalculé sans accord. Un changement du tarif de base (prix, fin de validité, ligne ajoutée ou supprimée) est signalé
par `changements`, et appliqué ligne par ligne par `appliquer`.
"""

import math

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, getdate, now_datetime, nowdate

from unicare.api.prix_en_vigueur import PRIX, choisir, tiers

AJUSTEMENTS = ("aucun", "remise", "majoration")
ARRONDIS = (0, 0.01, 1, 5, 10, 50, 100)
CHAMPS = [
	"name",
	"item_code",
	"price_list_rate",
	"uom",
	"valid_from",
	"valid_upto",
	"customer",
	"supplier",
	"batch_no",
	"note",
	"lead_time_days",
	"custom_prix_source",
	"custom_taux_source",
	"modified",
]


def regle(liste):
	"""La règle d'un tarif calculé, ou None s'il n'est pas lié à un tarif de base."""
	row = frappe.db.get_value(
		"Price List",
		liste,
		[
			"custom_tarif_base",
			"custom_ajustement",
			"custom_pourcentage",
			"custom_arrondi",
			"custom_calcule_le",
		],
		as_dict=True,
	)
	if not row or not row.custom_tarif_base:
		return None
	return {
		"base": row.custom_tarif_base,
		"ajustement": row.custom_ajustement or "aucun",
		"pourcentage": flt(row.custom_pourcentage),
		"arrondi": flt(row.custom_arrondi),
		"calcule_le": str(row.custom_calcule_le) if row.custom_calcule_le else None,
	}


def verifier_regle(ajustement, pourcentage, arrondi):
	"""Règle saisie → (ajustement, pourcentage, arrondi) vérifiés."""
	ajustement = cstr(ajustement) or "aucun"
	if ajustement not in AJUSTEMENTS:
		frappe.throw(_("Choisissez une remise, une majoration ou aucun ajustement."))
	pourcentage = flt(cstr(pourcentage).replace(",", ".")) if ajustement != "aucun" else 0
	if pourcentage < 0:
		frappe.throw(_("Le pourcentage ne peut pas être négatif."))
	if ajustement == "remise" and pourcentage >= 100:
		frappe.throw(_("Une remise doit rester sous 100 %."))
	arrondi = flt(arrondi)
	if arrondi not in ARRONDIS:
		frappe.throw(_("Arrondi inconnu."))
	return ajustement, pourcentage, arrondi


def calculer(taux, ajustement, pourcentage, arrondi):
	"""Le prix calculé depuis un prix d'origine : ajustement, puis arrondi au pas le plus proche (0,5 vers le haut)."""
	facteur = {"remise": 1 - pourcentage / 100, "majoration": 1 + pourcentage / 100}.get(ajustement, 1)
	valeur = flt(taux) * facteur
	pas = flt(arrondi)
	if pas:
		valeur = math.floor(valeur / pas + 0.5 + 1e-9) * pas
	valeur = flt(valeur, 2)
	return valeur if valeur > 0 else flt(pas or 0.01)


def _calcule_selon(r, taux):
	return calculer(taux, r["ajustement"], r["pourcentage"], r["arrondi"])


def manuel(r, row):
	"""Le prix a-t-il été changé à la main depuis son calcul ?"""
	return abs(flt(row.price_list_rate) - _calcule_selon(r, row.custom_taux_source)) > 0.005


def _lignes(liste):
	return frappe.get_all(
		PRIX, filters={"price_list": liste}, fields=CHAMPS, order_by="valid_from desc, modified desc"
	)


def _a_copier(base_rows, debut, a_venir, avec_tiers):
	"""Lignes du tarif de base à copier : le prix général en vigueur à `debut`, les prix à venir, ceux des tiers."""
	generales = [row for row in base_rows if not tiers(row) and not row.batch_no]
	retenues = list(choisir(generales, debut).values())
	if a_venir:
		retenues += [row for row in generales if row.valid_from and getdate(row.valid_from) > debut]
	if avec_tiers:
		retenues += [
			row
			for row in base_rows
			if tiers(row) and not row.batch_no and (not row.valid_upto or getdate(row.valid_upto) >= debut)
		]
	return retenues


def _valeurs(r, source, debut, sens):
	"""Champs d'une ligne calculée depuis `source`. Une ligne déjà commencée part de `debut`."""
	depart = getdate(source.valid_from) if source.valid_from else None
	return {
		"item_code": source.item_code,
		"uom": source.uom,
		"price_list_rate": _calcule_selon(r, source.price_list_rate),
		"valid_from": str(max(depart, debut)) if depart else str(debut),
		"valid_upto": source.valid_upto,
		"customer": source.customer if sens == "vente" else None,
		"supplier": source.supplier if sens == "achat" else None,
		"note": source.note,
		"lead_time_days": cint(source.lead_time_days) if sens == "achat" else 0,
		"custom_prix_source": source.name,
		"custom_taux_source": flt(source.price_list_rate),
	}


def _inserer(liste, valeurs):
	doc = frappe.new_doc(PRIX)
	doc.update({"price_list": liste, **valeurs})
	doc.check_permission("create")
	doc.insert()
	return doc


def copier(liste, sens, base, r, debut, a_venir=True, avec_tiers=False):
	"""Remplit un tarif neuf avec les prix calculés du tarif de base. Renvoie le nombre de prix créés."""
	debut = getdate(debut) if debut else getdate(nowdate())
	base_sens = "vente" if cint(frappe.db.get_value("Price List", base, "selling")) else "achat"
	retenues = _a_copier(_lignes(base), debut, a_venir, avec_tiers and base_sens == sens)
	for source in retenues:
		_inserer(liste, _valeurs(r, source, debut, sens))
	return len(retenues)


def changements(liste, r, sens):
	"""Ce qui a changé dans le tarif de base depuis le calcul : une entrée par ligne à recalculer, ajouter ou retirer."""
	base_rows = {row.name: row for row in _lignes(r["base"])}
	calcules = [row for row in _lignes(liste) if row.custom_prix_source]
	suivies = {row.custom_prix_source for row in calcules}
	avec_tiers = any(tiers(row) for row in calcules)
	today = getdate(nowdate())
	noms = {}

	def entree(cle, genre, source, row):
		noms.setdefault((source or row).item_code, None)
		return {
			"cle": cle,
			"type": genre,
			"article": (source or row).item_code,
			"tiers": tiers(source or row),
			"base_avant": flt(row.custom_taux_source) if row else None,
			"base_apres": flt(source.price_list_rate) if source else None,
			"actuel": flt(row.price_list_rate) if row else None,
			"nouveau": _calcule_selon(r, source.price_list_rate) if source else None,
			"debut": str((source or row).valid_from) if (source or row).valid_from else None,
			"fin": str(source.valid_upto) if source and source.valid_upto else None,
			"manuel": bool(row and manuel(r, row)),
		}

	result = []
	for row in calcules:
		source = base_rows.get(row.custom_prix_source)
		if not source:
			result.append(entree(row.name, "supprime", None, row))
		elif flt(source.price_list_rate) != flt(row.custom_taux_source) or cstr(source.valid_upto) != cstr(
			row.valid_upto
		):
			result.append(entree(row.name, "prix", source, row))
	# Lignes du tarif de base qu'une copie faite aujourd'hui reprendrait, et qui n'ont pas encore leur prix calculé.
	for source in _a_copier(list(base_rows.values()), today, True, avec_tiers):
		if source.name not in suivies:
			result.append(entree(f"nouveau:{source.name}", "nouveau", source, None))
	designations = dict(
		frappe.get_all(
			"Item", filters={"name": ["in", list(noms)]}, fields=["name", "item_name"], as_list=True
		)
	)
	for item in result:
		item["designation"] = designations.get(item["article"]) or item["article"]
	result.sort(key=lambda item: (item["designation"], item["debut"] or ""))
	return result


def appliquer(liste, r, sens, cles, ignorer=()):
	"""Applique les changements choisis (`cles`), et marque vus ceux à ignorer. Renvoie le nombre de lignes touchées."""
	cles, ignorer = set(cles or []), set(ignorer or [])
	base_rows = {row.name: row for row in _lignes(r["base"])}
	today = getdate(nowdate())
	touches = 0
	for item in changements(liste, r, sens):
		cle = item["cle"]
		if cle not in cles and cle not in ignorer:
			continue
		if item["type"] == "nouveau":
			if cle in cles:
				_inserer(liste, _valeurs(r, base_rows[cle.split(":", 1)[1]], today, sens))
				touches += 1
			continue
		doc = frappe.get_doc(PRIX, cle)
		if item["type"] == "supprime":
			if cle in cles:
				doc.check_permission("delete")
				doc.delete()
				touches += 1
			continue
		source = base_rows[doc.custom_prix_source]
		doc.check_permission("write")
		if cle in cles:
			doc.price_list_rate = _calcule_selon(r, source.price_list_rate)
			doc.valid_upto = source.valid_upto
		doc.custom_taux_source = flt(source.price_list_rate)
		doc.save()
		touches += 1
	frappe.db.set_value("Price List", liste, "custom_calcule_le", now_datetime())
	return touches


def changer_regle(liste, ancienne, nouvelle):
	"""Nouvelle règle : les prix calculés suivent, ceux modifiés à la main restent tels quels. Renvoie leur nombre."""
	gardes = 0
	for row in _lignes(liste):
		if not row.custom_prix_source:
			continue
		if manuel(ancienne, row):
			gardes += 1
			continue
		doc = frappe.get_doc(PRIX, row.name)
		doc.check_permission("write")
		doc.price_list_rate = _calcule_selon(nouvelle, row.custom_taux_source)
		doc.save()
	return gardes
