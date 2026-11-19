# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Réglages, page Listes de choix (/bureau/listes) : les valeurs proposées par les listes déroulantes du bureau.

Raisons de perte d'un devis, catégories de clients et de fournisseurs, groupes d'articles, unités. Les catégories et
groupes sont des arbres ERPNext : le bureau ne propose que les feuilles (`is_group = 0`), créées ici sous la racine.
Une valeur utilisée ne se supprime pas (on la renomme, ou on désactive une unité). Droits : ceux d'ERPNext.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr

from unicare.api.bureau_postes import require_bureau

# code : (doctype, champ du nom, champ parent de l'arbre ou None, libellé, (doctype, champ) qui l'utilisent, aide)
LISTES = {
	"raisons": (
		"Quotation Lost Reason",
		"order_lost_reason",
		None,
		"Raisons de perte",
		(("Quotation Lost Reason Detail", "lost_reason"),),
		"Proposées par « Déclarer perdu » sur un devis.",
	),
	"clients": (
		"Customer Group",
		"customer_group_name",
		"parent_customer_group",
		"Catégories de clients",
		(("Customer", "customer_group"),),
		"Champ Catégorie de la fiche client (pharmacie, grossiste…).",
	),
	"fournisseurs": (
		"Supplier Group",
		"supplier_group_name",
		"parent_supplier_group",
		"Catégories de fournisseurs",
		(("Supplier", "supplier_group"),),
		"Champ Catégorie de la fiche fournisseur.",
	),
	"articles": (
		"Item Group",
		"item_group_name",
		"parent_item_group",
		"Groupes d'articles",
		(("Item", "item_group"),),
		"Champ Groupe de l'article ; sert aussi à faire un inventaire partiel.",
	),
	"unites": (
		"UOM",
		"uom_name",
		None,
		"Unités",
		(
			("Item", "stock_uom"),
			("UOM Conversion Detail", "uom"),
			("Item Price", "uom"),
			("Recette de Conditionnement", "uom"),
			("Ingredient Recette", "uom"),
		),
		"Unités de stock et de vente des articles.",
	),
}
UNITE = "UOM"

# Module où la liste sert, pour la ranger dans la page ; page du bureau qui liste ses fiches (filtre doctype, champ).
MODULES = {
	"raisons": "ventes",
	"clients": "ventes",
	"fournisseurs": "achats",
	"articles": "stock",
	"unites": "stock",
}
LIENS = {
	"raisons": ("Devis", "Quotation Lost Reason Detail", "lost_reason", "devis"),
	"clients": ("Clients", "Customer", "customer_group", "clients"),
	"fournisseurs": ("Fournisseurs", "Supplier", "supplier_group", "fournisseurs"),
	"articles": ("Articles", "Item", "item_group", "articles"),
	"unites": ("Articles", "Item", "stock_uom", "articles"),
}
# Libellé de chaque source d'usage, pour le détail affiché sous le nombre de fiches.
SOURCES = {
	"Quotation Lost Reason Detail": "devis",
	"Customer": "clients",
	"Supplier": "fournisseurs",
	"Item": "articles",
	"UOM Conversion Detail": "conversions",
	"Item Price": "prix",
	"Recette de Conditionnement": "recettes",
	"Ingredient Recette": "lignes de recette",
}


def _liste(code):
	if code not in LISTES:
		frappe.throw(_("Liste inconnue."))
	return LISTES[code]


def _usages_detail(code):
	"""{valeur: {libellé de la source: nombre}} : où chaque valeur est utilisée."""
	detail = {}
	for doctype, field in _liste(code)[4]:
		for row in frappe.get_all(doctype, fields=[field, "count(*) as n"], group_by=field):
			if row.get(field):
				par_source = detail.setdefault(row[field], {})
				label = SOURCES.get(doctype, doctype)
				par_source[label] = par_source.get(label, 0) + row.n
	if code == "unites":
		# L'unité par défaut des nouveaux articles (paramètres de stock) compte comme utilisée.
		defaut = frappe.db.get_single_value("Stock Settings", "stock_uom")
		if defaut:
			detail.setdefault(defaut, {})["unité par défaut"] = 1
	return detail


def _usages(code):
	"""{valeur: nombre de fiches qui l'utilisent}."""
	return {valeur: sum(sources.values()) for valeur, sources in _usages_detail(code).items()}


def _racine(code):
	doctype, _champ, parent, *_rest = _liste(code)
	return (
		frappe.db.get_value(doctype, {"is_group": 1, parent: ["is", "not set"]}, "name") if parent else None
	)


