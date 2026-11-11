# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Actions groupées communes à toutes les listes du poste de bureau : modifier un champ, supprimer, ajouter des tags.

Même usage que la sélection du Desk, avec trois différences voulues :
- le serveur recalcule les champs modifiables à chaque écriture, plutôt que de faire confiance à l'écran ;
- un champ sans droit d'écriture est refusé, là où `save` remettrait l'ancienne valeur sans rien dire ;
- chaque refus revient avec sa raison : le navigateur envoie des lots courts au lieu d'un travail en arrière-plan.

Seuls les DocTypes de `BULK_DOCTYPES` sont acceptés. Une nouvelle liste s'y déclare en une entrée.
"""

import frappe
from frappe import _
from frappe.desk.doctype.tag.tag import DocTags
from frappe.model.workflow import get_workflow_name
from frappe.utils import cint, cstr, flt, get_datetime, getdate

from unicare.api.bureau_articles import ITEM, TYPE_FIELD, _article_for_write
from unicare.api.bureau_clients import CUSTOMER, _client_for_write
from unicare.api.bureau_commandes import COMMANDE, commande_for_bulk
from unicare.api.bureau_commandes import bulk_guard as commande_guard
from unicare.api.bureau_depots import depot_for_bulk
from unicare.api.bureau_devis import DEVIS, bulk_guard, devis_for_bulk
from unicare.api.bureau_factures import FACTURE, facture_for_bulk
from unicare.api.bureau_factures import bulk_guard as facture_guard
from unicare.api.bureau_commandes_achat import COMMANDE_ACHAT, commande_achat_for_bulk
from unicare.api.bureau_commandes_achat import bulk_guard as commande_achat_guard
from unicare.api.bureau_devis_fournisseur import DEVIS_F, devis_fournisseur_for_bulk
from unicare.api.bureau_devis_fournisseur import bulk_guard as devis_fournisseur_guard
from unicare.api.bureau_factures_achat import FACTURE_ACHAT, facture_achat_for_bulk
from unicare.api.bureau_factures_achat import bulk_guard as facture_achat_guard
from unicare.api.bureau_fournisseurs import SUPPLIER, _fournisseur_for_write
from unicare.api.bureau_list import _bulk_apply, _parse, link_search_values, row_tags
from unicare.api.bureau_livraisons import LIVRAISON, livraison_for_bulk
from unicare.api.bureau_lots import lot_for_bulk
from unicare.api.bureau_mouvements import bulk_guard as mouvement_guard
from unicare.api.bureau_mouvements import mouvement_for_bulk
from unicare.api.bureau_livraisons import bulk_guard as livraison_guard
from unicare.api.bureau_paiements import PAIEMENT, paiement_for_bulk
from unicare.api.bureau_paiements import bulk_guard as paiement_guard
from unicare.api.bureau_postes import require_bureau
from unicare.api.bureau_receptions import RECEPTION, reception_for_bulk
from unicare.api.bureau_receptions import bulk_guard as reception_guard

TEXT_TYPES = {"Data", "Small Text", "Text", "Long Text"}
NUMBER_TYPES = {"Float", "Currency", "Percent"}
# Les autres types du Desk (éditeur riche, fichier, signature…) n'ont pas de saisie ici : ils restent sur la fiche.
FIELD_TYPES = TEXT_TYPES | NUMBER_TYPES | {"Select", "Link", "Date", "Datetime", "Check", "Int"}

LINK_SEARCH_LIMIT = 8
TAG_LENGTH = 140


# load : charge un document et contrôle droits et version.
# excluded : champs dont l'écriture a ses propres règles, ailleurs que dans `save`.
# setters : champs écrits par une fonction métier. Ils sont proposés même masqués sur le formulaire, et ne se vident pas.
# guard : facultatif. `guard(doc, operation)` donne la raison de refuser une modification ou une suppression ; les tags n'y passent pas.
BULK_DOCTYPES = {
	CUSTOMER: {
		"load": _client_for_write,
		"excluded": {"customer_name"},  # propre à chaque client
		"setters": {},
	},
	SUPPLIER: {
		"load": _fournisseur_for_write,
		"excluded": {"supplier_name"},  # propre à chaque fournisseur
		"setters": {},
	},
	ITEM: {
		"load": _article_for_write,
		# Propres à chaque article ; le type a fixé le code, il ne change plus.
		"excluded": {"item_name", "item_code", "description", TYPE_FIELD},
		"setters": {},
	},
	DEVIS: {
		"load": devis_for_bulk,
		# Le client, les dates et la TVA se changent sur la fiche, avec leurs contrôles.
		"excluded": {
			"party_name",
			"quotation_to",
			"transaction_date",
			"valid_till",
			"taxes_and_charges",
			"company",
		},
		"setters": {},
		"guard": bulk_guard,
	},
	COMMANDE: {
		"load": commande_for_bulk,
		# Le client, les dates et la TVA se changent sur la fiche, avec leurs contrôles.
		"excluded": {"customer", "transaction_date", "delivery_date", "taxes_and_charges", "company"},
		"setters": {},
		"guard": commande_guard,
	},
	LIVRAISON: {
		"load": livraison_for_bulk,
		# Client, dates, lignes et retours se règlent sur la fiche.
		"excluded": {"customer", "posting_date", "posting_time", "is_return", "return_against", "company"},
		"setters": {},
		"guard": livraison_guard,
	},
	FACTURE: {
		"load": facture_for_bulk,
		# Client, dates, montants et avoirs se règlent sur la fiche.
		"excluded": {
			"customer",
			"posting_date",
			"due_date",
			"is_return",
			"return_against",
			"company",
			"taxes_and_charges",
		},
		"setters": {},
		"guard": facture_guard,
	},
	DEVIS_F: {
		"load": devis_fournisseur_for_bulk,
		# Le fournisseur, les dates et la TVA se changent sur la fiche, avec leurs contrôles.
		"excluded": {"supplier", "transaction_date", "valid_till", "taxes_and_charges", "company"},
		"setters": {},
		"guard": devis_fournisseur_guard,
	},
	COMMANDE_ACHAT: {
		"load": commande_achat_for_bulk,
		# Le fournisseur, les dates et la TVA se changent sur la fiche, avec leurs contrôles.
		"excluded": {"supplier", "transaction_date", "schedule_date", "taxes_and_charges", "company"},
		"setters": {},
		"guard": commande_achat_guard,
	},
	RECEPTION: {
		"load": reception_for_bulk,
		# Fournisseur, dates, lignes et retours se règlent sur la fiche.
		"excluded": {"supplier", "posting_date", "posting_time", "is_return", "return_against", "company"},
		"setters": {},
		"guard": reception_guard,
	},
	FACTURE_ACHAT: {
		"load": facture_achat_for_bulk,
		# Fournisseur, dates, montants et avoirs se règlent sur la fiche.
		"excluded": {
			"supplier",
			"posting_date",
			"due_date",
			"bill_no",
			"is_return",
			"return_against",
			"company",
			"taxes_and_charges",
		},
		"setters": {},
		"guard": facture_achat_guard,
	},
	"Stock Entry": {
		"load": mouvement_for_bulk,
		# Nature, dépôts, lignes et ordre se règlent sur la fiche, avec leurs contrôles.
		"excluded": {
			"purpose",
			"stock_entry_type",
			"from_warehouse",
			"to_warehouse",
			"posting_date",
			"posting_time",
			"company",
			"custom_ordre_conditionnement",
		},
		"setters": {},
		"guard": mouvement_guard,
	},
	"Batch": {
		"load": lot_for_bulk,
		# L'identité du lot (article, numéro, quantité, origine) vient des pièces : elle ne change pas en groupe.
		"excluded": {
			"batch_id",
			"item",
			"item_name",
			"batch_qty",
			"stock_uom",
			"custom_origine",
			"custom_ordre_conditionnement",
			"allow_negative_stock_for_batch",
			"reference_doctype",
			"reference_name",
			"parent_batch",
		},
		"setters": {},
	},
	"Warehouse": {
		"load": depot_for_bulk,
		# Le nom, la société et la nature (groupe ou non) sont fixés à la création ; le compte se règle sur le Desk.
		"excluded": {"warehouse_name", "company", "is_group", "account", "lft", "rgt", "old_parent"},
		"setters": {},
	},
	PAIEMENT: {
		"load": paiement_for_bulk,
		# Tiers, montants, comptes et affectations se règlent dans l'assistant.
		"excluded": {
			"payment_type",
			"party_type",
			"party",
			"paid_amount",
			"received_amount",
			"paid_from",
			"paid_to",
			"posting_date",
			"company",
		},
		"setters": {},
		"guard": paiement_guard,
	},
}


def _config(doctype):
	config = BULK_DOCTYPES.get(cstr(doctype))
	if not config:
		frappe.throw(_("Cette liste n'a pas d'action groupée."), frappe.PermissionError)
	return config


def _guard(config, doc, operation):
	guard = config.get("guard")
	return guard(doc, operation) if guard else None


def _workflow_field(doctype):
	workflow = get_workflow_name(doctype)
	return frappe.get_cached_value("Workflow", workflow, "workflow_state_field") if workflow else None


def _editable_fields(doctype):
	"""Critères du Desk, plus ce que `save` refuserait ou écraserait : le champ n'est alors même pas proposé."""
	config = _config(doctype)
	meta = frappe.get_meta(doctype)
	levels = meta.get_permlevel_access("write")
	state_field = _workflow_field(doctype)

	def eligible(df):
		if (
			df.fieldname in config["excluded"]
			or df.fieldname == state_field
			or df.fieldtype not in FIELD_TYPES
		):
			return False
		if df.permlevel not in levels:
			return False
		if df.fieldname in config["setters"]:
			return True
		if df.hidden or df.read_only or df.is_virtual or df.set_only_once:
			return False
		# Recopié depuis un autre document à chaque enregistrement : la valeur saisie serait perdue.
		return not (df.fetch_from and not df.fetch_if_empty)

	return [df for df in meta.fields if eligible(df)]


