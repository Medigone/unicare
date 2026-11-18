# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Réglages, page Utilisateurs (/bureau/utilisateurs) : les comptes, leurs rôles et leur mot de passe.

Seuls les rôles utiles au bureau sont proposés, regroupés par domaine et décrits en clair (ROLES). Les autres rôles
d'un compte (posés sur le Desk) sont conservés tels quels. Entrer dans le bureau demande un rôle d'un poste ouvert
(bureau_postes.BUREAU_ROLES). Garde-fous : on ne se désactive pas soi-même et on ne se retire pas l'administration.
Droits : ceux d'ERPNext sur User (en pratique, le rôle System Manager).
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, validate_email_address

from unicare.api.bureau_list import _parse
from unicare.api.bureau_postes import BUREAU_ROLES, require_bureau

USER = "User"
ADMIN = "System Manager"
CACHES = ("Administrator", "Guest")

# (domaine, ((rôle, libellé, ce qu'il permet), …))
ROLES = (
	(
		"Production",
		(
			("Opérateur Conditionnement", "Opérateur", "Le travail à l'atelier sur les ordres de conditionnement."),
			("Magasinier Conditionnement", "Magasinier", "Les matières et produits finis autour des ordres."),
			("Responsable Conditionnement", "Responsable production", "Les ordres, les recettes et les réglages de la production."),
		),
	),
	(
		"Ventes",
		(
			("Sales User", "Commercial", "Devis, commandes, livraisons et clients."),
			("Sales Manager", "Responsable ventes", "Comme le commercial, avec les droits de responsable d'ERPNext."),
		),
	),
	(
		"Achats",
		(
			("Purchase User", "Acheteur", "Devis fournisseur, commandes d'achat, réceptions et fournisseurs."),
			("Purchase Manager", "Responsable achats", "Comme l'acheteur, avec les droits de responsable d'ERPNext."),
		),
	),
	(
		"Stock",
		(
			("Stock User", "Magasinier stock", "Mouvements, inventaires, lots et état du stock."),
			("Stock Manager", "Responsable stock", "Comme le magasinier, avec les droits de responsable d'ERPNext."),
			("Item Manager", "Gestion des articles", "Créer et modifier les fiches articles."),
		),
	),
	(
		"Comptabilité",
		(
			("Accounts User", "Comptable", "Factures, encaissements et paiements."),
			("Accounts Manager", "Responsable comptable", "Comme le comptable, avec les réglages de la comptabilité."),
		),
	),
	(
		"Administration",
		(("System Manager", "Administrateur", "Tous les droits, dont les utilisateurs et tous les réglages."),),
	),
)
GERES = [role for _domaine, rows in ROLES for role, _label, _aide in rows]


def _roles_existants():
	return set(frappe.get_all("Role", filters={"name": ["in", GERES], "disabled": 0}, pluck="name"))


def _utilisateur(row, roles):
	geres = [role for role in GERES if role in roles]
	return {
		"name": row.name,
		"nom": row.full_name or row.name,
		"prenom": row.first_name or "",
		"nom_famille": row.last_name or "",
		"actif": bool(cint(row.enabled)),
		"derniere_connexion": str(row.last_login) if row.last_login else None,
		"roles": geres,
		"autres_roles": len(set(roles) - set(GERES)),
		"acces_bureau": bool(set(roles) & BUREAU_ROLES),
		"moi": row.name == frappe.session.user,
		"modified": str(row.modified),
	}


@frappe.whitelist()
def get_utilisateurs():
	require_bureau()
	frappe.has_permission(USER, "read", throw=True)
	rows = frappe.get_all(
		USER,
		filters={"user_type": "System User", "name": ["not in", CACHES]},
		fields=["name", "full_name", "first_name", "last_name", "enabled", "last_login", "modified"],
		order_by="enabled desc, full_name asc",
	)
	roles = {}
	for row in frappe.get_all(
		"Has Role", filters={"parenttype": USER, "parent": ["in", [r.name for r in rows] or [""]]}, fields=["parent", "role"]
	):
		roles.setdefault(row.parent, []).append(row.role)
	existants = _roles_existants()
	return {
		"utilisateurs": [_utilisateur(row, roles.get(row.name, [])) for row in rows],
		"roles": [
			{
				"domaine": domaine,
				"roles": [{"role": role, "label": label, "aide": aide} for role, label, aide in rows if role in existants],
			}
			for domaine, rows in ROLES
		],
		"roles_bureau": sorted(BUREAU_ROLES & existants),
		"droits": {
			"creer": bool(frappe.has_permission(USER, "create")),
			"modifier": bool(frappe.has_permission(USER, "write")),
		},
	}