def _valeurs(code):
	"""Les valeurs de la liste. Pour un arbre, ses dossiers aussi (`dossier`), chacun avec son `parent` (None : à la
	racine) ; la racine elle-même n'est pas renvoyée."""
	doctype, _champ, parent, *_rest = _liste(code)
	racine = _racine(code)
	fields = ["name", "modified"] + (["enabled", "must_be_whole_number"] if code == "unites" else [])
	if parent:
		fields += ["is_group", f"{parent} as parent"]
	detail = _usages_detail(code)
	return [
		{
			"name": row.name,
			"modified": str(row.modified),
			"usages": sum(detail.get(row.name, {}).values()),
			"detail": detail.get(row.name, {}),
			"actif": bool(cint(row.get("enabled", 1))),
			**({"entier": bool(cint(row.must_be_whole_number))} if code == "unites" else {}),
			**(
				{"dossier": bool(cint(row.is_group)), "parent": None if row.parent == racine else row.parent}
				if parent
				else {}
			),
		}
		for row in frappe.get_all(doctype, fields=fields, order_by="name asc", limit_page_length=0)
		if not (parent and row.name == racine)
	]


@frappe.whitelist()
def get_listes():
	"""Le résumé de chaque liste (pour les onglets) et ce que ce compte peut y faire."""
	require_bureau()
	listes = []
	for code, (doctype, _champ, _parent, label, _usage, aide) in LISTES.items():
		if not frappe.has_permission(doctype, "read"):
			continue
		filters = {"is_group": 0} if _parent else {}
		usages = _usages(code)
		noms = frappe.get_all(
			doctype,
			filters={**filters, **({"enabled": 1} if code == "unites" else {})},
			pluck="name",
			limit_page_length=0,
		)
		page, lien_doctype, lien_champ, fiches = LIENS[code]
		listes.append(
			{
				"code": code,
				"label": label,
				"aide": aide,
				"module": MODULES[code],
				"total": frappe.db.count(doctype, filters),
				"actifs": frappe.db.count(doctype, {**filters, "enabled": 1}) if code == "unites" else None,
				# Unités : les proposées que rien n'utilise ; ailleurs, les valeurs inutilisées.
				"inutilisees": sum(1 for nom in noms if not usages.get(nom)),
				"fiches": sum(usages.get(nom, 0) for nom in noms) if code != "unites" else None,
				"lien": {"page": page, "doctype": lien_doctype, "champ": lien_champ, "fiches": fiches},
				"fusion": code != "unites",
				# Catégories et groupes : arbres ERPNext, rangés en dossiers (`is_group`).
				"arbre": bool(_parent),
				"dossiers": frappe.db.count(doctype, {"is_group": 1}) - 1 if _parent else 0,
				"droits": {
					"creer": bool(frappe.has_permission(doctype, "create")),
					"modifier": bool(frappe.has_permission(doctype, "write")),
					"supprimer": bool(frappe.has_permission(doctype, "delete")),
					# Sinon (raisons de perte), seule une valeur encore inutilisée change de nom.
					"renommer_utilisee": bool(frappe.get_meta(doctype).allow_rename),
				},
			}
		)
	if not listes:
		frappe.throw(_("Vous n'avez accès à aucune liste de choix."), frappe.PermissionError)
	return listes


@frappe.whitelist()
def get_valeurs(code):
	require_bureau()
	frappe.has_permission(_liste(code)[0], "read", throw=True)
	return _valeurs(code)


def _nom(valeur):
	nom = cstr(valeur).strip()
	if not nom:
		frappe.throw(_("Donnez un nom."))
	if len(nom) > 140:
		frappe.throw(_("Nom trop long (140 caractères au plus)."))
	return nom


def _stale(doc, modified):
	if cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Cette valeur vient d'être modifiée par ailleurs. La liste a été rechargée : vérifiez, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)


def _doc(code, name, modified, perm):
	doctype, _champ, parent, *_rest = _liste(code)
	doc = frappe.get_doc(doctype, name)
	if parent and doc.name == _racine(code):
		frappe.throw(_("La racine de la liste ne se modifie que sur le Desk."))
	doc.check_permission(perm)
	_stale(doc, modified)
	return doc


def _dossier(code, nom):
	"""Le dossier où ranger une valeur : `nom`, ou la racine sans `nom`. Doit être un dossier de la même liste."""
	doctype, _champ, parent, *_rest = _liste(code)
	if not parent:
		frappe.throw(_("Cette liste n'a pas de dossiers."))
	if not nom:
		return _racine(code)
	if not cint(frappe.db.get_value(doctype, nom, "is_group")):
		frappe.throw(_("« {0} » n'est pas un dossier.").format(nom))
	return nom


