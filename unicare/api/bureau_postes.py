# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Postes du bureau (/bureau) : qui y entre, et ce que l'interface doit montrer à chacun.

Un poste choisit le menu et l'accueil. Il n'accorde aucun droit : la sécurité reste celle de Frappe
(`get_list`, `check_permission`, workflow). Ajouter une équipe revient à ajouter un poste ici et son menu
dans `bureau/src/lib/postes.ts` (même clé).
"""

import frappe
from frappe import _

# Un poste fermé est déclaré mais n'ouvre pas encore le bureau à ses rôles.
POSTES = {
	"conditionnement": {
		"label": "Conditionnement",
		"roles": {"Magasinier Conditionnement", "Opérateur Conditionnement", "Responsable Conditionnement"},
		"ouvert": True,
	},
}
ACCES_COMPLET = {"Administrator", "System Manager"}

BUREAU_ROLES = {"System Manager"}.union(*(poste["roles"] for poste in POSTES.values() if poste["ouvert"]))

# Documents dont l'interface a besoin de connaître les droits pour son menu et ses routes.
DOCTYPES_INTERFACE = (
	"Ordre de Conditionnement",
	"Recette de Conditionnement",
	"Checklist Ordre Conditionnement",
	"Parametres Conditionnement",
	"Item",
	"Customer",
	"Supplier",
	"Quotation",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"Payment Entry",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Warehouse",
	"Stock Entry",
	"Stock Reconciliation",
	"Batch",
	"Stock Ledger Entry",
	# Solde des clients : colonne et vue affichées seulement à qui lit la comptabilité.
	"GL Entry",
	# Stock des articles : colonne affichée seulement à qui lit les quantités par dépôt.
	"Bin",
)


def can_access_bureau(user=None):
	user = user or frappe.session.user
	if user == "Guest":
		return False
	roles = set(frappe.get_roles(user))
	return "Administrator" in roles or bool(roles & BUREAU_ROLES)


def require_bureau():
	"""Garde des méthodes du bureau : à appeler en tête de chaque endpoint."""
	if not can_access_bureau():
		frappe.throw(_("Votre compte n'a pas accès au poste de bureau."), frappe.PermissionError)
	return frappe.session.user


def get_postes(user=None):
	"""Postes ouverts de cet utilisateur, dans l'ordre de `POSTES`."""
	user = user or frappe.session.user
	if user == "Guest":
		return []
	roles = set(frappe.get_roles(user))
	complet = bool(roles & ACCES_COMPLET)
	return [
		{"key": key, "label": poste["label"]}
		for key, poste in POSTES.items()
		if poste["ouvert"] and (complet or roles & poste["roles"])
	]


def get_droits(user=None):
	"""Lecture et création par document, pour n'afficher que ce que le serveur acceptera."""
	user = user or frappe.session.user
	if user == "Guest":
		return {}
	return {
		doctype: {
			"read": bool(frappe.has_permission(doctype, "read", user=user)),
			"create": bool(frappe.has_permission(doctype, "create", user=user)),
		}
		for doctype in DOCTYPES_INTERFACE
	}
