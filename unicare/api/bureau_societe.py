# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Réglages > Société : l'identité imprimée sur les pièces (raison sociale, logo, adresse, RC, NIF, NIS, AI, banque).

Les champs vivent sur la fiche Société (champs `unicare_*`, unicare/unicare/custom/company.json, plus le logo, le
téléphone, l'e-mail et le site de la fiche standard). Les huit mentions qu'exige le décret exécutif 05-468 sur la
facture sont suivies ; une mention vide s'imprime « — ».
"""

import re

import frappe
from frappe import _
from frappe.utils import cstr, flt

from unicare.api.bureau_postes import require_bureau

COMPANY = "Company"

# champ du bureau → champ de la fiche Société
CHAMPS = {
	"raison_sociale": "unicare_raison_sociale",
	"forme_juridique": "unicare_forme_juridique",
	"capital_social": "unicare_capital_social",
	"adresse": "unicare_adresse",
	"wilaya": "unicare_wilaya",
	"commune": "unicare_commune",
	"telephone": "phone_no",
	"email": "email",
	"site_web": "website",
	"rc": "unicare_rc",
	"nif": "unicare_nif",
	"nis": "unicare_nis",
	"ai": "unicare_ai",
	"banque": "unicare_banque",
	"rib": "unicare_rib",
}
MENTIONS = [
	("raison_sociale", "Raison sociale"),
	("forme_juridique", "Forme juridique"),
	("capital_social", "Capital social"),
	("adresse", "Adresse du siège"),
	("rc", "RC"),
	("nif", "NIF"),
	("nis", "NIS"),
	("ai", "AI"),
]
# Identifiants faits de chiffres, et leur longueur habituelle : une autre longueur avertit sans bloquer.
CHIFFRES = {"nif": ("NIF", 15), "nis": ("NIS", 15), "ai": ("AI", 11), "rib": ("RIB", 20)}
LOGO_MAX = 2 * 1024 * 1024
LOGO_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def _societe():
	nom = (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or (frappe.get_all(COMPANY, pluck="name", limit=1) or [None])[0]
	)
	if not nom:
		frappe.throw(_("Aucune société n'est créée."))
	return frappe.get_doc(COMPANY, nom)


def _peut_modifier():
	return bool(frappe.has_permission(COMPANY, "write"))


def _modifier():
	require_bureau()
	if not _peut_modifier():
		frappe.throw(
			_("Votre compte ne peut pas modifier les informations de la société."), frappe.PermissionError
		)


def _stale(doc, modified):
	if cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Les informations de la société viennent d'être modifiées par ailleurs. Elles ont été rechargées : vérifiez-les, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)


def _rempli(valeur):
	return bool(flt(valeur)) if isinstance(valeur, int | float) else bool(cstr(valeur).strip())


def _communes(wilaya):
	if not wilaya:
		return []
	return frappe.get_all("Commune", filters={"wilaya": wilaya}, fields=["name", "nom"], order_by="nom asc")


def _payload(doc, avertissements=None):
	valeurs = {
		cle: doc.get(champ) if champ != "unicare_capital_social" else flt(doc.get(champ))
		for cle, champ in CHAMPS.items()
	}
	valeurs["raison_sociale"] = valeurs["raison_sociale"] or ""
	return {
		"name": doc.name,
		"nom_erp": doc.company_name,
		"modified": str(doc.modified),
		"valeurs": {cle: (valeur if valeur is not None else "") for cle, valeur in valeurs.items()},
		"logo": doc.company_logo or "",
		"wilayas": frappe.get_all("Wilaya", fields=["name", "nom", "code"], order_by="code asc, nom asc"),
		"communes": _communes(doc.get("unicare_wilaya")),
		"mentions": [
			{"cle": cle, "label": label, "ok": _rempli(valeurs.get(cle))} for cle, label in MENTIONS
		],
		"peut_modifier": _peut_modifier(),
		"avertissements": avertissements or [],
	}


@frappe.whitelist()
def get_societe():
	require_bureau()
	doc = _societe()
	doc.check_permission("read")
	return _payload(doc)


@frappe.whitelist()
def get_communes(wilaya=None):
	require_bureau()
	return _communes(cstr(wilaya))


def _nettoyer(cle, valeur):
	"""La valeur saisie, espaces de trop retirés ; les identifiants chiffrés vérifiés."""
	if cle == "capital_social":
		texte = re.sub(r"\s", "", cstr(valeur)).replace(",", ".")
		if texte and not re.fullmatch(r"\d+(\.\d+)?", texte):
			frappe.throw(_("Le capital social s'écrit en chiffres, par exemple 1000000."))
		return flt(texte)
	texte = " ".join(cstr(valeur).split())
	if cle in CHIFFRES and texte and not re.fullmatch(r"[\d ]+", texte):
		frappe.throw(_("Le {0} ne contient que des chiffres.").format(CHIFFRES[cle][0]))
	if cle == "email" and texte and not frappe.utils.validate_email_address(texte):
		frappe.throw(_("L'adresse e-mail « {0} » n'est pas valide.").format(texte))
	return texte


def _ecrire(doc, changes):
	"""Écrit les champs sans passer par l'enregistrement complet de la Société : ses hooks (départements,
	comptes par défaut…) n'ont rien à voir avec ces informations et journalisent des erreurs sur certains sites."""
	doc.db_set(changes, update_modified=True)
	frappe.clear_document_cache(COMPANY, doc.name)
	doc.reload()


