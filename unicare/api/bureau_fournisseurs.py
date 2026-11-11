# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Fournisseurs du poste de bureau (/bureau/fournisseurs) : liste, aperçu, fiche, création et modification.

Le pendant des clients (`bureau_clients`) pour le Supplier d'ERPNext. Mêmes règles : les listes passent par
`frappe.get_list`, chaque écriture par `doc.insert()` ou `doc.save()`, une modification reçoit la date `modified`
affichée à l'écran. Le solde se lit du côté du fournisseur : crédit moins débit, ce que la société lui doit.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, strip_html, validate_email_address

from unicare.api import activity
from unicare.api.bureau_clients import ADMIN_PIECES, bind_file
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

SUPPLIER = "Supplier"
GL_ENTRY = "GL Entry"
STATUS_FIELD = "custom_statut"
ACTIF = "Actif"
EXCLU = "Exclu"

LIST_FIELDS = [
	"name",
	"modified",
	"creation",
	"supplier_name",
	STATUS_FIELD,
	"supplier_group",
	"custom_wilaya",
	"custom_commune",
	"supplier_primary_contact",
	"mobile_no",
	"email_id",
	"_user_tags",
	BELL_FIELD,
]

VIEWS = {
	"all": lambda row: True,
	"actif": lambda row: row["status"] == ACTIF,
	"exclu": lambda row: row["status"] == EXCLU,
	"solde": lambda row: flt(row["solde"]) > 0,
}
SORT_KEYS = {
	"fournisseur",
	"status",
	"categorie",
	"wilaya",
	"contact",
	"telephone",
	"solde",
	"name",
	"creation",
	"modified",
}

RELATED_LIMIT = 50
SUPPLIER_SEARCH_LIMIT = 8

EDITABLE_FIELDS = {
	"supplier_name": "supplier_name",
	"status": STATUS_FIELD,
	"categorie": "supplier_group",
	"commune": "custom_commune",
	"rc": "custom_nº_rc",
	"nif": "custom_nº_nif",
	"nis": "custom_nº_nis",
	"ai": "custom_nº_ai",
}
REQUIRED_VALUES = {
	"supplier_name": _("Saisissez la raison sociale."),
	"categorie": _("Choisissez la catégorie."),
}
# Achats du fournisseur : (document, champ du fournisseur, champ de la date).
ACHATS = {
	"devis": ("Supplier Quotation", "supplier", "transaction_date"),
	"commandes": ("Purchase Order", "supplier", "transaction_date"),
	"receptions": ("Purchase Receipt", "supplier", "posting_date"),
	"factures": ("Purchase Invoice", "supplier", "posting_date"),
}


def _readable(doctype):
	return frappe.has_permission(doctype, "read")


def _soldes(names=None):
	"""Ce que la société doit à chaque fournisseur (crédit moins débit), pour qui peut lire la comptabilité."""
	if not _readable(GL_ENTRY):
		return {}
	filters = {"party_type": SUPPLIER, "is_cancelled": 0}
	if names is not None:
		if not names:
			return {}
		filters["party"] = ["in", names]
	rows = frappe.get_all(
		GL_ENTRY,
		filters=filters,
		fields=["party", "sum(credit) - sum(debit) as solde"],
		group_by="party",
	)
	return {row.party: flt(row.solde, 2) for row in rows}


def _contact_names(names):
	"""Nom lisible du contact principal de chaque fournisseur (le champ ne porte que l'identifiant du Contact)."""
	if not names or not _readable("Contact"):
		return {}
	rows = frappe.get_all(
		"Contact",
		filters={"name": ["in", list(names)]},
		fields=["name", "first_name", "last_name"],
	)
	return {row.name: " ".join(part for part in (row.first_name, row.last_name) if part) for row in rows}