@frappe.whitelist(methods=["POST"])
def create_valeur(code, nom, dossier=None, est_dossier=0):
	"""Nouvelle valeur ; dans un arbre, rangée dans `dossier` (la racine sinon), ou nouveau dossier (`est_dossier`)."""
	require_bureau()
	doctype, champ, parent, *_rest = _liste(code)
	frappe.has_permission(doctype, "create", throw=True)
	nom = _nom(nom)
	if frappe.db.exists(doctype, nom):
		frappe.throw(_("« {0} » existe déjà.").format(nom))
	doc = frappe.new_doc(doctype)
	doc.set(champ, nom)
	if parent:
		doc.set(parent, _dossier(code, dossier))
		doc.is_group = 1 if cint(est_dossier) else 0
	if code == "unites":
		doc.enabled = 1
	doc.insert()
	return _valeurs(code)


@frappe.whitelist(methods=["POST"])
def rename_valeur(code, name, modified, nom):
	"""Renomme la valeur partout où elle est utilisée (fiches et pièces)."""
	require_bureau()
	doc = _doc(code, name, modified, "write")
	nom = _nom(nom)
	if nom == doc.name:
		return _valeurs(code)
	if frappe.db.exists(doc.doctype, nom) and nom.lower() != doc.name.lower():
		frappe.throw(_("« {0} » existe déjà.").format(nom))
	if frappe.get_meta(doc.doctype).allow_rename:
		frappe.rename_doc(doc.doctype, doc.name, nom, force=False, merge=False)
		return _valeurs(code)
	# ERPNext interdit de renommer ce type (raisons de perte) : une valeur encore libre est remplacée.
	if _usages(code).get(doc.name):
		frappe.throw(
			_("« {0} » est déjà utilisée et ne peut pas être renommée : créez une nouvelle valeur.").format(
				doc.name
			)
		)
	doc.check_permission("delete")
	frappe.delete_doc(doc.doctype, doc.name)
	return create_valeur(code, nom)


@frappe.whitelist(methods=["POST"])
def delete_valeur(code, name, modified):
	require_bureau()
	doc = _doc(code, name, modified, "delete")
	if _usages(code).get(doc.name):
		frappe.throw(_("« {0} » est utilisée : renommez-la plutôt.").format(doc.name))
	parent = _liste(code)[2]
	if parent and cint(doc.is_group) and frappe.db.exists(doc.doctype, {parent: doc.name}):
		frappe.throw(_("Le dossier « {0} » n'est pas vide : déplacez ou supprimez d'abord son contenu.").format(doc.name))
	frappe.delete_doc(doc.doctype, doc.name)
	return _valeurs(code)


@frappe.whitelist(methods=["POST"])
def set_unite(name, modified, actif=None, entier=None):
	"""Unité proposée ou non dans les listes ; quantités entières seulement ou non."""
	require_bureau()
	doc = _doc("unites", name, modified, "write")
	if actif is not None:
		doc.enabled = 1 if cint(actif) else 0
	if entier is not None:
		doc.must_be_whole_number = 1 if cint(entier) else 0
	doc.save()
	return _valeurs("unites")


@frappe.whitelist(methods=["POST"])
def desactiver_unites_inutilisees():
	"""Retire des listes les unités qu'aucun article n'utilise. Elles restent réactivables une à une."""
	require_bureau()
	frappe.has_permission(UNITE, "write", throw=True)
	usages = _usages("unites")
	noms = [
		name
		for name in frappe.get_all(UNITE, filters={"enabled": 1}, pluck="name", limit_page_length=0)
		if not usages.get(name)
	]
	for name in noms:
		doc = frappe.get_doc(UNITE, name)
		doc.check_permission("write")
		doc.enabled = 0
		doc.save()
	return {"desactivees": len(noms), "valeurs": _valeurs("unites")}


def _cle(texte):
	"""Forme comparable d'une valeur : sans accents, casse, ponctuation ni marque du pluriel."""
	import unicodedata

	plain = "".join(
		c for c in unicodedata.normalize("NFD", cstr(texte).casefold()) if unicodedata.category(c) != "Mn"
	)
	mots = ["".join(ch for ch in mot if ch.isalnum()) for mot in plain.split()]
	return " ".join(mot[:-1] if len(mot) > 3 and mot[-1] in "sx" else mot for mot in mots if mot)