def _field_payload(df, doctype):
	options = (
		[option for option in cstr(df.options).split("\n") if option] if df.fieldtype == "Select" else []
	)
	return {
		"fieldname": df.fieldname,
		"label": _(df.label or df.fieldname),
		"fieldtype": df.fieldtype,
		"options": options,
		"required": bool(df.reqd or df.fieldname in _config(doctype)["setters"]),
	}


@frappe.whitelist()
def get_bulk_options(doctype):
	"""Ce que la barre d'actions peut proposer à cette personne sur cette liste."""
	require_bureau()
	return {
		"fields": [_field_payload(df, doctype) for df in _editable_fields(doctype)],
		"can_delete": bool(frappe.has_permission(doctype, "delete")),
	}


def _editable_field(doctype, fieldname):
	for df in _editable_fields(doctype):
		if df.fieldname == fieldname:
			return df
	frappe.throw(_("Ce champ ne se modifie pas sur plusieurs lignes."), frappe.PermissionError)


def _clean_value(df, value, required):
	"""Valeur saisie au format du champ. Une erreur de saisie refuse toute la demande, avant d'écrire quoi que ce soit."""
	empty = value is None or cstr(value).strip() == ""
	if df.fieldtype == "Check":
		return cint(value)
	if empty:
		if required:
			frappe.throw(_("Le champ {0} est obligatoire.").format(_(df.label)))
		return None
	if df.fieldtype == "Int" or df.fieldtype in NUMBER_TYPES:
		try:
			return int(value) if df.fieldtype == "Int" else float(value)
		except (TypeError, ValueError):
			frappe.throw(_("Le champ {0} attend un nombre.").format(_(df.label)))
	try:
		if df.fieldtype == "Date":
			return str(getdate(value))
		if df.fieldtype == "Datetime":
			return str(get_datetime(value))
	except Exception:
		frappe.throw(_("Le champ {0} attend une date.").format(_(df.label)))
	return cstr(value).strip()


