# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Versions des pièces du poste de bureau : la nouvelle version d'une pièce annulée, comme « Modifier » sur le Desk.

Une pièce validée ne change plus ; pour la corriger, on l'annule puis on en fait une nouvelle version : un brouillon
`NOM-1`, `NOM-2`… qui la cite dans `amended_from` (nomination de Frappe). Comme le Desk (`frappe.model.copy_doc` avec
`from_amend`), tout est recopié, y compris les liens des lignes vers les pièces d'origine (commande, réception…) ;
les statuts se recalculent à l'enregistrement. Les pièces jointes suivent. Une pièce annulée peut aussi se supprimer,
si plus rien de non annulé ne la cite : Frappe en reste juge.
"""

import frappe
from frappe import _
from frappe.utils import cint


def open_version(doc):
	"""La version non annulée qui remplace déjà cette pièce, s'il y en a une."""
	return frappe.db.get_value(doc.doctype, {"amended_from": doc.name, "docstatus": ["<", 2]}, "name")


# Écritures qu'ERPNext garde, marquées annulées, quand une pièce est annulée : elles la rendent impossible à supprimer.
LEDGERS = ("Stock Ledger Entry", "GL Entry", "Payment Ledger Entry")


def has_ledger(doc):
	"""La pièce a laissé des écritures de stock ou de comptabilité : ERPNext la garde, même annulée (piste d'audit)."""
	return any(frappe.db.exists(ledger, {"voucher_type": doc.doctype, "voucher_no": doc.name}) for ledger in LEDGERS)


def cancelled_actions(doc):
	"""Ce qu'on peut faire d'une pièce annulée : en faire une nouvelle version, ou la supprimer si rien ne la garde."""
	found = []
	if frappe.has_permission(doc.doctype, "amend") and frappe.has_permission(doc.doctype, "create") and not open_version(doc):
		found.append("nouvelle_version")
	if doc.has_permission("delete") and not has_ledger(doc):
		found.append("supprimer")
	return found


def versions(doc):
	"""La pièce d'origine et les versions qui en sont faites, pour la fiche."""

	# Certaines pièces (Stock Entry…) n'ont pas de statut : on le déduit alors de `docstatus`.
	fields = ["name", "docstatus", "status"] if doc.meta.has_field("status") else ["name", "docstatus"]

	def row(name):
		values = frappe.db.get_value(doc.doctype, name, fields, as_dict=True)
		if not values:
			return None
		status = "Draft" if cint(values.docstatus) == 0 else values.get("status") or ("Cancelled" if cint(values.docstatus) == 2 else "Submitted")
		return {"name": values.name, "docstatus": cint(values.docstatus), "status": status}

	origine = row(doc.amended_from) if doc.get("amended_from") else None
	suivantes = [
		row(name)
		for name in frappe.get_all(doc.doctype, filters={"amended_from": doc.name}, pluck="name", order_by="creation asc")
	]
	return {"origine": origine, "suivantes": [entry for entry in suivantes if entry]}


def _replace_disabled_taxes(doc):
	"""Un modèle de TVA désactivé depuis l'annulation bloquerait la nouvelle version : on prend celui par défaut."""
	from erpnext.controllers.accounts_controller import get_taxes_and_charges

	template = doc.get("taxes_and_charges")
	field = doc.meta.get_field("taxes_and_charges")
	if not template or not field or not frappe.db.get_value(field.options, template, "disabled"):
		return None
	default = frappe.db.get_value(field.options, {"company": doc.company, "is_default": 1, "disabled": 0}, "name")
	doc.taxes_and_charges = default
	doc.set("taxes", (get_taxes_and_charges(field.options, default) or []) if default else [])
	return _("Le modèle de TVA « {0} » est désactivé : remplacé par « {1} ». Vérifiez la TVA.").format(
		template, default or _("aucun")
	)


def amend(doc):
	"""Crée la nouvelle version (brouillon) d'une pièce annulée et la renvoie, avec un message s'il y a lieu."""
	if doc.docstatus != 2:
		frappe.throw(_("Seule une pièce annulée peut avoir une nouvelle version."))
	frappe.has_permission(doc.doctype, "amend", throw=True)
	frappe.has_permission(doc.doctype, "create", throw=True)
	existing = open_version(doc)
	if existing:
		frappe.throw(_("La version {0} existe déjà : corrigez-la, ou annulez-la d'abord.").format(existing))
	# Copie complète, comme le Desk : les champs `no_copy` gardent les liens des lignes vers leurs pièces d'origine.
	new = frappe.copy_doc(doc)
	new.amended_from = doc.name
	new.docstatus = 0
	note = _replace_disabled_taxes(new)
	new.insert()
	return {"name": new.name, "note": note}