def _list_row(fournisseur, soldes, contacts):
	contact = fournisseur.supplier_primary_contact
	return {
		"name": fournisseur.name,
		"modified": fournisseur.modified,
		"creation": str(fournisseur.creation),
		"tags": row_tags(fournisseur),
		"cloche": row_bell(fournisseur),
		"fournisseur": fournisseur.supplier_name or fournisseur.name,
		"status": fournisseur.get(STATUS_FIELD),
		"categorie": fournisseur.supplier_group,
		"wilaya": fournisseur.custom_wilaya,
		"contact": (contacts.get(contact) or contact) if contact else None,
		"telephone": fournisseur.mobile_no,
		"solde": soldes.get(fournisseur.name, 0) if soldes is not None else None,
	}


def order_fournisseurs(rows, sort=None, direction=None):
	"""Par raison sociale, ou par la colonne demandée. Une ligne sans valeur reste à la fin, dans les deux sens."""
	key = sort if sort in SORT_KEYS else "fournisseur"
	descending = cstr(direction) == "desc" and sort in SORT_KEYS
	ordered = sorted(rows, key=lambda row: cstr(row["fournisseur"]).casefold())
	filled = [row for row in ordered if row.get(key) not in (None, "")]
	empty = [row for row in ordered if row.get(key) in (None, "")]

	def value(row):
		item = row[key]
		return item if isinstance(item, (int, float)) else cstr(item).casefold()

	return sorted(filled, key=value, reverse=descending) + empty


