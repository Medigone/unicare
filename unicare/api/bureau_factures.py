# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Factures client du poste de bureau (/bureau/factures) : liste, aperçu, fiche, encaissement et avoirs.

Une facture naît d'une commande ou d'un bon de livraison (leurs fiches la créent en brouillon) : montants et suivi
facturé restent ceux d'ERPNext. Sur le brouillon se règlent l'échéance, la TVA et, pour un avoir, les quantités
créditées ; la validation passe l'écriture comptable. Une facture validée s'encaisse (Payment Entry validée
aussitôt), donne un avoir (facture de retour, en brouillon) ou s'annule.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_fullname, getdate, today

from unicare.api import activity
from unicare.api.bureau_devis import TAXES, _day, _status, _taxes_templates, tax_lines
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
from unicare.api.bureau_versions import amend, cancelled_actions, versions

FACTURE = "Sales Invoice"
LIGNES = "Sales Invoice Item"
PAIEMENT = "Payment Entry"
MODE = "Mode of Payment"

IMPAYEES = (
	"Unpaid",
	"Partly Paid",
	"Overdue",
	"Partly Paid and Discounted",
	"Overdue and Discounted",
	"Unpaid and Discounted",
)
EN_RETARD = ("Overdue", "Overdue and Discounted")
CLOS = ("Cancelled", "Credit Note Issued", "Return")

FIELDS = [
	"name",
	"modified",
	"creation",
	"status",
	"docstatus",
	"customer",
	"customer_name",
	"posting_date",
	"due_date",
	"is_return",
	"return_against",
	"grand_total",
	"rounded_total",
	"outstanding_amount",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "brouillons", "impayees", "en_retard", "payees", "avoirs", "clos")
SORT_KEYS = {
	"name",
	"client_label",
	"date",
	"echeance",
	"status",
	"total_ttc",
	"reste",
	"creation",
	"modified",
}


def in_view(view, row):
	if view == "all":
		return True
	status = row["status"]
	if view == "brouillons":
		return status == "Draft"
	if view == "avoirs":
		return bool(row["avoir"])
	if view == "impayees":
		return status in IMPAYEES and not row["avoir"]
	if view == "en_retard":
		return status in EN_RETARD and not row["avoir"]
	if view == "payees":
		return status == "Paid" and not row["avoir"]
	return status in CLOS and not (row["avoir"] and status == "Return")


def _sources(names):
	"""Commandes et bons de livraison d'origine de chaque facture lisible."""
	if not names:
		return {}
	rows = frappe.get_all(
		LIGNES,
		filters={"parent": ["in", names], "parenttype": FACTURE},
		fields=["parent", "sales_order", "delivery_note"],
		order_by="idx asc",
	)
	sources = {}
	for row in rows:
		entry = sources.setdefault(row.parent, {"commandes": [], "livraisons": []})
		for key, value in (("commandes", row.sales_order), ("livraisons", row.delivery_note)):
			if value and value not in entry[key]:
				entry[key].append(value)
	return sources


def _total(doc):
	return flt(doc.rounded_total) or flt(doc.grand_total)


def _list_row(facture, sources):
	entry = sources.get(facture.name, {"commandes": [], "livraisons": []})
	return {
		"name": facture.name,
		"modified": facture.modified,
		"creation": str(facture.creation),
		"tags": row_tags(facture),
		"cloche": row_bell(facture),
		"client": facture.customer,
		"client_label": facture.customer_name or facture.customer,
		"date": _day(facture.posting_date),
		"echeance": _day(facture.due_date),
		"status": _status(facture),
		"avoir": cint(facture.is_return),
		"avoir_de": facture.return_against or None,
		"total_ttc": _total(facture),
		"reste": flt(facture.outstanding_amount),
		"commandes": ", ".join(entry["commandes"]) or None,
		"livraisons": ", ".join(entry["livraisons"]) or None,
	}


