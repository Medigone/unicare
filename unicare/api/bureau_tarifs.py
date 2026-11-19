# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Réglages, page Tarifs et prix (/bureau/tarifs) : les tarifs de vente et d'achat, et les prix des articles.

Un article peut avoir plusieurs lignes « Item Price » dans un même tarif : des périodes (`valid_from`, `valid_upto`),
une unité, un client (vente) ou un fournisseur (achat). Le prix affiché pour un article est son prix « en vigueur » :
la ligne générale (sans client ni fournisseur) que reprend une pièce à la date choisie, selon prix_en_vigueur.py, la
règle que suivent aussi les devis, commandes et pièces d'achat. La case de prix de la page modifie cette ligne ; la
fenêtre d'un article gère toutes ses lignes.

Un tarif désactivé (`enabled`) n'est plus proposé sur les pièces ; ses prix restent lisibles mais ERPNext refuse de
les modifier. Les tarifs par défaut sont ceux des paramètres de vente et d'achat, lus par `_price_list()` et
`buying_price_list()`, et restent actifs. Droits : ceux d'ERPNext.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, cstr, date_diff, flt, getdate, now_datetime, nowdate

from unicare.api import tarifs_calcules as calcul
from unicare.api.bureau_achats import buying_price_list
from unicare.api.bureau_devis import _company, _price_list, filter_words
from unicare.api.bureau_postes import require_bureau
from unicare.api.prix_en_vigueur import choisir, lignes_tarif, prix_en_vigueur, tiers

PRIX = "Item Price"
TARIF = "Price List"
REGLAGES = {
	"vente": ("Selling Settings", "selling_price_list"),
	"achat": ("Buying Settings", "buying_price_list"),
}
VUES = ("tous", "sans_prix", "avec_prix", "a_venir", "expire", "ecart")
PAGE = 50
# Un prix qui s'arrête dans ce nombre de jours « expire bientôt ».
EXPIRE_JOURS = 45
# Écart signalé entre le prix d'un tarif d'achat et le dernier prix payé.
ECART_SIGNALE = 0.05


def _sens(doc):
	return "vente" if cint(doc.get("selling")) else "achat"


def _tarif(name, actif=True):
	"""Un tarif (actif si `actif`), ou une erreur lisible."""
	filters = {"name": name}
	if actif:
		filters["enabled"] = 1
	doc = frappe.db.get_value(
		TARIF, filters, ["name", "selling", "buying", "currency", "enabled"], as_dict=True
	)
	if not doc:
		frappe.throw(
			_("Tarif inconnu ou désactivé : {0}.").format(name)
			if actif
			else _("Tarif inconnu : {0}.").format(name)
		)
	return doc


def _date(date=None):
	return getdate(date) if date else getdate(nowdate())


def _defauts():
	return {"vente": _price_list(), "achat": buying_price_list()}


@frappe.whitelist()
def get_tarifs():
	"""Tous les tarifs (actifs ou non), ceux qui servent par défaut, et ce que ce compte peut y changer."""
	require_bureau()
	frappe.has_permission(PRIX, "read", throw=True)
	rows = frappe.get_all(
		TARIF,
		fields=["name", "selling", "buying", "currency", "enabled", "custom_tarif_base"],
		order_by="enabled desc, name asc",
	)
	today = _date()
	toutes = frappe.get_all(
		PRIX,
		fields=[
			"price_list",
			"item_code",
			"valid_from",
			"valid_upto",
			"customer",
			"supplier",
			"batch_no",
			"modified",
		],
		order_by="valid_from desc, modified desc",
	)
	par_tarif = {}
	for row in toutes:
		par_tarif.setdefault(row.price_list, []).append(row)
	actifs = {sens: {item.name for item in _articles(sens)} for sens in REGLAGES}
	defauts = _defauts()
	return {
		"tarifs": [
			{
				"name": row.name,
				"sens": _sens(row),
				"devise": row.currency,
				"actif": bool(cint(row.enabled)),
				"prix": len(
					[
						code
						for code in choisir(par_tarif.get(row.name, []), today)
						if code in actifs[_sens(row)]
					]
				),
				"total": len(actifs[_sens(row)]),
				"defaut": defauts[_sens(row)] == row.name,
				"base": row.custom_tarif_base or None,
			}
			for row in rows
			if cint(row.selling) or cint(row.buying)
		],
		"defauts": defauts,
		"can_edit_prix": bool(frappe.has_permission(PRIX, "write"))
		and bool(frappe.has_permission(PRIX, "create")),
		"can_create_tarif": bool(frappe.has_permission(TARIF, "create")),
		"can_toggle_tarif": bool(frappe.has_permission(TARIF, "write")),
		"can_delete_tarif": bool(frappe.has_permission(TARIF, "delete"))
		and bool(frappe.has_permission(PRIX, "delete")),
		"can_set_defaut": {
			sens: bool(frappe.has_permission(doctype, "write"))
			for sens, (doctype, _field) in REGLAGES.items()
		},
	}