def _avertissements(doc):
	sortie = []
	for cle, (libelle, longueur) in CHIFFRES.items():
		chiffres = re.sub(r"\D", "", cstr(doc.get(CHAMPS[cle])))
		if chiffres and len(chiffres) != longueur:
			sortie.append(
				_("Le {0} compte {1} chiffres ; on en attend d'habitude {2}.").format(
					libelle, len(chiffres), longueur
				)
			)
	return sortie


@frappe.whitelist()
def save_societe(modified, valeurs):
	_modifier()
	doc = _societe()
	_stale(doc, modified)
	valeurs = frappe.parse_json(valeurs) if isinstance(valeurs, str) else (valeurs or {})
	changes = {CHAMPS[cle]: _nettoyer(cle, valeur) for cle, valeur in valeurs.items() if cle in CHAMPS}
	if "unicare_raison_sociale" in changes and not changes["unicare_raison_sociale"]:
		frappe.throw(_("La raison sociale est obligatoire : c'est le nom imprimé sur toutes les pièces."))
	wilaya = changes.get("unicare_wilaya", doc.get("unicare_wilaya")) or None
	commune = changes.get("unicare_commune", doc.get("unicare_commune")) or None
	if wilaya and not frappe.db.exists("Wilaya", wilaya):
		frappe.throw(_("La wilaya « {0} » n'existe pas.").format(wilaya))
	if commune and (
		not frappe.db.exists("Commune", commune)
		or (wilaya and frappe.db.get_value("Commune", commune, "wilaya") != wilaya)
	):
		commune = None  # une commune d'une autre wilaya ne reste pas
	changes["unicare_wilaya"], changes["unicare_commune"] = wilaya, commune
	_ecrire(doc, changes)
	return _payload(doc, _avertissements(doc))


@frappe.whitelist(methods=["POST"])
def envoyer_logo(modified):
	"""Le logo envoyé (PNG, JPG ou WebP, 2 Mo au plus) devient celui de la société, public : il s'imprime."""
	_modifier()
	doc = _societe()
	_stale(doc, modified)
	fichier = frappe.request.files.get("file") if frappe.request else None
	if not fichier:
		frappe.throw(_("Choisissez une image."))
	enregistrer_logo(doc, fichier.stream.read(), cstr(fichier.mimetype))
	return _payload(doc)


def enregistrer_logo(doc, contenu, mimetype):
	"""Contrôle l'image puis en fait le logo de la société ; l'ancien fichier est supprimé."""
	extension = LOGO_TYPES.get(mimetype)
	if not extension:
		frappe.throw(_("Le logo doit être une image PNG, JPG ou WebP."))
	if len(contenu) > LOGO_MAX:
		frappe.throw(_("Le logo pèse plus de 2 Mo : réduisez-le avant de l'envoyer."))
	ancien = doc.company_logo
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"logo-{frappe.scrub(doc.name)}.{extension}",
			"attached_to_doctype": COMPANY,
			"attached_to_name": doc.name,
			"attached_to_field": "company_logo",
			"is_private": 0,
			"content": contenu,
		}
	).insert(ignore_permissions=True)
	_ecrire(doc, {"company_logo": file_doc.file_url})
	_supprimer_fichier(doc.name, ancien, garder=file_doc.name)


@frappe.whitelist()
def supprimer_logo(modified):
	_modifier()
	doc = _societe()
	_stale(doc, modified)
	ancien = doc.company_logo
	_ecrire(doc, {"company_logo": None})
	_supprimer_fichier(doc.name, ancien)
	return _payload(doc)


def _supprimer_fichier(societe, url, garder=None):
	if not url:
		return
	for nom in frappe.get_all(
		"File",
		filters={"attached_to_doctype": COMPANY, "attached_to_name": societe, "file_url": url},
		pluck="name",
	):
		if nom != garder:
			frappe.delete_doc("File", nom, ignore_permissions=True)


@frappe.whitelist(methods=["GET"])
def apercu_pdf():
	"""Une facture d'exemple (jamais enregistrée) avec les informations actuelles de la société, en PDF."""
	require_bureau()
	societe = _societe()
	client = frappe.get_all("Customer", filters={"disabled": 0}, pluck="name", limit=1)
	article = frappe.get_all(
		"Item", filters={"is_sales_item": 1, "disabled": 0, "has_variants": 0}, pluck="name", limit=1
	)
	if not client or not article:
		frappe.throw(_("Il faut au moins un client et un article pour montrer une facture d'exemple."))
	doc = frappe.new_doc("Sales Invoice")
	doc.company, doc.customer = societe.name, client[0]
	doc.posting_date = frappe.utils.nowdate()
	for i in range(3):
		doc.append("items", {"item_code": article[0], "qty": 10 * (i + 1), "rate": 100 * (i + 1)})
	doc.set_missing_values()
	modele = frappe.db.get_value(
		"Sales Taxes and Charges Template", {"company": societe.name, "is_default": 1}
	)
	if modele and not doc.taxes:
		doc.taxes_and_charges = modele
		doc.set_taxes()
	doc.calculate_taxes_and_totals()
	doc.name = "EXEMPLE"
	pdf = frappe.get_print(
		"Sales Invoice", doc.name, "Unicare Facture", doc=doc, as_pdf=True, no_letterhead=1
	)
	frappe.local.response.filename = "Facture-exemple.pdf"
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"