def _same(df, left, right):
	if df.fieldtype == "Check" or df.fieldtype == "Int" or df.fieldtype in NUMBER_TYPES:
		return flt(left) == flt(right)
	return cstr(left) == cstr(right)


@frappe.whitelist(methods=["POST"])
def bulk_update(doctype, items, fieldname, value=None):
	"""Donne la même valeur à un champ de plusieurs documents, avec les validations et les hooks de `save`."""
	require_bureau()
	config = _config(doctype)
	df = _editable_field(doctype, cstr(fieldname))
	setter = config["setters"].get(df.fieldname)
	value = _clean_value(df, value, bool(df.reqd or setter))

	def apply(doc):
		if doc.docstatus == 2:
			return _("Document annulé.")
		refusal = _guard(config, doc, "update")
		if refusal:
			return refusal
		before = doc.get(df.fieldname)
		if _same(df, before, value):
			return None
		if setter:
			setter(doc, value)
		else:
			doc.set(df.fieldname, value)
		doc.save()
		# Un hook peut remettre l'ancienne valeur : ne pas annoncer une modification qui n'a pas eu lieu.
		if _same(df, doc.get(df.fieldname), before):
			return _("Cette valeur n'a pas été retenue.")
		return None

	return _bulk_apply(items, apply, config["load"])