@frappe.whitelist()
def get_doublons(code):
	"""Valeurs qui ne diffèrent que par les accents, la casse ou le pluriel : [{source, cible}], la moins utilisée
	en source (à fusionner dans la cible)."""
	require_bureau()
	frappe.has_permission(_liste(code)[0], "read", throw=True)
	if code == "unites":
		return []
	groupes = {}
	for row in _valeurs(code):
		if row.get("dossier"):
			continue
		groupes.setdefault(_cle(row["name"]), []).append(row)
	paires = []
	for rows in groupes.values():
		if len(rows) < 2:
			continue
		rows.sort(key=lambda row: (-row["usages"], row["name"]))
		paires += [
			{"source": row["name"], "cible": rows[0]["name"], "usages": row["usages"]} for row in rows[1:]
		]
	return paires


@frappe.whitelist()
def get_fiches(code, name, limit=5):
	"""Les premières fiches qui utilisent une valeur (pour la fenêtre de fusion), et leur nombre."""
	require_bureau()
	frappe.has_permission(_liste(code)[0], "read", throw=True)
	_page, doctype, champ, _fiches = LIENS[code]
	if not frappe.has_permission(doctype, "read"):
		return {"total": _usages(code).get(name, 0), "fiches": []}
	parent = frappe.get_meta(doctype).istable
	titre = None if parent else frappe.get_meta(doctype).title_field
	rows = frappe.get_all(
		doctype,
		filters={champ: name},
		fields=["parent as name"] if parent else ["name"] + ([titre] if titre else []),
		limit_page_length=cint(limit) or 5,
		order_by="modified desc",
	)
	return {
		"total": _usages(code).get(name, 0),
		"fiches": [
			{"name": row.name, "titre": (row.get(titre) if titre else None) or row.name} for row in rows
		],
	}


@frappe.whitelist(methods=["POST"])
def fusionner(code, name, modified, cible):
	"""Reclasse dans `cible` tout ce qui utilise la valeur `name`, puis supprime `name`. Ne se défait pas.

	Catégories et groupes : renommage avec fusion d'ERPNext, qui suit tous les liens. Raisons de perte (non
	renommables) : les lignes des devis sont reprises une à une. Les unités ne se fusionnent pas (stock, conversions).
	"""
	require_bureau()
	if code == "unites":
		frappe.throw(_("Les unités ne se fusionnent pas : retirez celle-ci des listes."))
	doc = _doc(code, name, modified, "write")
	doc.check_permission("delete")
	if cint(doc.get("is_group")):
		frappe.throw(_("Un dossier ne se fusionne pas : déplacez son contenu, puis supprimez-le."))
	cible = cstr(cible).strip()
	if not cible or cible == doc.name:
		frappe.throw(_("Choisissez une autre valeur dans laquelle fusionner."))
	doctype, _champ, parent, *_rest = _liste(code)
	cible_doc = frappe.db.get_value(doctype, cible, ["name"] + (["is_group"] if parent else []), as_dict=True)
	if not cible_doc:
		frappe.throw(_("« {0} » n'existe pas.").format(cible))
	if parent and cint(cible_doc.is_group):
		frappe.throw(_("Fusionnez dans une valeur, pas dans un groupe."))
	if frappe.get_meta(doctype).allow_rename:
		frappe.rename_doc(doctype, doc.name, cible, force=False, merge=True)
	else:
		for doctype_usage, champ_usage in _liste(code)[4]:
			frappe.db.set_value(
				doctype_usage, {champ_usage: doc.name}, champ_usage, cible, update_modified=False
			)
		frappe.delete_doc(doctype, doc.name)
	return _valeurs(code)


@frappe.whitelist(methods=["POST"])
def deplacer(code, name, modified, dossier=None):
	"""Range une valeur ou un dossier dans un autre dossier (la racine sans `dossier`). Les fiches gardent leur valeur."""
	require_bureau()
	doctype, _champ, parent, *_rest = _liste(code)
	doc = _doc(code, name, modified, "write")
	cible = _dossier(code, dossier)
	if cible == doc.name:
		frappe.throw(_("Un dossier ne se range pas dans lui-même."))
	if cint(doc.is_group):
		lft, rgt = frappe.db.get_value(doctype, doc.name, ["lft", "rgt"])
		cible_lft = frappe.db.get_value(doctype, cible, "lft")
		if lft < cible_lft < rgt:
			frappe.throw(_("« {0} » est rangé dans « {1} » : il ne peut pas le contenir.").format(cible, doc.name))
	doc.set(parent, cible)
	doc.save()
	return _valeurs(code)