def _resume(item, rows, date, sens):
	"""Une ligne de la page : le prix général en vigueur de l'article et ce qui l'entoure (à venir, tiers, passé)."""
	courant = choisir(rows, date).get(item.name)
	generales = [row for row in rows if not tiers(row) and not row.batch_no]
	a_venir = sorted(
		(row for row in generales if row.valid_from and getdate(row.valid_from) > date),
		key=lambda row: getdate(row.valid_from),
	)
	anciennes = [row for row in generales if row.valid_upto and getdate(row.valid_upto) < date]
	nb_tiers = sum(
		1 for row in rows if tiers(row) and (not row.valid_upto or getdate(row.valid_upto) >= date)
	)
	fin = getdate(courant.valid_upto) if courant and courant.valid_upto else None
	dernier_achat = flt(item.last_purchase_rate) or None if sens == "achat" else None
	prix = flt(courant.price_list_rate) if courant else None
	ecart = round((dernier_achat - prix) / prix, 4) if prix and dernier_achat else None
	return {
		"article": item.name,
		"designation": item.item_name or item.name,
		"unite": item.stock_uom,
		"prix": prix,
		"unite_prix": courant.uom if courant else None,
		"ligne": courant.name if courant else None,
		"modified": str(courant.modified) if courant else None,
		"debut": str(courant.valid_from) if courant and courant.valid_from else None,
		"fin": str(fin) if fin else None,
		"expire_bientot": bool(fin and date_diff(fin, date) <= EXPIRE_JOURS),
		"a_venir": {"prix": flt(a_venir[0].price_list_rate), "debut": str(a_venir[0].valid_from)}
		if a_venir
		else None,
		"nb_a_venir": len(a_venir),
		"nb_tiers": nb_tiers,
		"nb_anciens": len(anciennes),
		"dernier_expire": {"prix": flt(anciennes[0].price_list_rate), "fin": str(anciennes[0].valid_upto)}
		if anciennes and not courant
		else None,
		"nb_lignes": len(rows),
		"dernier_achat": dernier_achat,
		"ecart": ecart,
	}


def _dans_vue(ligne, vue):
	if vue == "sans_prix":
		return ligne["prix"] is None
	if vue == "avec_prix":
		return ligne["prix"] is not None
	if vue == "a_venir":
		return bool(ligne["nb_a_venir"])
	if vue == "expire":
		return ligne["expire_bientot"]
	if vue == "ecart":
		return ligne["ecart"] is not None and abs(ligne["ecart"]) > ECART_SIGNALE
	return True


def _articles(sens):
	flag = "is_sales_item" if sens == "vente" else "is_purchase_item"
	return frappe.get_all(
		"Item",
		filters={"disabled": 0, flag: 1, "has_variants": 0},
		fields=["name", "item_name", "stock_uom", "last_purchase_rate"],
		order_by="item_name asc",
	)


@frappe.whitelist()
def get_prix(liste, search=None, vue="tous", start=0, date=None):
	"""Une ligne par article actif du sens du tarif (vendu ou acheté), avec son prix en vigueur à `date`."""
	require_bureau()
	frappe.has_permission(PRIX, "read", throw=True)
	if vue not in VUES:
		frappe.throw(_("Vue inconnue."))
	tarif = _tarif(liste, actif=False)
	sens = _sens(tarif)
	date = _date(date)
	items = _articles(sens)
	if cstr(search).strip():
		items = filter_words(items, search)
	par_article = {}
	for row in lignes_tarif(liste, [item.name for item in items]):
		par_article.setdefault(row.item_code, []).append(row)
	lignes = [_resume(item, par_article.get(item.name, []), date, sens) for item in items]
	vues = VUES if sens == "achat" else VUES[:-1]
	compte = {key: sum(1 for ligne in lignes if _dans_vue(ligne, key)) for key in vues}
	reprenables = sum(1 for ligne in lignes if ligne["prix"] is None and ligne["dernier_achat"])
	lignes = [ligne for ligne in lignes if _dans_vue(ligne, vue)]
	start = max(cint(start), 0)
	return {
		"tarif": {
			"name": tarif.name,
			"sens": sens,
			"devise": tarif.currency,
			"actif": bool(cint(tarif.enabled)),
			"regle": _regle_et_changements(tarif.name, sens),
		},
		"date": str(date),
		"lignes": lignes[start : start + PAGE],
		"total": len(lignes),
		"compte": compte,
		# Tarif d'achat : articles sans prix en vigueur qui ont un dernier prix payé, à reprendre.
		"reprenables": reprenables,
		"start": start,
		"page": PAGE,
	}


