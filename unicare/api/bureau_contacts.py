# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Contacts d'un client ou d'un fournisseur, gérés depuis leur fiche du bureau (sans passer par le Desk).

Un contact est un document Contact d'ERPNext, relié au tiers par un lien dynamique. Le téléphone et l'e-mail vont dans
ses lignes (`phone_nos`, `email_ids`), dont ERPNext tire le mobile et l'e-mail principal. Le droit d'écrire se lit sur
le tiers : qui peut modifier le client peut gérer ses contacts.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr

from unicare.api.bureau_list import _parse
from unicare.api.bureau_postes import require_bureau

TIERS = {"Customer", "Supplier"}


def _tiers(link_doctype, link_name):
	require_bureau()
	if link_doctype not in TIERS:
		frappe.throw(_("Contacts : tiers inconnu."))
	doc = frappe.get_doc(link_doctype, link_name)
	doc.check_permission("write")
	return doc


def _linked(contact, link_doctype, link_name):
	return any(row.link_doctype == link_doctype and row.link_name == link_name for row in contact.links)


def _set_primary(link_doctype, link_name, contact_name):
	"""Un seul contact principal par tiers ; pour un fournisseur, il devient aussi son contact principal."""
	others = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "link_doctype": link_doctype, "link_name": link_name, "parent": ["!=", contact_name]},
		pluck="parent",
	)
	for name in others:
		if frappe.db.get_value("Contact", name, "is_primary_contact"):
			frappe.db.set_value("Contact", name, "is_primary_contact", 0)
	if link_doctype == "Supplier":
		frappe.db.set_value("Supplier", link_name, "supplier_primary_contact", contact_name)


@frappe.whitelist(methods=["POST"])
def save_contact(link_doctype, link_name, contact=None, values=None):
	"""Crée (sans `contact`) ou modifie un contact du tiers : prénom, nom, fonction, téléphone, e-mail, principal."""
	_tiers(link_doctype, link_name)
	values = _parse(values) or {}
	prenom = cstr(values.get("prenom")).strip()
	nom = cstr(values.get("nom")).strip()
	if not prenom and not nom:
		frappe.throw(_("Indiquez au moins le prénom ou le nom du contact."))
	telephone = cstr(values.get("telephone")).strip()
	email = cstr(values.get("email")).strip()
	if email and not frappe.utils.validate_email_address(email):
		frappe.throw(_("L'adresse e-mail {0} n'est pas valide.").format(email))
	if contact:
		doc = frappe.get_doc("Contact", contact)
		if not _linked(doc, link_doctype, link_name):
			frappe.throw(_("Ce contact n'appartient pas à ce tiers."), frappe.PermissionError)
	else:
		doc = frappe.new_doc("Contact")
		doc.append("links", {"link_doctype": link_doctype, "link_name": link_name})
	doc.first_name = prenom or nom
	doc.last_name = nom if prenom else None
	doc.designation = cstr(values.get("fonction")).strip() or None
	doc.set("phone_nos", [{"phone": telephone, "is_primary_mobile_no": 1, "is_primary_phone": 1}] if telephone else [])
	doc.set("email_ids", [{"email_id": email, "is_primary": 1}] if email else [])
	doc.is_primary_contact = 1 if cint(values.get("principal")) else 0
	doc.flags.ignore_permissions = True
	doc.save()
	if doc.is_primary_contact:
		_set_primary(link_doctype, link_name, doc.name)
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def delete_contact(link_doctype, link_name, contact):
	"""Retire le contact du tiers ; s'il n'est relié à rien d'autre, il est supprimé."""
	_tiers(link_doctype, link_name)
	doc = frappe.get_doc("Contact", contact)
	if not _linked(doc, link_doctype, link_name):
		frappe.throw(_("Ce contact n'appartient pas à ce tiers."), frappe.PermissionError)
	if link_doctype == "Supplier" and frappe.db.get_value("Supplier", link_name, "supplier_primary_contact") == doc.name:
		frappe.db.set_value("Supplier", link_name, "supplier_primary_contact", None)
	remaining = [row for row in doc.links if not (row.link_doctype == link_doctype and row.link_name == link_name)]
	if remaining:
		doc.set("links", remaining)
		doc.flags.ignore_permissions = True
		doc.save()
	else:
		frappe.delete_doc("Contact", doc.name, ignore_permissions=True)
	return {"deleted": contact}
