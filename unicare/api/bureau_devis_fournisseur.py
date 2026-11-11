# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Devis fournisseur du poste de bureau (/bureau/devis-fournisseurs) : liste, aperçu, fiche, création et cycle.

Le Supplier Quotation standard d'ERPNext, pendant d'achat du devis client (`bureau_devis`) : il se saisit ici avec
son fournisseur, sa référence, sa validité, sa TVA déductible et ses lignes au prix d'achat connu. Un brouillon se
modifie, se valide ou se supprime ; un devis validé donne sa commande d'achat (en brouillon, par l'outil d'ERPNext)
ou s'annule. Chaque écriture reçoit la date `modified` affichée à l'écran.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, cstr, flt, get_fullname, getdate, today

from unicare.api import activity
from unicare.api.bureau_achats import (
	replace_disabled_taxes,
	SUPPLIER,
	buying_price_list,
	check_supplier,
	clean_lines,
	set_lines,
	set_purchase_taxes,
	taxes_options,
)
from unicare.api.bureau_devis import (
	EXPIRE_SOUS,
	VALIDITE_PAR_DEFAUT,
	_company,
	_day,
	_status,
	line_description,
	tax_lines,
)
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

DEVIS_F = "Supplier Quotation"
LIGNES = "Supplier Quotation Item"
COMMANDE_ACHAT = "Purchase Order"
LIGNES_COMMANDE = "Purchase Order Item"

CLOS = ("Stopped", "Expired", "Cancelled")

FIELDS = [
	"name",
	"modified",
	"creation",
	"owner",
	"status",
	"docstatus",
	"supplier",
	"supplier_name",
	"transaction_date",
	"valid_till",
	"quotation_number",
	"net_total",
	"grand_total",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "brouillons", "ouverts", "expirent", "commandes", "clos")
SORT_KEYS = {
	"name",
	"fournisseur_label",
	"date",
	"valable",
	"status",
	"reference",
	"total",
	"total_ttc",
	"lignes",
	"creation",
	"modified",
}


def in_view(view, row, current_day=None):
	if view == "all":
		return True
	status = row["status"]
	if view == "brouillons":
		return status == "Draft"
	if view == "ouverts":
		return status == "Submitted" and not row.get("commande")
	if view == "expirent":
		day = getdate(current_day or today())
		valable = row.get("valable")
		return (
			status == "Submitted"
			and not row.get("commande")
			and bool(valable)
			and day <= getdate(valable) <= add_days(day, EXPIRE_SOUS)
		)
	if view == "commandes":
		return status == "Submitted" and bool(row.get("commande"))
	return status in CLOS


def _lines_by_devis(names):
	if not names:
		return {}
	rows = frappe.get_all(
		LIGNES,
		filters={"parent": ["in", names], "parenttype": DEVIS_F},
		fields=["parent", "item_name", "item_code"],
		order_by="idx asc",
	)
	lines = {}
	for row in rows:
		lines.setdefault(row.parent, []).append(row.item_name or row.item_code)
	return lines


def _ordered(names):
	"""Devis repris par au moins une commande d'achat non annulée."""
	if not names:
		return set()
	rows = frappe.get_all(
		LIGNES_COMMANDE,
		filters={"supplier_quotation": ["in", names], "docstatus": ["<", 2]},
		pluck="supplier_quotation",
		distinct=True,
	)
	return set(rows)


def _list_row(devis, lines, ordered):
	articles = lines.get(devis.name, [])
	return {
		"name": devis.name,
		"modified": devis.modified,
		"creation": str(devis.creation),
		"tags": row_tags(devis),
		"cloche": row_bell(devis),
		"fournisseur": devis.supplier,
		"fournisseur_label": devis.supplier_name or devis.supplier,
		"date": _day(devis.transaction_date),
		"valable": _day(devis.valid_till),
		"reference": devis.quotation_number or None,
		"status": _status(devis),
		"commande": devis.name in ordered,
		"total": flt(devis.net_total),
		"total_ttc": flt(devis.grand_total),
		"lignes": len(articles),
		"articles": ", ".join(articles[:3]) + (f" (+{len(articles) - 3})" if len(articles) > 3 else ""),
	}