def _stale(doc, modified):
	if cstr(modified) != str(doc.modified):
		frappe.throw(
			_("Ce compte vient d'être modifié par ailleurs. La liste a été rechargée : vérifiez, puis recommencez."),
			frappe.TimestampMismatchError,
		)


def _mot_de_passe(doc, mot_de_passe):
	"""Pose le mot de passe ; la politique de mots de passe du site s'applique à l'enregistrement."""
	mot_de_passe = cstr(mot_de_passe)
	if len(mot_de_passe) < 8:
		frappe.throw(_("Le mot de passe doit faire au moins 8 caractères."))
	doc.new_password = mot_de_passe


@frappe.whitelist(methods=["POST"])
def save_utilisateur(name=None, modified=None, values=None):
	"""Crée (sans `name`, avec un mot de passe) ou modifie un compte : nom, actif, rôles proposés."""
	require_bureau()
	values = _parse(values) or {}
	if name:
		if name in CACHES:
			frappe.throw(_("Ce compte ne se modifie pas ici."))
		doc = frappe.get_doc(USER, name)
		doc.check_permission("write")
		_stale(doc, modified)
	else:
		frappe.has_permission(USER, "create", throw=True)
		email = cstr(values.get("email")).strip().lower()
		if not email or not validate_email_address(email):
			frappe.throw(_("Adresse e-mail invalide : elle sert d'identifiant de connexion."))
		if frappe.db.exists(USER, email):
			frappe.throw(_("Un compte existe déjà pour {0}.").format(email))
		doc = frappe.new_doc(USER)
		doc.update({"email": email, "user_type": "System User", "send_welcome_email": 0})
		_mot_de_passe(doc, values.get("mot_de_passe"))

	prenom = cstr(values.get("prenom")).strip()
	if not prenom:
		frappe.throw(_("Indiquez au moins le prénom."))
	doc.first_name = prenom
	doc.last_name = cstr(values.get("nom_famille")).strip() or None

	moi = doc.name == frappe.session.user
	actif = values.get("actif") is not False
	if moi and not actif:
		frappe.throw(_("Vous ne pouvez pas désactiver votre propre compte."))
	doc.enabled = 1 if actif else 0

	if "roles" in values:
		existants = _roles_existants()
		voulus = {role for role in values.get("roles") or [] if role in existants}
		inconnus = set(values.get("roles") or []) - existants
		if inconnus:
			frappe.throw(_("Rôle inconnu : {0}.").format(", ".join(sorted(inconnus))))
		if moi and ADMIN in {r.role for r in doc.get("roles") or []} and ADMIN not in voulus:
			frappe.throw(_("Vous ne pouvez pas retirer votre propre rôle Administrateur."))
		# Les rôles non proposés ici (posés sur le Desk) restent tels quels.
		garder = [r.role for r in doc.get("roles") or [] if r.role not in GERES]
		doc.set("roles", [{"role": role} for role in garder + [r for r in GERES if r in voulus]])

	doc.save() if name else doc.insert()
	return get_utilisateurs()


@frappe.whitelist(methods=["POST"])
def set_mot_de_passe(name, modified, mot_de_passe):
	"""Remplace le mot de passe d'un compte (à lui communiquer ; il pourra le changer ensuite)."""
	require_bureau()
	if name in CACHES:
		frappe.throw(_("Ce compte ne se modifie pas ici."))
	doc = frappe.get_doc(USER, name)
	doc.check_permission("write")
	_stale(doc, modified)
	_mot_de_passe(doc, mot_de_passe)
	doc.save()
	return get_utilisateurs()