def _statut(row, courant, date):
	if row.valid_from and getdate(row.valid_from) > date:
		return "a_venir"
	if row.valid_upto and getdate(row.valid_upto) < date:
		return "expire"
	if tiers(row):
		return "tiers"
	if row.batch_no:
		return "lot"
	return "vigueur" if courant and row.name == courant.name else "remplace"


def _item(article):
	item = frappe.db.get_value(
		"Item", article, ["name", "item_name", "stock_uom", "last_purchase_rate", "disabled"], as_dict=True
	)
	if not item or cint(item.disabled):
		frappe.throw(_("Article inconnu ou désactivé : {0}.").format(article))
	return item


@frappe.whitelist()
def get_lignes(liste, article, date=None):
	"""Toutes les lignes de prix d'un article dans un tarif, avec leur statut à `date`, et les unités possibles."""
	require_bureau()
	frappe.has_permission(PRIX, "read", throw=True)
	tarif = _tarif(liste, actif=False)
	sens = _sens(tarif)
	date = _date(date)
	item = _item(article)
	rows = lignes_tarif(liste, [article])
	courant = choisir(rows, date).get(article)
	unites = [
		row.uom
		for row in frappe.get_all(
			"UOM Conversion Detail",
			filters={"parenttype": "Item", "parent": article},
			fields=["uom", "conversion_factor"],
			order_by="conversion_factor asc",
		)
	]
	if item.stock_uom not in unites:
		unites.insert(0, item.stock_uom)
	return {
		"article": item.name,
		"designation": item.item_name or item.name,
		"unite": item.stock_uom,
		"unites": unites,
		"sens": sens,
		"devise": tarif.currency,
		"dernier_achat": flt(item.last_purchase_rate) or None if sens == "achat" else None,
		"lignes": [
			{
				"ligne": row.name,
				"statut": _statut(row, courant, date),
				"prix": flt(row.price_list_rate),
				"debut": str(row.valid_from) if row.valid_from else None,
				"fin": str(row.valid_upto) if row.valid_upto else None,
				"unite": row.uom,
				"tiers": tiers(row),
				"lot": row.batch_no or None,
				"note": row.note or "",
				"delai": cint(row.lead_time_days) or None,
				"modified": str(row.modified),
			}
			for row in sorted(
				rows,
				key=lambda row: getdate(row.valid_from) if row.valid_from else getdate("1900-01-01"),
				reverse=True,
			)
		],
	}


def _prix_valeur(prix):
	text = cstr(prix).strip().replace(" ", "").replace(" ", "").replace(",", ".")
	if not text:
		return None
	try:
		value = float(text)
	except ValueError:
		frappe.throw(_("Prix illisible : {0}.").format(prix))
	if value <= 0:
		frappe.throw(_("Un prix doit être supérieur à zéro. Pour retirer le prix, videz le champ."))
	return value


def _verifier_a_jour(doc, modified):
	if cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Ce prix vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)


def _nouvelle_ligne(liste, article, valeurs):
	doc = frappe.new_doc(PRIX)
	doc.update({"price_list": liste, "item_code": article, **valeurs})
	doc.check_permission("create")
	doc.insert()
	return doc


@frappe.whitelist(methods=["POST"])
def set_prix(liste, article, prix=None, modified=None):
	"""Pose, change ou retire (prix vide) le prix général en vigueur aujourd'hui. Renvoie la ligne à jour.

	Sans prix en vigueur, une ligne est créée à l'unité de stock, valable dès aujourd'hui et sans fin.
	"""
	require_bureau()
	tarif = _tarif(liste)
	sens = _sens(tarif)
	item = _item(article)
	value = _prix_valeur(prix)
	current = prix_en_vigueur(liste, [article]).get(article)
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
		_nouvelle_ligne(
			liste, article, {"uom": item.stock_uom, "price_list_rate": value, "valid_from": nowdate()}
		)
	return _resume(item, lignes_tarif(liste, [article]), _date(), sens)