def order_devis(rows, sort=None, direction=None):
	"""Les plus récents d'abord, ou par la colonne demandée. Une ligne sans valeur reste à la fin."""
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
def get_devis_fournisseurs(
	view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None
):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), DEVIS_F)
	devis = frappe.get_list(
		DEVIS_F,
		filters=conditions,
		distinct=has_child_filter(conditions, DEVIS_F),
		or_filters=[
			["name", "like", pattern],
			["supplier_name", "like", pattern],
			["supplier", "like", pattern],
			["quotation_number", "like", pattern],
		]
		if value
		else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	names = [row.name for row in devis]
	lines = _lines_by_devis(names)
	ordered_names = _ordered(names)
	rows = [_list_row(row, lines, ordered_names) for row in devis]
	current_day = today()
	counts = {name: sum(1 for row in rows if in_view(name, row, current_day)) for name in VIEWS}
	ordered = order_devis([row for row in rows if in_view(view, row, current_day)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"devis": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


@frappe.whitelist()
def get_devis_fournisseur_options():
	"""Valeurs proposées dans les filtres et dans la fenêtre du devis fournisseur."""
	require_bureau()
	return {
		**taxes_options(_company()),
		"validite_jours": VALIDITE_PAR_DEFAUT,
		"filter_fields": doctype_filter_fields(DEVIS_F),
	}


def blocked(doc):
	"""Ce qui empêche de valider : aucune ligne, une ligne sans prix, une validité passée."""
	reasons = []
	if not doc.items:
		reasons.append(_("Le devis n'a aucune ligne."))
	missing = sum(1 for item in doc.items if flt(item.rate) <= 0)
	if missing:
		reasons.append(_("{0} ligne(s) sans prix.").format(missing))
	if doc.valid_till and getdate(doc.valid_till) < getdate(today()):
		reasons.append(_("La date de validité est passée."))
	return reasons


def _commandes(doc):
	"""Commandes d'achat faites depuis ce devis, par leurs lignes. `None` sans droit de lecture."""
	if not frappe.has_permission(COMMANDE_ACHAT, "read"):
		return None
	rows = frappe.get_list(
		COMMANDE_ACHAT,
		filters=[
			[LIGNES_COMMANDE, "supplier_quotation", "=", doc.name],
			[COMMANDE_ACHAT, "docstatus", "<", 2],
		],
		fields=["name", "status", "docstatus", "transaction_date", "schedule_date", "grand_total"],
		order_by=f"`tab{COMMANDE_ACHAT}`.transaction_date desc",
		distinct=True,
	)
	return [
		{
			"name": row.name,
			"status": _status(row),
			"date": _day(row.transaction_date),
			"reception": _day(row.schedule_date),
			"total": flt(row.grand_total),
		}
		for row in rows
	]


def actions(doc):
	"""Ce que cette personne peut faire sur ce devis, maintenant. Le serveur reste seul juge à l'exécution."""
	found = []
	if doc.docstatus == 0:
		if doc.has_permission("write"):
			found.append("modifier")
		if doc.has_permission("submit"):
			found.append("valider")
		if doc.has_permission("delete"):
			found.append("supprimer")
	elif doc.docstatus == 1:
		if doc.status == "Submitted" and frappe.has_permission(COMMANDE_ACHAT, "create"):
			found.append("commande")
		if doc.has_permission("cancel"):
			found.append("annuler")
	return found


def _line(item):
	return {
		"name": item.name,
		"article": item.item_code,
		"designation": item.item_name or item.item_code,
		"description": line_description(item),
		"quantite": flt(item.qty),
		"unite": item.uom,
		"prix": flt(item.rate),
		"prix_tarif": flt(item.price_list_rate),
		"remise": flt(item.discount_percentage),
		"montant": flt(item.amount),
	}


def _devis_payload(doc):
	allowed = actions(doc)
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"status": _status(doc),
		"docstatus": cint(doc.docstatus),
		"fournisseur": doc.supplier,
		"fournisseur_label": doc.supplier_name or doc.supplier,
		"date": _day(doc.transaction_date),
		"valable": _day(doc.valid_till),
		"reference": doc.quotation_number or None,
		"cree_par": get_fullname(doc.owner),
		"devise": doc.currency,
		"taxes_modele": doc.taxes_and_charges,
		"lignes": [_line(item) for item in doc.items],
		"taxes": tax_lines(doc),
		"total": flt(doc.net_total),
		"total_taxes": flt(doc.total_taxes_and_charges),
		"total_ttc": flt(doc.grand_total),
		"arrondi": flt(doc.rounded_total) or None,
		"en_lettres": doc.in_words or None,
		"commandes": _commandes(doc),
		"actions": allowed,
		"blocked": blocked(doc) if "valider" in allowed else [],
		"can_print": bool(doc.has_permission("print")),
		"comments": activity.comment_summary(DEVIS_F, doc.name),
	}


@frappe.whitelist()
def get_devis_fournisseur(name):
	require_bureau()
	doc = frappe.get_doc(DEVIS_F, name)
	doc.check_permission("read")
	return _devis_payload(doc)


def _load(name, modified):
	require_bureau()
	doc = frappe.get_doc(DEVIS_F, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Ce devis vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	return doc


def _for_work(name, modified, action):
	"""Le devis à modifier : l'action doit être permise, et l'écran à jour."""
	doc = _load(name, modified)
	if action not in actions(doc):
		frappe.throw(_("Cette action n'est pas possible sur ce devis."), frappe.PermissionError)
	return doc


def _check_validity(valable, date):
	"""La validité est facultative côté achat ; donnée, elle ne précède pas la date du devis."""
	if not valable:
		return None
	if getdate(valable) < getdate(date):
		frappe.throw(_("La validité ne peut pas précéder la date du devis."))
	return getdate(valable)


@frappe.whitelist(methods=["POST"])
def create_devis_fournisseur(values=None):
	"""Crée un devis fournisseur en brouillon : fournisseur, référence, validité, TVA et lignes."""
	require_bureau()
	frappe.has_permission(DEVIS_F, "create", throw=True)
	values = _parse(values) or {}
	fournisseur = check_supplier(values.get("fournisseur"))
	lignes = clean_lines(values.get("lignes"))
	date = today()
	doc = frappe.new_doc(DEVIS_F)
	doc.update(
		{
			"supplier": fournisseur,
			"company": _company(),
			"transaction_date": date,
			"valid_till": _check_validity(values.get("valable"), date),
			"quotation_number": cstr(values.get("reference")).strip() or None,
			"buying_price_list": buying_price_list(),
		}
	)
	set_lines(doc, lignes)
	set_purchase_taxes(doc, cstr(values.get("taxes")).strip())
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_devis_fournisseur(name, modified, values=None):
	"""Brouillon seulement : lignes, validité, référence et TVA. Les champs absents ne changent pas."""
	doc = _for_work(name, modified, "modifier")
	values = _parse(values) or {}
	if "lignes" in values:
		set_lines(doc, clean_lines(values["lignes"]))
	if "valable" in values:
		doc.valid_till = _check_validity(values["valable"], doc.transaction_date)
	if "reference" in values:
		doc.quotation_number = cstr(values["reference"]).strip() or None
	if "taxes" in values:
		set_purchase_taxes(doc, cstr(values["taxes"]).strip())
	doc.save()
	return _devis_payload(doc)


@frappe.whitelist(methods=["POST"])
def validate_devis_fournisseur(name, modified):
	doc = _for_work(name, modified, "valider")
	reasons = blocked(doc)
	if reasons:
		frappe.throw(" ".join(reasons))
	doc.submit()
	return _devis_payload(doc)


@frappe.whitelist(methods=["POST"])
def cancel_devis_fournisseur(name, modified):
	doc = _for_work(name, modified, "annuler")
	doc.cancel()
	return _devis_payload(doc)


@frappe.whitelist(methods=["POST"])
def delete_devis_fournisseur(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(DEVIS_F, doc.name)
	return {"deleted": doc.name}


@frappe.whitelist(methods=["POST"])
def create_commande_achat(name, modified, reception):
	"""Commande d'achat en brouillon, reprise du devis par l'outil standard d'ERPNext."""
	from erpnext.buying.doctype.supplier_quotation.supplier_quotation import make_purchase_order

	doc = _for_work(name, modified, "commande")
	if not reception:
		frappe.throw(_("Choisissez la date de réception prévue."))
	if getdate(reception) < getdate(today()):
		frappe.throw(_("La date de réception ne peut pas être passée."))
	frappe.has_permission(COMMANDE_ACHAT, "create", throw=True)
	commande = make_purchase_order(doc.name)
	commande.transaction_date = today()
	commande.schedule_date = getdate(reception)
	for item in commande.items:
		item.schedule_date = commande.schedule_date
	note = replace_disabled_taxes(commande)
	commande.insert()
	return {"commande": commande.name, "note": note, "devis": _devis_payload(frappe.get_doc(DEVIS_F, doc.name))}


def devis_fournisseur_for_bulk(name, modified):
	"""Devis d'une action groupée ou d'un tag : lisible, et dans la version affichée à l'écran."""
	return _load(name, modified)


def bulk_guard(doc, operation):
	if doc.docstatus != 0:
		return _("Devis validé ou annulé : il ne change plus.")
	return None


def _check_activity(name):
	require_bureau()
	frappe.get_doc(DEVIS_F, name).check_permission("read")


@frappe.whitelist()
def get_devis_fournisseur_activity(name):
	require_bureau()
	return activity.get_feed(DEVIS_F, name)


@frappe.whitelist(methods=["POST"])
def add_devis_fournisseur_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(DEVIS_F, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_devis_fournisseur_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(DEVIS_F, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_devis_fournisseur_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(DEVIS_F, name, comment)
