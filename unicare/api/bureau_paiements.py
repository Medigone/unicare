# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Paiements du poste de bureau (/bureau/paiements) : liste, aperçu, fiche et assistant de saisie.

Un paiement est un Payment Entry d'ERPNext, de l'un de quatre types : encaissement client, remboursement client
(contre ses avoirs), paiement fournisseur, remboursement fournisseur (contre ses avoirs d'achat). L'assistant
choisit le type, le tiers, le montant et le mode, puis propose de rapprocher le montant des pièces ouvertes du tiers
(échéance la plus ancienne d'abord) ; ce qui n'est pas affecté reste une avance. Il crée un brouillon, que la fiche
relit puis valide. Les règles d'ERPNext restent seules juges : `insert`, `save`, `submit` et `cancel`.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_fullname, getdate, today

from unicare.api import activity
from unicare.api.bureau_devis import _company, _day
from unicare.api.bureau_factures import MODE, _payment_account
from unicare.api.bureau_list import (
	BELL_FIELD,
	_parse,
	condition_filters,
	doctype_filter_fields,
	has_child_filter,
	page_bounds,
	row_bell,
	row_tags,
)
from unicare.api.bureau_postes import require_bureau

PAIEMENT = "Payment Entry"
REFERENCES = "Payment Entry Reference"
PIECES_MAX = 100

# Type de l'assistant → (sens ERPNext, tiers, pièce rapprochée, signe du reste dû rapproché, libellé).
KINDS = {
	"encaissement_client": ("Receive", "Customer", "Sales Invoice", 1, _("Encaissement client")),
	"remboursement_client": ("Pay", "Customer", "Sales Invoice", -1, _("Remboursement client")),
	"paiement_fournisseur": ("Pay", "Supplier", "Purchase Invoice", 1, _("Paiement fournisseur")),
	"remboursement_fournisseur": (
		"Receive",
		"Supplier",
		"Purchase Invoice",
		-1,
		_("Remboursement fournisseur"),
	),
}
PARTY_NAME = {"Customer": "customer_name", "Supplier": "supplier_name"}
PARTY_FIELD = {"Sales Invoice": "customer", "Purchase Invoice": "supplier"}

FIELDS = [
	"name",
	"modified",
	"creation",
	"docstatus",
	"status",
	"payment_type",
	"party_type",
	"party",
	"party_name",
	"posting_date",
	"paid_amount",
	"unallocated_amount",
	"mode_of_payment",
	"reference_no",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "brouillons", "encaissements", "decaissements", "non_affectes", "annules")
SORT_KEYS = {
	"name",
	"tiers_label",
	"date",
	"montant",
	"non_affecte",
	"mode",
	"status",
	"creation",
	"modified",
}


def kind_of(payment_type, party_type):
	"""Type de l'assistant d'un paiement existant. Un remboursement se reconnaît au sens contraire du tiers."""
	if party_type == "Customer":
		return "encaissement_client" if payment_type == "Receive" else "remboursement_client"
	if party_type == "Supplier":
		return "paiement_fournisseur" if payment_type == "Pay" else "remboursement_fournisseur"
	return None


def _status(row):
	return {0: "Draft", 2: "Cancelled"}.get(cint(row.get("docstatus")), "Submitted")


def in_view(view, row):
	if view == "all":
		return True
	if view == "brouillons":
		return row["status"] == "Draft"
	if view == "annules":
		return row["status"] == "Cancelled"
	if row["status"] == "Cancelled":
		return False
	if view == "encaissements":
		return row["sens"] == "Receive"
	if view == "decaissements":
		return row["sens"] == "Pay"
	return row["status"] == "Submitted" and row["non_affecte"] > 0


def _list_row(paiement):
	kind = kind_of(paiement.payment_type, paiement.party_type)
	return {
		"name": paiement.name,
		"modified": paiement.modified,
		"creation": str(paiement.creation),
		"tags": row_tags(paiement),
		"cloche": row_bell(paiement),
		"type": kind,
		"type_label": KINDS[kind][4] if kind else paiement.payment_type,
		"sens": paiement.payment_type,
		"tiers_type": paiement.party_type,
		"tiers": paiement.party,
		"tiers_label": paiement.party_name or paiement.party,
		"date": _day(paiement.posting_date),
		"montant": flt(paiement.paid_amount),
		"non_affecte": flt(paiement.unallocated_amount),
		"mode": paiement.mode_of_payment,
		"reference": paiement.reference_no or None,
		"status": _status(paiement),
	}


def order_paiements(rows, sort=None, direction=None):
	if sort not in SORT_KEYS:
		return sorted(rows, key=lambda row: (cstr(row["date"]), cstr(row["name"])), reverse=True)
	descending = cstr(direction) == "desc"
	ordered = sorted(rows, key=lambda row: cstr(row["name"]), reverse=True)
	filled = [row for row in ordered if row.get(sort) not in (None, "")]
	empty = [row for row in ordered if row.get(sort) in (None, "")]

	def value(row):
		item = row[sort]
		return item if isinstance(item, (int, float)) else cstr(item).casefold()

	return sorted(filled, key=value, reverse=descending) + empty


@frappe.whitelist()
def get_paiements(
	view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None
):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), PAIEMENT)
	paiements = frappe.get_list(
		PAIEMENT,
		filters=[["party_type", "in", list(PARTY_NAME)], *conditions],
		distinct=has_child_filter(conditions, PAIEMENT),
		or_filters=[
			["name", "like", pattern],
			["party_name", "like", pattern],
			["party", "like", pattern],
			["reference_no", "like", pattern],
		]
		if value
		else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	rows = [_list_row(row) for row in paiements]
	counts = {name: sum(1 for row in rows if in_view(name, row)) for name in VIEWS}
	ordered = order_paiements([row for row in rows if in_view(view, row)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"paiements": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


@frappe.whitelist()
def get_paiement_options():
	"""Types que la personne peut saisir (droit de lire le tiers et sa pièce), modes de paiement et filtres."""
	require_bureau()
	kinds = [
		{"value": key, "label": label, "sens": sens, "tiers": party_type}
		for key, (sens, party_type, doctype, _sign, label) in KINDS.items()
		if frappe.has_permission(party_type, "read") and frappe.has_permission(doctype, "read")
	]
	return {
		"types": kinds,
		"modes": frappe.get_all(
			MODE, filters={"enabled": 1}, fields=["name as value", "type"], order_by="name asc"
		),
		"can_create": bool(frappe.has_permission(PAIEMENT, "create")),
		"filter_fields": doctype_filter_fields(PAIEMENT),
	}


def _kind(kind):
	if kind not in KINDS:
		frappe.throw(_("Type de paiement inconnu."))
	return KINDS[kind]


@frappe.whitelist()
def search_tiers(kind, search=None):
	"""Clients ou fournisseurs actifs, selon le type de paiement."""
	require_bureau()
	_sens, party_type, _doctype, _sign, _label = _kind(kind)
	value = cstr(search).strip()
	name_field = PARTY_NAME[party_type]
	rows = frappe.get_list(
		party_type,
		filters={"disabled": 0},
		or_filters=[[name_field, "like", f"%{value}%"], ["name", "like", f"%{value}%"]] if value else None,
		fields=["name", f"{name_field} as label"],
		order_by=f"{name_field} asc",
		limit_page_length=12,
	)
	return [{"name": row.name, "label": row.label or row.name} for row in rows]


@frappe.whitelist()
def get_pieces_ouvertes(kind, tiers, exclude=None):
	"""Pièces du tiers qui restent à régler dans ce sens, l'échéance la plus ancienne d'abord.

	Les montants sont rendus positifs : l'assistant raisonne toujours en « ce qu'il reste à régler ».
	`exclude` : le paiement en cours de modification, dont les affectations ne comptent pas comme réglées.
	"""
	require_bureau()
	_sens, party_type, doctype, sign, _label = _kind(kind)
	frappe.get_doc(party_type, tiers).check_permission("read")
	rows = frappe.get_list(
		doctype,
		filters={
			PARTY_FIELD[doctype]: tiers,
			"docstatus": 1,
			"outstanding_amount": [">", 0] if sign > 0 else ["<", 0],
		},
		fields=[
			"name",
			"posting_date",
			"due_date",
			"grand_total",
			"rounded_total",
			"outstanding_amount",
			"is_return",
		],
		order_by="due_date asc, posting_date asc, name asc",
		limit_page_length=PIECES_MAX,
	)
	pending = {}
	if exclude:
		for ref in frappe.get_all(
			REFERENCES,
			filters={"parent": exclude, "reference_doctype": doctype},
			fields=["reference_name", "allocated_amount"],
		):
			pending[ref.reference_name] = abs(flt(ref.allocated_amount))
	return [
		{
			"doctype": doctype,
			"name": row.name,
			"date": _day(row.posting_date),
			"echeance": _day(row.due_date),
			"total": abs(flt(row.rounded_total) or flt(row.grand_total)),
			"reste": flt(abs(flt(row.outstanding_amount)), 2),
			"avoir": cint(row.is_return),
			"deja": pending.get(row.name, 0),
		}
		for row in rows
	]


def _clean(values):
	"""Saisie de l'assistant → valeurs contrôlées. Refuse tout ce que l'écran aurait dû refuser."""
	values = _parse(values) or {}
	kind = cstr(values.get("type")).strip()
	sens, party_type, doctype, sign, _label = _kind(kind)
	tiers = cstr(values.get("tiers")).strip()
	if not tiers:
		frappe.throw(_("Choisissez le tiers."))
	frappe.get_doc(party_type, tiers).check_permission("read")
	montant = flt(values.get("montant"), 2)
	if montant <= 0:
		frappe.throw(_("Le montant doit être positif."))
	mode = cstr(values.get("mode")).strip()
	mode_type = frappe.db.get_value(MODE, {"name": mode, "enabled": 1}, "type")
	if not mode_type:
		frappe.throw(_("Choisissez un mode de paiement de la liste."))
	date = getdate(values.get("date") or today())
	if date > getdate(today()):
		frappe.throw(_("La date du paiement ne peut pas être dans le futur."))
	reference = cstr(values.get("reference")).strip()
	if mode_type == "Bank" and not reference:
		frappe.throw(_("Saisissez la référence (nº de chèque, de virement ou de traite)."))
	allocations = []
	seen = set()
	for entry in values.get("affectations") or []:
		name = cstr((entry or {}).get("name")).strip()
		amount = flt((entry or {}).get("montant"), 2)
		if not name or amount == 0:
			continue
		if amount < 0:
			frappe.throw(_("Un montant affecté ne peut pas être négatif."))
		if name in seen:
			frappe.throw(_("La pièce {0} est affectée deux fois.").format(name))
		seen.add(name)
		allocations.append((name, amount))
	if flt(sum(amount for _name, amount in allocations), 2) > montant:
		frappe.throw(_("Les montants affectés dépassent le montant du paiement."))
	return {
		"kind": kind,
		"sens": sens,
		"party_type": party_type,
		"doctype": doctype,
		"sign": sign,
		"tiers": tiers,
		"montant": montant,
		"mode": mode,
		"date": date,
		"reference": reference,
		"date_reference": getdate(values.get("date_reference") or date) if reference else None,
		"allocations": allocations,
		"remarque": cstr(values.get("remarque")).strip() or None,
	}


def _fill(doc, values):
	"""Remplit le Payment Entry ; ERPNext complète devises, restes dus et totaux à l'enregistrement."""
	from erpnext.accounts.party import get_party_account

	company = doc.company or _company()
	party_account = get_party_account(values["party_type"], values["tiers"], company)
	treasury = _payment_account(company, values["mode"])
	receive = values["sens"] == "Receive"
	doc.update(
		{
			"payment_type": values["sens"],
			"company": company,
			"posting_date": values["date"],
			"mode_of_payment": values["mode"],
			"party_type": values["party_type"],
			"party": values["tiers"],
			"paid_from": party_account if receive else treasury,
			"paid_to": treasury if receive else party_account,
			"paid_amount": values["montant"],
			"received_amount": values["montant"],
			"source_exchange_rate": 1,
			"target_exchange_rate": 1,
			"reference_no": values["reference"] or None,
			"reference_date": values["date_reference"],
			"remarks": values["remarque"],
		}
	)
	for field in ("paid_from", "paid_to"):
		doc.set(
			f"{field}_account_currency",
			frappe.get_cached_value("Account", doc.get(field), "account_currency"),
		)
	doc.set("references", [])
	for name, amount in values["allocations"]:
		piece = frappe.db.get_value(
			values["doctype"],
			name,
			[PARTY_FIELD[values["doctype"]], "docstatus", "outstanding_amount", "company"],
			as_dict=True,
		)
		if not piece or piece.docstatus != 1 or piece[PARTY_FIELD[values["doctype"]]] != values["tiers"]:
			frappe.throw(_("La pièce {0} n'est pas une pièce validée de ce tiers.").format(name))
		if flt(piece.outstanding_amount) * values["sign"] <= 0:
			frappe.throw(_("La pièce {0} n'a plus rien à régler dans ce sens.").format(name))
		doc.append(
			"references",
			{
				"reference_doctype": values["doctype"],
				"reference_name": name,
				# Un avoir se rembourse : son reste dû et son affectation sont négatifs, comme sur le Desk.
				"allocated_amount": amount * values["sign"],
			},
		)


def actions(doc):
	found = []
	if doc.docstatus == 0:
		if doc.has_permission("write") and kind_of(doc.payment_type, doc.party_type):
			found.append("modifier")
		if doc.has_permission("submit"):
			found.append("valider")
		if doc.has_permission("delete"):
			found.append("supprimer")
	elif doc.docstatus == 1 and doc.has_permission("cancel"):
		found.append("annuler")
	return found


def _paiement_payload(doc):
	kind = kind_of(doc.payment_type, doc.party_type)
	allowed = actions(doc)
	refs = []
	for ref in doc.references:
		refs.append(
			{
				"doctype": ref.reference_doctype,
				"name": ref.reference_name,
				"echeance": _day(ref.due_date),
				"total": abs(flt(ref.total_amount)),
				"reste": abs(flt(ref.outstanding_amount)),
				"montant": abs(flt(ref.allocated_amount)),
			}
		)
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"status": _status(doc),
		"docstatus": cint(doc.docstatus),
		"type": kind,
		"type_label": KINDS[kind][4] if kind else doc.payment_type,
		"sens": doc.payment_type,
		"tiers_type": doc.party_type,
		"tiers": doc.party,
		"tiers_label": doc.party_name or doc.party,
		"date": _day(doc.posting_date),
		"montant": flt(doc.paid_amount),
		"affecte": flt(doc.total_allocated_amount),
		"non_affecte": flt(doc.unallocated_amount),
		"mode": doc.mode_of_payment,
		"reference": doc.reference_no or None,
		"date_reference": _day(doc.reference_date),
		"remarque": doc.remarks or None,
		"compte_depart": doc.paid_from,
		"compte_arrivee": doc.paid_to,
		"en_lettres": doc.get("in_words") or None,
		"affectations": refs,
		"cree_par": get_fullname(doc.owner),
		"actions": allowed,
		"can_print": bool(doc.has_permission("print")),
		"comments": activity.comment_summary(PAIEMENT, doc.name),
	}


@frappe.whitelist()
def get_paiement(name):
	require_bureau()
	doc = frappe.get_doc(PAIEMENT, name)
	doc.check_permission("read")
	return _paiement_payload(doc)


def _for_work(name, modified, action):
	require_bureau()
	doc = frappe.get_doc(PAIEMENT, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Ce paiement vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	if action not in actions(doc):
		frappe.throw(_("Cette action n'est pas possible sur ce paiement."), frappe.PermissionError)
	return doc


@frappe.whitelist(methods=["POST"])
def create_paiement(values=None):
	"""Crée le paiement en brouillon, avec ses affectations. Il se relit puis se valide sur sa fiche."""
	require_bureau()
	frappe.has_permission(PAIEMENT, "create", throw=True)
	values = _clean(values)
	doc = frappe.new_doc(PAIEMENT)
	_fill(doc, values)
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_paiement(name, modified, values=None):
	"""Brouillon : toute la saisie de l'assistant, affectations comprises, remplace la précédente."""
	doc = _for_work(name, modified, "modifier")
	values = _clean(values)
	_fill(doc, values)
	doc.save()
	return _paiement_payload(doc)


@frappe.whitelist(methods=["POST"])
def validate_paiement(name, modified):
	doc = _for_work(name, modified, "valider")
	doc.submit()
	return _paiement_payload(doc)


@frappe.whitelist(methods=["POST"])
def cancel_paiement(name, modified):
	doc = _for_work(name, modified, "annuler")
	doc.cancel()
	return _paiement_payload(doc)


@frappe.whitelist(methods=["POST"])
def delete_paiement(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(PAIEMENT, doc.name)
	return {"deleted": doc.name}


def paiement_for_bulk(name, modified):
	require_bureau()
	doc = frappe.get_doc(PAIEMENT, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Ce paiement vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	return doc


def bulk_guard(doc, operation):
	if doc.docstatus != 0:
		return _("Paiement validé ou annulé : il ne change plus.")
	return None


def _check_activity(name):
	require_bureau()
	frappe.get_doc(PAIEMENT, name).check_permission("read")


@frappe.whitelist()
def get_paiement_activity(name):
	require_bureau()
	return activity.get_feed(PAIEMENT, name)


@frappe.whitelist(methods=["POST"])
def add_paiement_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(PAIEMENT, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_paiement_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(PAIEMENT, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_paiement_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(PAIEMENT, name, comment)