def order_factures(rows, sort=None, direction=None):
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
def get_factures(
	view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None
):
	"""Une page de la liste, le total, l'ordre de toute la vue, les compteurs de toutes les vues, et le reste dû."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), FACTURE)
	factures = frappe.get_list(
		FACTURE,
		filters=conditions,
		distinct=has_child_filter(conditions, FACTURE),
		or_filters=[
			["name", "like", pattern],
			["customer_name", "like", pattern],
			["customer", "like", pattern],
		]
		if value
		else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	sources = _sources([row.name for row in factures])
	rows = [_list_row(row, sources) for row in factures]
	counts = {name: sum(1 for row in rows if in_view(name, row)) for name in VIEWS}
	shown = [row for row in rows if in_view(view, row)]
	ordered = order_factures(shown, sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"factures": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		# Ce qui reste à encaisser sur la vue affichée : factures validées, avoirs déduits.
		"reste_du": flt(sum(row["reste"] for row in shown if row["status"] != "Draft"), 2),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


def _modes():
	return frappe.get_all(MODE, filters={"enabled": 1}, fields=["name", "type"], order_by="name asc")


@frappe.whitelist()
def get_facture_options():
	require_bureau()
	return {
		"taxes": [{"value": row.name, "label": row.title or row.name} for row in _taxes_templates()],
		"filter_fields": doctype_filter_fields(FACTURE),
	}


def _paiements(doc):
	"""Encaissements rattachés à la facture, par les lignes de référence des Payment Entry."""
	if not frappe.has_permission(PAIEMENT, "read"):
		return None
	rows = frappe.get_list(
		PAIEMENT,
		filters=[
			["Payment Entry Reference", "reference_doctype", "=", FACTURE],
			["Payment Entry Reference", "reference_name", "=", doc.name],
			[PAIEMENT, "docstatus", "<", 2],
		],
		fields=[
			"name",
			"posting_date",
			"mode_of_payment",
			"reference_no",
			"docstatus",
			"`tabPayment Entry Reference`.allocated_amount as montant",
		],
		order_by=f"`tab{PAIEMENT}`.posting_date desc",
	)
	return [
		{
			"name": row.name,
			"date": _day(row.posting_date),
			"mode": row.mode_of_payment,
			"reference": row.reference_no or None,
			"montant": flt(row.montant),
			"brouillon": row.docstatus == 0,
		}
		for row in rows
	]


def _avoirs(doc):
	return [
		{"name": row.name, "status": _status(row), "date": _day(row.posting_date), "total": _total(row)}
		for row in frappe.get_list(
			FACTURE,
			filters={"return_against": doc.name, "docstatus": ["<", 2]},
			fields=["name", "status", "docstatus", "posting_date", "grand_total", "rounded_total"],
			order_by="posting_date desc",
		)
	]


def blocked(doc):
	if doc.docstatus != 0:
		return []
	reasons = []
	if not doc.items:
		reasons.append(_("La facture n'a aucune ligne."))
	if any(flt(item.rate) <= 0 for item in doc.items) and not cint(doc.is_return):
		reasons.append(_("Une ligne n'a pas de prix."))
	if doc.due_date and getdate(doc.due_date) < getdate(doc.posting_date):
		reasons.append(_("L'échéance précède la date de la facture."))
	return reasons


def actions(doc):
	if doc.docstatus == 2:
		return cancelled_actions(doc)
	found = []
	if doc.docstatus == 0:
		if doc.has_permission("write"):
			found.append("modifier")
		if doc.has_permission("submit"):
			found.append("valider")
		if doc.has_permission("delete"):
			found.append("supprimer")
		return found
	if doc.docstatus != 1:
		return found
	if not cint(doc.is_return):
		if flt(doc.outstanding_amount) > 0 and frappe.has_permission(PAIEMENT, "create"):
			found.append("encaisser")
		if doc.status != "Credit Note Issued" and doc.has_permission("create"):
			found.append("avoir")
	if doc.has_permission("cancel"):
		found.append("annuler")
	return found


def _line(item):
	return {
		"name": item.name,
		"article": item.item_code,
		"designation": item.item_name or item.item_code,
		"quantite": flt(item.qty),
		"unite": item.uom,
		"prix": flt(item.rate),
		"montant": flt(item.amount),
		"commande": item.sales_order or None,
		"livraison": item.delivery_note or None,
	}


def _facture_payload(doc):
	allowed = actions(doc)
	sources = {"commandes": [], "livraisons": []}
	for item in doc.items:
		for key, value in (("commandes", item.sales_order), ("livraisons", item.delivery_note)):
			if value and value not in sources[key]:
				sources[key].append(value)
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"status": _status(doc),
		"docstatus": cint(doc.docstatus),
		"avoir": cint(doc.is_return),
		"avoir_de": doc.return_against or None,
		# Avoir : il réduit le reste dû de sa facture (0), ou garde son propre solde à rembourser (1).
		"avoir_autonome": cint(doc.get("update_outstanding_for_self")),
		"client": doc.customer,
		"client_label": doc.customer_name or doc.customer,
		"date": _day(doc.posting_date),
		"echeance": _day(doc.due_date),
		"cree_par": get_fullname(doc.owner),
		"taxes_modele": doc.taxes_and_charges,
		"lignes": [_line(item) for item in doc.items],
		"taxes": tax_lines(doc),
		"total": flt(doc.net_total),
		"total_taxes": flt(doc.total_taxes_and_charges),
		"total_ttc": _total(doc),
		"en_lettres": doc.in_words or None,
		"reste": flt(doc.outstanding_amount),
		"paye": flt(_total(doc) - flt(doc.outstanding_amount), 2) if doc.docstatus == 1 else 0,
		"commandes": sources["commandes"],
		"livraisons": sources["livraisons"],
		"paiements": _paiements(doc),
		"avoirs": _avoirs(doc),
		"version_de": doc.get("amended_from") or None,
		"versions": versions(doc),
		"actions": allowed,
		"blocked": blocked(doc) if "valider" in allowed else [],
		"modes": [{"value": row.name, "type": row.type} for row in _modes()]
		if "encaisser" in allowed
		else [],
		"can_print": bool(doc.has_permission("print")),
		"comments": activity.comment_summary(FACTURE, doc.name),
	}


@frappe.whitelist()
def get_facture(name):
	require_bureau()
	doc = frappe.get_doc(FACTURE, name)
	doc.check_permission("read")
	return _facture_payload(doc)


def _for_work(name, modified, action):
	require_bureau()
	doc = frappe.get_doc(FACTURE, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Cette facture vient d'être modifiée par ailleurs. Elle a été rechargée : vérifiez-la, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	if action not in actions(doc):
		frappe.throw(_("Cette action n'est pas possible sur cette facture."), frappe.PermissionError)
	return doc


@frappe.whitelist(methods=["POST"])
def update_facture(name, modified, echeance=None, taxes=None, lignes=None):
	"""Brouillon : échéance, modèle de TVA et, pour un avoir, quantités créditées (négatives). Absent : inchangé."""
	from erpnext.controllers.accounts_controller import get_taxes_and_charges

	doc = _for_work(name, modified, "modifier")
	if echeance is not None:
		if not echeance:
			frappe.throw(_("L'échéance est obligatoire."))
		if getdate(echeance) < getdate(doc.posting_date):
			frappe.throw(_("L'échéance ne peut pas précéder la date de la facture."))
		doc.due_date = getdate(echeance)
		# L'échéancier suit l'échéance unique saisie ici, comme une facture sans conditions de paiement.
		doc.payment_terms_template = None
		doc.set("payment_schedule", [])
	if taxes is not None:
		template = cstr(taxes).strip()
		if template and not frappe.db.exists(
			TAXES, {"name": template, "company": doc.company, "disabled": 0}
		):
			frappe.throw(_("Choisissez un modèle de TVA de la liste."))
		doc.taxes_and_charges = template or None
		doc.set("taxes", (get_taxes_and_charges(TAXES, template) or []) if template else [])
	lignes = _parse(lignes) or []
	if lignes:
		if not cint(doc.is_return):
			frappe.throw(
				_(
					"Les quantités d'une facture viennent de sa commande ou de son bon : modifiez-les à la source."
				)
			)
		rows = {row.name: row for row in doc.items}
		removed = set()
		for ligne in lignes:
			row = rows.get(cstr((ligne or {}).get("name")))
			if not row:
				frappe.throw(_("Cette ligne n'est plus dans l'avoir : rechargez-le."))
			quantite = flt(ligne.get("quantite"))
			if quantite > 0:
				frappe.throw(_("Une ligne d'avoir se saisit en quantité négative."))
			if quantite == 0:
				removed.add(row.name)
			else:
				row.qty = quantite
		if removed:
			doc.set("items", [row for row in doc.items if row.name not in removed])
			if not doc.items:
				frappe.throw(_("L'avoir doit garder au moins une ligne : supprimez le brouillon plutôt."))
	doc.save()
	return _facture_payload(doc)


@frappe.whitelist(methods=["POST"])
def validate_facture(name, modified):
	doc = _for_work(name, modified, "valider")
	reasons = blocked(doc)
	if reasons:
		frappe.throw(" ".join(reasons))
	doc.submit()
	return _facture_payload(doc)


@frappe.whitelist(methods=["POST"])
def cancel_facture(name, modified):
	doc = _for_work(name, modified, "annuler")
	doc.cancel()
	return _facture_payload(doc)


@frappe.whitelist(methods=["POST"])
def delete_facture(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(FACTURE, doc.name)
	return {"deleted": doc.name}


@frappe.whitelist(methods=["POST"])
def create_version(name, modified):
	"""Nouvelle version (brouillon `NOM-1`) d'une pièce annulée, comme « Modifier » sur le Desk."""
	doc = _for_work(name, modified, "nouvelle_version")
	return amend(doc)