def _valeurs_ligne(sens, item, valeurs):
	"""Champs « Item Price » d'une ligne saisie dans la fenêtre, vérifiés."""
	valeurs = frappe.parse_json(valeurs) if isinstance(valeurs, str) else (valeurs or {})
	prix = _prix_valeur(valeurs.get("prix"))
	if prix is None:
		frappe.throw(_("Saisissez le prix."))
	debut = valeurs.get("debut") or None
	if not debut:
		frappe.throw(_("Indiquez à partir de quand le prix est valable."))
	fin = valeurs.get("fin") or None
	if fin and getdate(fin) < getdate(debut):
		frappe.throw(_("La fin de validité ne peut pas précéder son début."))
	unite = cstr(valeurs.get("unite")).strip() or item.stock_uom
	if unite != item.stock_uom and not frappe.db.exists(
		"UOM Conversion Detail", {"parenttype": "Item", "parent": item.name, "uom": unite}
	):
		frappe.throw(_("L'article {0} ne se compte pas en {1}.").format(item.item_name or item.name, unite))
	partie = cstr(valeurs.get("tiers")).strip() or None
	doctype = "Customer" if sens == "vente" else "Supplier"
	if partie and not frappe.db.exists(doctype, partie):
		frappe.throw(
			_("{0} inconnu : {1}.").format(_("Client") if sens == "vente" else _("Fournisseur"), partie)
		)
	return {
		"price_list_rate": prix,
		"valid_from": debut,
		"valid_upto": fin,
		"uom": unite,
		"customer": partie if sens == "vente" else None,
		"supplier": partie if sens == "achat" else None,
		"note": cstr(valeurs.get("note")).strip() or None,
		"lead_time_days": max(cint(valeurs.get("delai")), 0) if sens == "achat" else 0,
	}


def _clore_precedents(liste, article, valeurs, sauf=None):
	"""Arrête la veille du nouveau prix les prix de même portée (même tiers, même unité) encore ouverts à cette date."""
	debut = getdate(valeurs["valid_from"])
	veille = add_days(debut, -1)
	for row in lignes_tarif(liste, [article]):
		if row.name == sauf or row.batch_no:
			continue
		if (row.customer or None) != valeurs["customer"] or (row.supplier or None) != valeurs["supplier"]:
			continue
		if row.uom != valeurs["uom"]:
			continue
		commence_avant = not row.valid_from or getdate(row.valid_from) < debut
		ouvert = not row.valid_upto or getdate(row.valid_upto) >= debut
		if commence_avant and ouvert:
			doc = frappe.get_doc(PRIX, row.name)
			doc.check_permission("write")
			doc.valid_upto = veille
			doc.save()


@frappe.whitelist(methods=["POST"])
def save_ligne(liste, article, valeurs, ligne=None, modified=None, clore=0):
	"""Crée (sans `ligne`) ou modifie une ligne de prix d'un article. `clore` arrête la veille les prix qu'elle
	remplace. Renvoie toutes les lignes de l'article."""
	require_bureau()
	tarif = _tarif(liste)
	sens = _sens(tarif)
	item = _item(article)
	champs = _valeurs_ligne(sens, item, valeurs)
	if ligne:
		doc = frappe.get_doc(PRIX, ligne)
		if doc.price_list != liste or doc.item_code != article:
			frappe.throw(_("Cette ligne de prix n'appartient pas à cet article."))
		_verifier_a_jour(doc, modified)
		doc.check_permission("write")
		if cint(clore):
			_clore_precedents(liste, article, champs, sauf=doc.name)
		doc.update(champs)
		doc.save()
	else:
		if cint(clore):
			_clore_precedents(liste, article, champs)
		_nouvelle_ligne(liste, article, champs)
	return get_lignes(liste, article)


@frappe.whitelist(methods=["POST"])
def delete_ligne(liste, ligne, modified):
	"""Supprime une ligne de prix. Renvoie les lignes restantes de l'article."""
	require_bureau()
	_tarif(liste)
	doc = frappe.get_doc(PRIX, ligne)
	if doc.price_list != liste:
		frappe.throw(_("Cette ligne de prix n'appartient pas à ce tarif."))
	_verifier_a_jour(doc, modified)
	doc.check_permission("delete")
	article = doc.item_code
	doc.delete()
	return get_lignes(liste, article)