@frappe.whitelist(methods=["POST"])
def bulk_delete(doctype, items):
	"""Supprime plusieurs documents. Un document soumis ou lié à d'autres est refusé, avec la raison."""
	require_bureau()
	config = _config(doctype)

	def apply(doc):
		doc.check_permission("delete")
		refusal = _guard(config, doc, "delete")
		if refusal:
			return refusal
		frappe.delete_doc(doc.doctype, doc.name)
		return None

	return _bulk_apply(items, apply, config["load"])


def _clean_tags(tags):
	cleaned = []
	for tag in _parse(tags) or []:
		tag = cstr(tag).strip()
		if "," in tag:
			frappe.throw(_("Un tag ne peut pas contenir de virgule."))
		if len(tag) > TAG_LENGTH:
			frappe.throw(_("Un tag compte au plus {0} caractères.").format(TAG_LENGTH))
		if tag and tag not in cleaned:
			cleaned.append(tag)
	if not cleaned:
		frappe.throw(_("Saisissez au moins un tag."))
	return cleaned


@frappe.whitelist(methods=["POST"])
def bulk_add_tags(doctype, items, tags):
	"""Ajoute des tags à plusieurs documents. La date `modified` ne change pas, comme sur le Desk."""
	require_bureau()
	config = _config(doctype)
	tags = _clean_tags(tags)

	def apply(doc):
		for tag in tags:
			DocTags(doc.doctype).add(doc.name, tag)
		return None

	return _bulk_apply(items, apply, config["load"])


def _current_tags(doctype, name):
	return {"tags": row_tags({"_user_tags": frappe.db.get_value(doctype, name, "_user_tags")})}


@frappe.whitelist(methods=["POST"])
def add_doc_tag(doctype, name, modified, tag):
	"""Ajoute un tag depuis le tiroir ou la fiche. Renvoie les tags du document."""
	require_bureau()
	doc = _config(doctype)["load"](cstr(name), modified)
	for cleaned in _clean_tags([tag]):
		DocTags(doc.doctype).add(doc.name, cleaned)
	return _current_tags(doc.doctype, doc.name)


@frappe.whitelist(methods=["POST"])
def remove_doc_tag(doctype, name, modified, tag):
	"""Retire un tag depuis le tiroir ou la fiche. Renvoie les tags du document."""
	require_bureau()
	doc = _config(doctype)["load"](cstr(name), modified)
	DocTags(doc.doctype).remove(doc.name, cstr(tag))
	return _current_tags(doc.doctype, doc.name)


@frappe.whitelist()
def get_bulk_tags(search=None):
	"""Tags existants, pour les proposer à la saisie."""
	require_bureau()
	return frappe.get_list(
		"Tag",
		filters=[["name", "like", f"%{cstr(search).strip()}%"]],
		pluck="name",
		order_by="name asc",
		limit_page_length=LINK_SEARCH_LIMIT,
	)


@frappe.whitelist()
def search_bulk_link(doctype, fieldname, search=None):
	"""Valeurs possibles d'un champ lien, avec les droits de lecture de la personne sur leur DocType."""
	require_bureau()
	df = _editable_field(doctype, cstr(fieldname))
	if df.fieldtype != "Link":
		frappe.throw(_("Ce champ n'est pas un lien."))
	return link_search_values(df.options, search, LINK_SEARCH_LIMIT)
