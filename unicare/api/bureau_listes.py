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


def _liste(code):
	if code not in LISTES:
		frappe.throw(_("Liste inconnue."))
	return LISTES[code]


def _usages(code):
	"""{valeur: nombre de fiches qui l'utilisent}."""
	counts = {}
	for doctype, field in _liste(code)[4]:
		for row in frappe.get_all(doctype, fields=[field, "count(*) as n"], group_by=field):
			if row.get(field):
				counts[row[field]] = counts.get(row[field], 0) + row.n
	if code == "unites":
		# L'unité par défaut des nouveaux articles (paramètres de stock) compte comme utilisée.
		defaut = frappe.db.get_single_value("Stock Settings", "stock_uom")
		if defaut:
			counts[defaut] = counts.get(defaut, 0) + 1
	return counts


def _racine(code):
	doctype, _champ, parent, *_rest = _liste(code)
	return frappe.db.get_value(doctype, {"is_group": 1, parent: ["is", "not set"]}, "name") if parent else None


def _valeurs(code):
	doctype, _champ, parent, *_rest = _liste(code)
	filters = {"is_group": 0} if parent else {}
	fields = ["name", "modified"] + (["enabled", "must_be_whole_number"] if code == "unites" else [])
	usages = _usages(code)
	return [
		{
			"name": row.name,
			"modified": str(row.modified),
			"usages": usages.get(row.name, 0),
			"actif": bool(cint(row.get("enabled", 1))),
			**({"entier": bool(cint(row.must_be_whole_number))} if code == "unites" else {}),
		}
		for row in frappe.get_all(doctype, filters=filters, fields=fields, order_by="name asc", limit_page_length=0)
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
		listes.append(
			{
				"code": code,
				"label": label,
				"aide": aide,
				"total": frappe.db.count(doctype, filters),
				"actifs": frappe.db.count(doctype, {**filters, "enabled": 1}) if code == "unites" else None,
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
			_("Cette valeur vient d'être modifiée par ailleurs. La liste a été rechargée : vérifiez, puis recommencez."),
			frappe.TimestampMismatchError,
		)


def _doc(code, name, modified, perm):
	doctype, _champ, parent, *_rest = _liste(code)
	doc = frappe.get_doc(doctype, name)
	if parent and cint(doc.is_group):
		frappe.throw(_("Ce groupe ne se modifie que sur le Desk."))
	doc.check_permission(perm)
	_stale(doc, modified)
	return doc


@frappe.whitelist(methods=["POST"])
def create_valeur(code, nom):
	require_bureau()
	doctype, champ, parent, *_rest = _liste(code)
	frappe.has_permission(doctype, "create", throw=True)
	nom = _nom(nom)
	if frappe.db.exists(doctype, nom):
		frappe.throw(_("« {0} » existe déjà.").format(nom))
	doc = frappe.new_doc(doctype)
	doc.set(champ, nom)
	if parent:
		doc.set(parent, _racine(code))
		doc.is_group = 0
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
		frappe.throw(_("« {0} » est déjà utilisée et ne peut pas être renommée : créez une nouvelle valeur.").format(doc.name))
	doc.check_permission("delete")
	frappe.delete_doc(doc.doctype, doc.name)
	return create_valeur(code, nom)


@frappe.whitelist(methods=["POST"])
def delete_valeur(code, name, modified):
	require_bureau()
	doc = _doc(code, name, modified, "delete")
	if _usages(code).get(doc.name):
		frappe.throw(_("« {0} » est utilisée : renommez-la plutôt.").format(doc.name))
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
		name for name in frappe.get_all(UNITE, filters={"enabled": 1}, pluck="name", limit_page_length=0) if not usages.get(name)
	]
	for name in noms:
		doc = frappe.get_doc(UNITE, name)
		doc.check_permission("write")
		doc.enabled = 0
		doc.save()
	return {"desactivees": len(noms), "valeurs": _valeurs("unites")}