@frappe.whitelist(methods=["POST"])
def reprendre_derniers_prix(liste, articles=None):
	"""Tarif d'achat : donne aux articles sans prix en vigueur leur dernier prix payé, dès aujourd'hui.

	`articles` : liste de codes ; sans liste, tous les articles achetés concernés. Renvoie le nombre de prix créés.
	"""
	require_bureau()
	tarif = _tarif(liste)
	if _sens(tarif) != "achat":
		frappe.throw(_("Seul un tarif d'achat reprend les derniers prix payés."))
	items = _articles("achat")
	if articles:
		wanted = set(frappe.parse_json(articles) if isinstance(articles, str) else articles)
		items = [item for item in items if item.name in wanted]
	en_vigueur = prix_en_vigueur(liste, [item.name for item in items])
	crees = 0
	for item in items:
		if item.name in en_vigueur or flt(item.last_purchase_rate) <= 0:
			continue
		_nouvelle_ligne(
			liste,
			item.name,
			{"uom": item.stock_uom, "price_list_rate": flt(item.last_purchase_rate), "valid_from": nowdate()},
		)
		crees += 1
	return {"crees": crees}


@frappe.whitelist(methods=["POST"])
def create_tarif(
	nom,
	sens,
	base=None,
	ajustement="aucun",
	pourcentage=0,
	arrondi=0,
	debut=None,
	a_venir=1,
	tiers=0,
	lien=1,
):
	"""Nouveau tarif de vente ou d'achat, dans la devise de la société.

	Avec `base`, il reprend les prix de ce tarif, ajustés (remise ou majoration en %, puis arrondi) et valables dès
	`debut` ; `a_venir` et `tiers` ajoutent les prix à venir et ceux réservés à un client ou un fournisseur. Avec
	`lien`, il garde sa règle et signale ensuite les changements du tarif de base (voir tarifs_calcules.py).
	"""
	require_bureau()
	frappe.has_permission(TARIF, "create", throw=True)
	if sens not in REGLAGES:
		frappe.throw(_("Choisissez un tarif de vente ou d'achat."))
	nom = cstr(nom).strip()
	if not nom:
		frappe.throw(_("Donnez un nom au tarif."))
	if frappe.db.exists(TARIF, nom):
		frappe.throw(_("Un tarif s'appelle déjà « {0} ».").format(nom))
	r = None
	if base:
		_tarif(base, actif=False)
		ajustement, pourcentage, arrondi = calcul.verifier_regle(ajustement, pourcentage, arrondi)
		r = {"base": base, "ajustement": ajustement, "pourcentage": pourcentage, "arrondi": arrondi}
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
	if r and cint(lien):
		doc.update(
			{
				"custom_tarif_base": base,
				"custom_ajustement": r["ajustement"],
				"custom_pourcentage": r["pourcentage"],
				"custom_arrondi": r["arrondi"],
				"custom_calcule_le": now_datetime(),
			}
		)
	doc.insert()
	crees = calcul.copier(doc.name, sens, base, r, debut, cint(a_venir), cint(tiers)) if r else 0
	result = get_tarifs()
	result["crees"] = crees
	return result


def _regle_et_changements(liste, sens):
	r = calcul.regle(liste)
	if r:
		r["changements"] = len(calcul.changements(liste, r, sens))
	return r


def _tarif_calcule(liste):
	tarif = _tarif(liste)
	r = calcul.regle(liste)
	if not r:
		frappe.throw(_("Le tarif « {0} » n'est pas calculé depuis un autre tarif.").format(liste))
	return _sens(tarif), r


@frappe.whitelist()
def get_changements(liste):
	"""Tarif calculé : sa règle, et les changements du tarif de base pas encore repris."""
	require_bureau()
	frappe.has_permission(PRIX, "read", throw=True)
	sens, r = _tarif_calcule(liste)
	return {"regle": r, "changements": calcul.changements(liste, r, sens)}


@frappe.whitelist(methods=["POST"])
def recalculer(liste, cles=None, ignorer=None):
	"""Applique les changements du tarif de base choisis (`cles`) ; `ignorer` les marque vus sans changer le prix."""
	require_bureau()
	sens, r = _tarif_calcule(liste)
	cles = frappe.parse_json(cles) if isinstance(cles, str) else cles
	ignorer = frappe.parse_json(ignorer) if isinstance(ignorer, str) else ignorer
	touches = calcul.appliquer(liste, r, sens, cles or [], ignorer or [])
	return {"touches": touches, **get_changements(liste)}