@frappe.whitelist()
def get_fournisseurs(
	view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None
):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), SUPPLIER)
	fournisseurs = frappe.get_list(
		SUPPLIER,
		filters=[["disabled", "=", 0], *conditions],
		distinct=has_child_filter(conditions, SUPPLIER),
		or_filters=[
			["supplier_name", "like", pattern],
			["name", "like", pattern],
			["custom_wilaya", "like", pattern],
			["supplier_group", "like", pattern],
		]
		if value
		else None,
		fields=LIST_FIELDS,
		limit_page_length=0,
	)
	soldes = _soldes() if _readable(GL_ENTRY) else None
	contacts = _contact_names({row.supplier_primary_contact for row in fournisseurs if row.supplier_primary_contact})
	rows = [_list_row(row, soldes, contacts) for row in fournisseurs]
	counts = {name: sum(1 for row in rows if test(row)) for name, test in VIEWS.items()}
	ordered = order_fournisseurs([row for row in rows if VIEWS[view](row)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"fournisseurs": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


def _plain(values):
	return [{"value": value, "label": value} for value in values]


def _statuses():
	return [
		option
		for option in (frappe.get_meta(SUPPLIER).get_field(STATUS_FIELD).options or "").split("\n")
		if option
	]


def _categories():
	return frappe.get_all(
		"Supplier Group", filters={"is_group": 0}, order_by="name asc", pluck="name", limit_page_length=0
	)


@frappe.whitelist()
def get_fournisseur_options():
	"""Valeurs proposées dans les filtres de la liste et dans la fenêtre du fournisseur."""
	require_bureau()
	categories = _categories()
	wilayas = frappe.get_all("Wilaya", order_by="name asc", pluck="name", limit_page_length=0)
	return {
		"statuses": _statuses(),
		"categories": categories,
		"wilayas": wilayas,
		"filter_fields": doctype_filter_fields(
			SUPPLIER,
			{"supplier_group": _plain(categories), "custom_wilaya": _plain(wilayas)},
		),
	}


@frappe.whitelist()
def search_fournisseurs(search=None, actifs=0):
	"""Fournisseurs dont le nom ressemble à la saisie : doublon à la création, ou choix du fournisseur d'une pièce.

	`actifs` : seulement ceux à qui l'on peut acheter (ni désactivés ni exclus).
	"""
	require_bureau()
	value = cstr(search).strip()
	if not value and not cint(actifs):
		return []
	filters = {"disabled": 0, STATUS_FIELD: ["!=", EXCLU]} if cint(actifs) else None
	rows = frappe.get_list(
		SUPPLIER,
		filters=filters,
		or_filters=[["supplier_name", "like", f"%{value}%"], ["name", "like", f"%{value}%"]] if value else None,
		fields=["name", "supplier_name", "custom_wilaya", "disabled", STATUS_FIELD],
		order_by="supplier_name asc",
		limit_page_length=SUPPLIER_SEARCH_LIMIT,
	)
	return [
		{
			"name": row.name,
			"label": row.supplier_name or row.name,
			"wilaya": row.custom_wilaya,
			"disabled": cint(row.disabled) or int(row.get(STATUS_FIELD) == EXCLU),
		}
		for row in rows
	]


def _contacts(doc):
	"""Contacts liés au fournisseur, le principal d'abord."""
	if not _readable("Contact"):
		return []
	rows = frappe.db.sql(
		"""
		select c.name, trim(concat_ws(' ', c.first_name, c.last_name)) as nom, c.designation as fonction,
			coalesce(nullif(c.mobile_no, ''), c.phone) as telephone, c.email_id as email, c.is_primary_contact as principal
		from `tabContact` c
		join `tabDynamic Link` dl on dl.parent = c.name and dl.parenttype = 'Contact' and dl.link_doctype = 'Supplier'
		where dl.link_name = %(name)s
		order by (c.name = %(primary)s) desc, c.is_primary_contact desc, c.name asc
		limit %(limit)s
		""",
		{"name": doc.name, "primary": doc.supplier_primary_contact or "", "limit": RELATED_LIMIT},
		as_dict=True,
	)
	contacts = []
	for index, row in enumerate(rows):
		principal = row.name == doc.supplier_primary_contact or (not doc.supplier_primary_contact and index == 0)
		contacts.append(
			{
				"nom": row.nom,
				"fonction": row.fonction,
				"telephone": row.telephone,
				"email": row.email,
				"principal": int(principal),
			}
		)
	return contacts


def _commune_label(name):
	return (frappe.db.get_value("Commune", name, "nom") if name else None) or name


def _achats(name):
	"""Dernières pièces d'achat par nature. `None` : la personne ne lit pas ce document."""
	result = {}
	for key, (doctype, field, date_field) in ACHATS.items():
		if not _readable(doctype):
			result[key] = None
			continue
		fields = ["name", f"{date_field} as date", "grand_total as total", "status", "currency", "docstatus"]
		if doctype == "Purchase Invoice":
			fields.append("outstanding_amount as reste")
		rows = frappe.get_list(
			doctype,
			filters={field: name, "docstatus": ["<", 2]},
			fields=fields,
			order_by=f"{date_field} desc, creation desc",
			limit_page_length=RELATED_LIMIT,
		)
		for row in rows:
			if cint(row.pop("docstatus")) == 0:
				row.status = "Draft"
		result[key] = rows
	return result


def _comptabilite(name):
	"""Solde et dernières écritures du fournisseur. `None` sans droit sur la comptabilité."""
	if not _readable(GL_ENTRY):
		return None
	filters = {"party_type": SUPPLIER, "party": name, "is_cancelled": 0}
	totals = frappe.get_all(
		GL_ENTRY, filters=filters, fields=["sum(debit) as debit", "sum(credit) as credit"]
	)[0]
	ecritures = frappe.get_all(
		GL_ENTRY,
		filters=filters,
		fields=[
			"voucher_type",
			"voucher_no",
			"max(posting_date) as date",
			"sum(debit) as debit",
			"sum(credit) as credit",
		],
		group_by="voucher_type, voucher_no",
		order_by="date desc, voucher_no desc",
		limit_page_length=RELATED_LIMIT,
	)
	return {
		"debit": flt(totals.debit, 2),
		"credit": flt(totals.credit, 2),
		"solde": flt(flt(totals.credit) - flt(totals.debit), 2),
		"ecritures": [{**row, "debit": flt(row.debit, 2), "credit": flt(row.credit, 2)} for row in ecritures],
	}


def _fournisseur_payload(doc, full=False):
	"""Ce que montrent l'aperçu et, avec `full`, la fiche : achats, comptabilité et commentaires en plus."""
	solde = _soldes([doc.name]).get(doc.name, 0) if _readable(GL_ENTRY) else None
	payload = {
		"name": doc.name,
		"modified": doc.modified,
		"tags": row_tags(doc.as_dict()),
		"fournisseur": doc.supplier_name or doc.name,
		"status": doc.get(STATUS_FIELD),
		"categorie": doc.supplier_group,
		"type": doc.supplier_type,
		"pays": doc.country,
		"commune": doc.custom_commune,
		"commune_label": _commune_label(doc.custom_commune),
		"wilaya": doc.custom_wilaya,
		"adresse": doc.primary_address and strip_html(doc.primary_address).strip(),
		"depuis": str(doc.creation)[:10],
		"telephone": doc.mobile_no,
		"email": doc.email_id,
		"solde": solde,
		"pieces": [
			{"key": key, "label": label, "numero": doc.get(number), "fichier": doc.get(file)}
			for key, (label, number, file) in ADMIN_PIECES.items()
		],
		"contacts": _contacts(doc),
		"can_edit": bool(doc.has_permission("write")),
	}
	if full:
		payload.update(
			{
				"achats": _achats(doc.name),
				"comptabilite": _comptabilite(doc.name),
				"comments": activity.comment_summary(SUPPLIER, doc.name),
			}
		)
	return payload


@frappe.whitelist()
def get_fournisseur(name, full=0):
	require_bureau()
	doc = frappe.get_doc(SUPPLIER, name)
	doc.check_permission("read")
	return _fournisseur_payload(doc, full=cint(full))


def _fournisseur_for_write(name, modified):
	"""Fournisseur à modifier : mêmes droits que le Desk, et version identique à celle affichée à l'écran."""
	require_bureau()
	doc = frappe.get_doc(SUPPLIER, name)
	doc.check_permission("write")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Ce fournisseur vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	return doc


def _clean_values(values):
	values = _parse(values) or {}
	return {key: cstr(value).strip() for key, value in values.items()}


def _check_required(values, keys):
	for key in keys:
		if not values.get(key):
			frappe.throw(REQUIRED_VALUES[key])


def _check_unique_name(supplier_name, current=None):
	"""Deux fournisseurs ne partagent pas la même raison sociale, à la casse près."""
	label = cstr(supplier_name).strip()
	existing = frappe.db.sql(
		"select name from `tabSupplier` where lower(supplier_name) = lower(%s) and name != %s limit 1",
		(label, current or ""),
	)
	if existing:
		frappe.throw(_("Un fournisseur « {0} » existe déjà ({1}).").format(label, existing[0][0]))


def _check_choices(values):
	"""Les listes fermées de la fenêtre : le serveur refuse une valeur hors liste, même envoyée à la main."""
	if values.get("status") and values["status"] not in _statuses():
		frappe.throw(_("Valeur inconnue : {0}.").format(values["status"]))
	if values.get("categorie") and not frappe.db.exists(
		"Supplier Group", {"name": values["categorie"], "is_group": 0}
	):
		frappe.throw(_("Choisissez une catégorie de la liste."))
	if values.get("commune") and not frappe.db.exists("Commune", values["commune"]):
		frappe.throw(_("Choisissez une commune de la liste."))
	if values.get("contact_email"):
		validate_email_address(values["contact_email"], throw=True)


def _new_contact(supplier, values):
	"""Le contact principal, comme le bouton « Ajouter Contact » du Desk : un document Contact lié au fournisseur."""
	if not frappe.has_permission("Contact", "create"):
		frappe.throw(
			_("Votre rôle ne peut pas créer de contact : laissez le contact vide."), frappe.PermissionError
		)
	contact = frappe.new_doc("Contact")
	contact.first_name = values["contact"]
	contact.designation = values.get("fonction") or None
	contact.is_primary_contact = 1
	contact.append("links", {"link_doctype": SUPPLIER, "link_name": supplier.name})
	if values.get("contact_telephone"):
		contact.append("phone_nos", {"phone": values["contact_telephone"], "is_primary_mobile_no": 1})
	if values.get("contact_email"):
		contact.append("email_ids", {"email_id": values["contact_email"], "is_primary": 1})
	contact.insert()
	return contact


@frappe.whitelist(methods=["POST"])
def create_fournisseur(values=None):
	"""Crée un fournisseur actif, et son contact principal si un nom est saisi. Tout ou rien."""
	require_bureau()
	frappe.has_permission(SUPPLIER, "create", throw=True)
	values = _clean_values(values)
	_check_required(values, REQUIRED_VALUES)
	if not values.get("contact") and any(
		values.get(key) for key in ("fonction", "contact_telephone", "contact_email")
	):
		frappe.throw(_("Saisissez le nom du contact."))
	_check_unique_name(values["supplier_name"])
	_check_choices(values)
	doc = frappe.new_doc(SUPPLIER)
	doc.update(
		{
			"supplier_name": values["supplier_name"],
			"supplier_type": "Company",
			STATUS_FIELD: ACTIF,
			"supplier_group": values["categorie"],
			"custom_commune": values.get("commune") or None,
			**{
				fieldname: values.get(key) or None for key, (_label, fieldname, _file) in ADMIN_PIECES.items()
			},
		}
	)
	doc.insert()
	if values.get("contact"):
		contact = _new_contact(doc, values)
		doc.reload()
		doc.supplier_primary_contact = contact.name
		doc.mobile_no = values.get("contact_telephone") or None
		doc.email_id = values.get("contact_email") or None
		doc.save()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_fournisseur(name, modified, values=None):
	doc = _fournisseur_for_write(name, modified)
	values = {key: value for key, value in _clean_values(values).items() if key in EDITABLE_FIELDS}
	_check_required(values, [key for key in REQUIRED_VALUES if key in values])
	if "status" in values and not values["status"]:
		frappe.throw(_("Choisissez le statut du fournisseur."))
	if "supplier_name" in values:
		_check_unique_name(values["supplier_name"], name)
	_check_choices(values)
	for key, value in values.items():
		doc.set(EDITABLE_FIELDS[key], value or None)
	doc.save()
	return _fournisseur_payload(doc, full=True)


@frappe.whitelist(methods=["POST"])
def set_fournisseur_piece(name, modified, piece, file_url):
	"""Range un fichier déjà envoyé dans la pièce administrative choisie."""
	doc = _fournisseur_for_write(name, modified)
	if piece not in ADMIN_PIECES:
		frappe.throw(_("Pièce inconnue."))
	if not frappe.db.exists(
		"File", {"file_url": file_url, "attached_to_doctype": SUPPLIER, "attached_to_name": name}
	):
		frappe.throw(_("Ce fichier n'est pas joint à ce fournisseur."))
	bind_file(SUPPLIER, name, ADMIN_PIECES[piece][2], file_url)
	doc.set(ADMIN_PIECES[piece][2], file_url)
	doc.save()
	return _fournisseur_payload(doc, full=True)


@frappe.whitelist()
def get_fournisseur_activity(name):
	require_bureau()
	return activity.get_feed(SUPPLIER, name)


@frappe.whitelist(methods=["POST"])
def add_fournisseur_comment(name, text, mentions=None):
	require_bureau()
	return activity.add_comment(SUPPLIER, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_fournisseur_comment(name, comment, text, mentions=None):
	require_bureau()
	return activity.update_comment(SUPPLIER, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_fournisseur_comment(name, comment):
	require_bureau()
	return activity.delete_comment(SUPPLIER, name, comment)
