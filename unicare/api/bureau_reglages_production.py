# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Réglages de la production (/bureau/reglages-production) : checklists avant production et paramètres.

Les checklists sont des modèles : chaque ordre en reçoit une copie à sa création, qu'on coche à l'atelier. Les
paramètres (single « Parametres Conditionnement ») donnent les dépôts repris par chaque nouvel ordre et l'écart de
rendement toléré. Modifiables par qui a le droit d'écrire (le Responsable Conditionnement) ; lisibles par les autres.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

from unicare.api.bureau_list import _parse
from unicare.api.bureau_postes import require_bureau
from unicare.api.bureau_stock import depots

CHECKLIST = "Checklist Ordre Conditionnement"
PARAMETRES = "Parametres Conditionnement"
ORDRE = "Ordre de Conditionnement"
DEPOTS = ("warehouse_mp", "warehouse_conditionnement", "warehouse_atelier", "warehouse_pf", "warehouse_rebuts")


def _checklist(doc):
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"actif": bool(cint(doc.actif)),
		"lignes": [{"controle": row.controle, "obligatoire": bool(cint(row.obligatoire))} for row in doc.lignes],
		"ordres": frappe.db.count(ORDRE, {"modele_checklist": doc.name}),
	}


@frappe.whitelist()
def get_reglages():
	require_bureau()
	frappe.has_permission(CHECKLIST, "read", throw=True)
	parametres = frappe.get_single(PARAMETRES)
	return {
		"checklists": [_checklist(frappe.get_doc(CHECKLIST, name)) for name in frappe.get_list(CHECKLIST, order_by="name asc", pluck="name")],
		"parametres": {
			"modified": str(parametres.modified),
			**{field: parametres.get(field) for field in DEPOTS},
			"tolerance": flt(parametres.rendement_tolerance_pct),
		},
		"depots": depots(),
		"can_edit_checklists": bool(frappe.has_permission(CHECKLIST, "write")),
		"can_create_checklists": bool(frappe.has_permission(CHECKLIST, "create")),
		"can_edit_parametres": bool(frappe.has_permission(PARAMETRES, "write")),
	}


def _stale(doc, modified):
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(_("Ces réglages viennent d'être modifiés par ailleurs. Ils ont été rechargés : vérifiez-les, puis recommencez."), frappe.TimestampMismatchError)


def _lignes(values):
	lignes = []
	for ligne in values.get("lignes") or []:
		controle = cstr((ligne or {}).get("controle")).strip()
		if controle:
			lignes.append({"controle": controle, "obligatoire": 0 if ligne.get("obligatoire") is False else 1})
	if not lignes:
		frappe.throw(_("Une checklist doit avoir au moins un contrôle."))
	return lignes


@frappe.whitelist(methods=["POST"])
def save_checklist(name=None, modified=None, values=None):
	"""Crée (sans `name`) ou modifie une checklist : son nom (à la création), ses contrôles, et si elle est proposée."""
	require_bureau()
	values = _parse(values) or {}
	if name:
		doc = frappe.get_doc(CHECKLIST, name)
		doc.check_permission("write")
		_stale(doc, modified)
	else:
		frappe.has_permission(CHECKLIST, "create", throw=True)
		titre = cstr(values.get("titre")).strip()
		if not titre:
			frappe.throw(_("Donnez un nom à la checklist."))
		if frappe.db.exists(CHECKLIST, titre):
			frappe.throw(_("Une checklist s'appelle déjà « {0} ».").format(titre))
		doc = frappe.new_doc(CHECKLIST)
		doc.titre = titre
	doc.actif = 0 if values.get("actif") is False else 1
	doc.set("lignes", _lignes(values))
	doc.save() if name else doc.insert()
	return get_reglages()


@frappe.whitelist(methods=["POST"])
def delete_checklist(name, modified):
	require_bureau()
	doc = frappe.get_doc(CHECKLIST, name)
	doc.check_permission("delete")
	_stale(doc, modified)
	if frappe.db.exists(ORDRE, {"modele_checklist": name}):
		frappe.throw(_("Des ordres utilisent cette checklist : rendez-la inactive plutôt."))
	frappe.delete_doc(CHECKLIST, name)
	return get_reglages()


@frappe.whitelist(methods=["POST"])
def save_parametres(modified, values=None):
	require_bureau()
	doc = frappe.get_single(PARAMETRES)
	doc.check_permission("write")
	_stale(doc, modified)
	values = _parse(values) or {}
	connus = set(depots())
	for field in DEPOTS:
		depot = cstr(values.get(field)).strip()
		if depot and depot not in connus:
			frappe.throw(_("Dépôt inconnu ou désactivé : {0}.").format(depot))
		doc.set(field, depot or None)
	tolerance = flt(values.get("tolerance"))
	if tolerance <= 0 or tolerance > 100:
		frappe.throw(_("L'écart toléré est un pourcentage entre 1 et 100."))
	doc.rendement_tolerance_pct = tolerance
	doc.save()
	return get_reglages()