@frappe.whitelist(methods=["POST"])
def set_regle(liste, ajustement, pourcentage=0, arrondi=0):
	"""Change la règle d'un tarif calculé : ses prix suivent, sauf ceux modifiés à la main."""
	require_bureau()
	_sens_d, ancienne = _tarif_calcule(liste)
	ajustement, pourcentage, arrondi = calcul.verifier_regle(ajustement, pourcentage, arrondi)
	nouvelle = {**ancienne, "ajustement": ajustement, "pourcentage": pourcentage, "arrondi": arrondi}
	doc = frappe.get_doc(TARIF, liste)
	doc.check_permission("write")
	gardes = calcul.changer_regle(liste, ancienne, nouvelle)
	doc.update(
		{"custom_ajustement": ajustement, "custom_pourcentage": pourcentage, "custom_arrondi": arrondi}
	)
	doc.save()
	return {"gardes": gardes, **get_changements(liste)}


@frappe.whitelist(methods=["POST"])
def detacher(liste):
	"""Le tarif cesse de suivre son tarif de base : ses prix restent, ils ne sont plus signalés ni recalculés."""
	require_bureau()
	_tarif_calcule(liste)
	doc = frappe.get_doc(TARIF, liste)
	doc.check_permission("write")
	doc.custom_tarif_base = None
	doc.save()
	return get_tarifs()


@frappe.whitelist(methods=["POST"])
def delete_tarif(liste):
	"""Supprime un tarif et toutes ses lignes de prix. Renvoie les tarifs restants.

	Le tarif par défaut ne se supprime pas. Les tarifs calculés depuis celui-ci gardent leurs prix et sont détachés.
	Un tarif utilisé par une pièce ou une fiche (client, fournisseur) est refusé : il se désactive à la place.
	"""
	require_bureau()
	tarif = _tarif(liste, actif=False)
	if _defauts()[_sens(tarif)] == tarif.name:
		frappe.throw(
			_("« {0} » est le tarif par défaut : choisissez d'abord un autre tarif par défaut.").format(liste)
		)
	frappe.has_permission(TARIF, "delete", throw=True)
	frappe.has_permission(PRIX, "delete", throw=True)
	derives = frappe.get_all(TARIF, filters={"custom_tarif_base": liste}, pluck="name")
	lignes = frappe.get_all(PRIX, filters={"price_list": liste}, pluck="name")
	frappe.db.savepoint("supprimer_tarif")
	try:
		for name in lignes:
			frappe.delete_doc(PRIX, name)
		for name in derives:
			frappe.db.set_value(TARIF, name, "custom_tarif_base", None)
		frappe.delete_doc(TARIF, liste)
	except frappe.LinkExistsError:
		frappe.db.rollback(save_point="supprimer_tarif")
		frappe.clear_last_message()
		frappe.throw(
			_(
				"« {0} » est utilisé par des pièces ou des fiches (client, fournisseur) : il ne peut pas être supprimé. "
				"Désactivez-le plutôt."
			).format(liste)
		)
	result = get_tarifs()
	result["supprimes"] = len(lignes)
	result["detaches"] = derives
	return result


@frappe.whitelist(methods=["POST"])
def set_tarif_actif(liste, actif):
	"""Active ou désactive un tarif. Le tarif par défaut d'un sens reste actif."""
	require_bureau()
	tarif = _tarif(liste, actif=False)
	actif = bool(cint(actif))
	if not actif and _defauts()[_sens(tarif)] == tarif.name:
		frappe.throw(
			_("« {0} » est le tarif par défaut : choisissez d'abord un autre tarif par défaut.").format(liste)
		)
	doc = frappe.get_doc(TARIF, liste)
	doc.check_permission("write")
	doc.enabled = int(actif)
	doc.save()
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
	"""Prix en vigueur de l'article dans les tarifs par défaut, pour sa fiche ; None si le compte ne lit pas les prix."""
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
		row = prix_en_vigueur(liste, [article]).get(article) if liste else None
		concerne = cint(item.get("is_sales_item" if sens == "vente" else "is_purchase_item"))
		result[sens] = {
			"tarif": liste,
			"prix": flt(row.price_list_rate) if row else None,
			"concerne": bool(concerne),
		}
	return result