def _payment_account(company, mode):
	"""Compte d'arrivée : celui du mode de paiement pour la société, sinon la caisse ou la banque par défaut."""
	account = frappe.db.get_value(
		"Mode of Payment Account", {"parent": mode, "company": company}, "default_account"
	)
	if account:
		return account
	kind = frappe.db.get_value(MODE, mode, "type")
	field = "default_cash_account" if kind == "Cash" else "default_bank_account"
	account = frappe.get_cached_value("Company", company, field)
	if not account:
		frappe.throw(
			_("Aucun compte n'est défini pour le mode {0} : renseignez-le sur le Desk.").format(mode)
		)
	return account


@frappe.whitelist(methods=["POST"])
def encaisser(name, modified, montant, mode, date=None, reference=None, date_reference=None):
	"""Enregistre et valide un encaissement, partiel ou total, sur la facture."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	doc = _for_work(name, modified, "encaisser")
	montant = flt(montant, 2)
	if montant <= 0:
		frappe.throw(_("Le montant encaissé doit être positif."))
	if montant > flt(doc.outstanding_amount, 2):
		frappe.throw(
			_("Le montant dépasse le reste dû ({0}).").format(
				frappe.format(doc.outstanding_amount, {"fieldtype": "Currency", "options": doc.currency})
			)
		)
	mode = cstr(mode).strip()
	kind = frappe.db.get_value(MODE, {"name": mode, "enabled": 1}, "type")
	if not kind:
		frappe.throw(_("Choisissez un mode de paiement de la liste."))
	date = getdate(date or today())
	if date > getdate(today()):
		frappe.throw(_("La date d'encaissement ne peut pas être dans le futur."))
	reference = cstr(reference).strip()
	if kind == "Bank" and not reference:
		frappe.throw(_("Saisissez la référence (nº de chèque, de virement ou de traite)."))
	paiement = get_payment_entry(
		FACTURE, doc.name, party_amount=montant, bank_account=_payment_account(doc.company, mode)
	)
	paiement.posting_date = date
	paiement.mode_of_payment = mode
	paiement.paid_amount = montant
	paiement.received_amount = montant
	for row in paiement.references:
		row.allocated_amount = montant
	if reference:
		paiement.reference_no = reference
		paiement.reference_date = getdate(date_reference or date)
	paiement.insert()
	paiement.submit()
	return {"paiement": paiement.name, "facture": _facture_payload(frappe.get_doc(FACTURE, doc.name))}


@frappe.whitelist(methods=["POST"])
def create_avoir(name, modified):
	"""Avoir en brouillon (facture de retour), de toutes les quantités : on réduit ensuite ce qu'on ne crédite pas."""
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

	doc = _for_work(name, modified, "avoir")
	avoir = make_sales_return(doc.name)
	if not avoir.get("items"):
		frappe.throw(_("Il ne reste rien à créditer."))
	# Tant que la facture n'est pas soldée, l'avoir réduit son reste dû. ERPNext reprend la main si l'avoir le dépasse :
	# il garde alors son propre solde, à rembourser.
	avoir.update_outstanding_for_self = 0 if flt(doc.outstanding_amount) > 0 else 1
	avoir.insert()
	return {"name": avoir.name, "facture": _facture_payload(frappe.get_doc(FACTURE, doc.name))}


def facture_for_bulk(name, modified):
	require_bureau()
	doc = frappe.get_doc(FACTURE, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Cette facture vient d'être modifiée par ailleurs. Elle a été rechargée : vérifiez-la, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	return doc


def bulk_guard(doc, operation):
	# Une pièce annulée peut se supprimer en groupe ; seuls les brouillons se modifient.
	if doc.docstatus != 0 and not (operation == "delete" and doc.docstatus == 2):
		return _("Facture validée ou annulée : elle ne change plus.")
	return None


def _check_activity(name):
	require_bureau()
	frappe.get_doc(FACTURE, name).check_permission("read")


@frappe.whitelist()
def get_facture_activity(name):
	require_bureau()
	return activity.get_feed(FACTURE, name)


@frappe.whitelist(methods=["POST"])
def add_facture_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(FACTURE, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_facture_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(FACTURE, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_facture_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(FACTURE, name, comment)
