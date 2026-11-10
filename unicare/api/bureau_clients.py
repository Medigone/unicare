# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Clients du poste de bureau (/bureau/clients) : liste, aperçu, fiche, création et modification.

Repris du poste de bureau d'aurescrm, sans ce qui y est propre (commercial attribué, créances, tickets, visites).
Les listes passent par `frappe.get_list` pour garder les permissions, chaque écriture passe par `doc.insert()` ou
`doc.save()` pour garder validations et hooks, et une modification reçoit la date `modified` affichée à l'écran.
Un document lié que le rôle ne peut pas lire donne une valeur vide, pas une erreur.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, strip_html, validate_email_address

from unicare.api import activity
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

CUSTOMER = "Customer"
GL_ENTRY = "GL Entry"
PHONE_FIELD = "custom_téléphone"
MAIN_PHONE_FIELD = "custom_nº_téléphone_principal"

LIST_FIELDS = [
	"name",
	"modified",
	"creation",
	"customer_name",
	"custom_status",
	"customer_group",
	"custom_wilaya",
	"custom_commune",
	"custom_nom_contact_principal",
	PHONE_FIELD,
	MAIN_PHONE_FIELD,
	"_user_tags",
	BELL_FIELD,
]

VIEWS = {
	"all": lambda row: True,
	"actif": lambda row: row["status"] == "Actif",
	"dormant": lambda row: row["status"] == "Dormant",
	"perdu": lambda row: row["status"] in ("Perdu", "Exclu"),
	"solde": lambda row: flt(row["solde"]) > 0,
}
SORT_KEYS = {
	"client",
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
COMMUNE_SEARCH_LIMIT = 12
CLIENT_SEARCH_LIMIT = 8
# Statut d'un client créé depuis le bureau : unicare n'a pas de prospect, le statut se change ensuite.
NEW_STATUS = "Actif"

# Seuls ces champs se modifient depuis la fenêtre. Le contact principal est un document Contact, pas un champ.
EDITABLE_FIELDS = {
	"customer_name": "customer_name",
	"status": "custom_status",
	"forme_juridique": "custom_forme_juridique",
	"categorie": "customer_group",
	"commune": "custom_commune",
	"gps": "custom_gps",
	"telephone": MAIN_PHONE_FIELD,
	"email": "custom_email_principal_client",
	"rc": "custom_nº_rc",
	"nif": "custom_nº_nif",
	"nis": "custom_nº_nis",
	"ai": "custom_nº_ai",
}
REQUIRED_VALUES = {
	"customer_name": _("Saisissez la raison sociale."),
	"forme_juridique": _("Choisissez la forme juridique."),
	"categorie": _("Choisissez la catégorie."),
	"commune": _("Choisissez la commune."),
}
# Ventes du client : (document, champ du client, champ de la date, statut à afficher).
VENTES = {
	"devis": ("Quotation", "party_name", "transaction_date"),
	"commandes": ("Sales Order", "customer", "transaction_date"),
	"livraisons": ("Delivery Note", "customer", "posting_date"),
	"factures": ("Sales Invoice", "customer", "posting_date"),
}
# Pièce administrative → (libellé, champ du numéro, champ du fichier).
ADMIN_PIECES = {
	"rc": ("Nº RC", "custom_nº_rc", "custom_fichier_rc"),
	"nif": ("Nº NIF", "custom_nº_nif", "custom_fichier_nif"),
	"nis": ("Nº NIS", "custom_nº_nis", "custom_fichier_nis"),
	"ai": ("Nº AI", "custom_nº_ai", "custom_fichier_ai"),
}


def _readable(doctype):
	return frappe.has_permission(doctype, "read")


def _soldes(names=None):
	"""Solde comptable par client (débit moins crédit des écritures non annulées), pour qui peut lire la comptabilité.

	Le montant est dans la devise de chaque société, additionné toutes sociétés confondues : un seul dinar ici.
	"""
	if not _readable(GL_ENTRY):
		return {}
	filters = {"party_type": CUSTOMER, "is_cancelled": 0}
	if names is not None:
		if not names:
			return {}
		filters["party"] = ["in", names]
	rows = frappe.get_all(
		GL_ENTRY,
		filters=filters,
		fields=["party", "sum(debit) - sum(credit) as solde"],
		group_by="party",
	)
	return {row.party: flt(row.solde, 2) for row in rows}


def _list_row(client, soldes):
	return {
		"name": client.name,
		"modified": client.modified,
		"creation": str(client.creation),
		"tags": row_tags(client),
		"cloche": row_bell(client),
		"client": client.customer_name or client.name,
		"status": client.custom_status,
		"categorie": client.customer_group,
		"wilaya": client.custom_wilaya,
		"contact": client.custom_nom_contact_principal,
		"telephone": client.get(MAIN_PHONE_FIELD) or client.get(PHONE_FIELD),
		"solde": soldes.get(client.name, 0) if soldes is not None else None,
	}


def order_clients(rows, sort=None, direction=None):
	"""Par raison sociale, ou par la colonne demandée. Une ligne sans valeur reste à la fin, dans les deux sens."""
	key = sort if sort in SORT_KEYS else "client"
	descending = cstr(direction) == "desc" and sort in SORT_KEYS

	def text(row):
		return cstr(row["client"]).casefold()

	ordered = sorted(rows, key=text)
	filled = [row for row in ordered if row.get(key) not in (None, "")]
	empty = [row for row in ordered if row.get(key) in (None, "")]

	def value(row):
		item = row[key]
		return item if isinstance(item, (int, float)) else cstr(item).casefold()

	# Le tri de Python est stable : à valeur égale, l'ordre alphabétique reste, y compris en sens inverse.
	return sorted(filled, key=value, reverse=descending) + empty


@frappe.whitelist()
def get_clients(
	view="all", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None
):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), CUSTOMER)
	clients = frappe.get_list(
		CUSTOMER,
		filters=[["disabled", "=", 0], *conditions],
		distinct=has_child_filter(conditions, CUSTOMER),
		or_filters=[
			["customer_name", "like", pattern],
			["name", "like", pattern],
			["custom_wilaya", "like", pattern],
			["custom_nom_contact_principal", "like", pattern],
		]
		if value
		else None,
		fields=LIST_FIELDS,
		limit_page_length=0,
	)
	soldes = _soldes() if _readable(GL_ENTRY) else None
	rows = [_list_row(client, soldes) for client in clients]
	counts = {name: sum(1 for row in rows if test(row)) for name, test in VIEWS.items()}
	ordered = order_clients([row for row in rows if VIEWS[view](row)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"clients": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		# Toute la vue, pour aller au client voisin depuis l'aperçu, au-delà de la page affichée.
		"names": [row["name"] for row in ordered],
	}


def _plain(values):
	return [{"value": value, "label": value} for value in values]


def _select_options(fieldname):
	return [
		option
		for option in (frappe.get_meta(CUSTOMER).get_field(fieldname).options or "").split("\n")
		if option
	]


@frappe.whitelist()
def get_client_options():
	"""Valeurs proposées dans les filtres de la liste et dans la fenêtre du client.

	Ces listes de référence ne contiennent que des noms : tout rôle du bureau les reçoit, sans droit sur chacune.
	"""
	require_bureau()
	categories = frappe.get_all(
		"Customer Group", filters={"is_group": 0}, order_by="name asc", pluck="name", limit_page_length=0
	)
	wilayas = frappe.get_all("Wilaya", order_by="name asc", pluck="name", limit_page_length=0)
	return {
		"statuses": _select_options("custom_status"),
		"formes": _select_options("custom_forme_juridique"),
		"categories": categories,
		"wilayas": wilayas,
		"filter_fields": doctype_filter_fields(
			CUSTOMER,
			{
				"customer_group": _plain(categories),
				"custom_wilaya": _plain(wilayas),
			},
		),
	}


@frappe.whitelist()
def search_communes(search=None):
	"""Communes proposées dans la fenêtre : la wilaya et la région en découlent sur le client."""
	require_bureau()
	value = cstr(search).strip()
	return frappe.get_list(
		"Commune",
		or_filters=[["nom", "like", f"%{value}%"], ["wilaya", "like", f"%{value}%"]] if value else None,
		fields=["name", "nom as commune", "wilaya"],
		order_by="nom asc",
		limit_page_length=COMMUNE_SEARCH_LIMIT,
	)


@frappe.whitelist()
def search_clients(search=None):
	"""Clients dont le nom ressemble à la saisie, pour repérer un doublon avant de créer."""
	require_bureau()
	value = cstr(search).strip()
	if not value:
		return []
	clients = frappe.get_list(
		CUSTOMER,
		or_filters=[["customer_name", "like", f"%{value}%"], ["name", "like", f"%{value}%"]],
		fields=["name", "customer_name", "custom_wilaya", "disabled"],
		order_by="customer_name asc",
		limit_page_length=CLIENT_SEARCH_LIMIT,
	)
	return [
		{
			"name": client.name,
			"label": client.customer_name or client.name,
			"wilaya": client.custom_wilaya,
			"disabled": cint(client.disabled),
		}
		for client in clients
	]


def _contacts(doc):
	"""Le contact principal de la fiche, puis les contacts liés au client, sans doublon."""
	contacts = []
	if (
		doc.custom_nom_contact_principal
		or doc.get(MAIN_PHONE_FIELD)
		or doc.get(PHONE_FIELD)
		or doc.custom_email_principal_client
	):
		contacts.append(
			{
				"nom": doc.custom_nom_contact_principal,
				"fonction": None,
				"telephone": doc.get(MAIN_PHONE_FIELD) or doc.get(PHONE_FIELD),
				"email": doc.custom_email_principal_client or doc.custom_email,
				"principal": 1,
			}
		)
	if not _readable("Contact"):
		return contacts
	rows = frappe.db.sql(
		"""
		select trim(concat_ws(' ', c.first_name, c.last_name)) as nom, c.designation as fonction,
			coalesce(nullif(c.mobile_no, ''), c.phone) as telephone, c.email_id as email, c.is_primary_contact as principal
		from `tabContact` c
		join `tabDynamic Link` dl on dl.parent = c.name and dl.parenttype = 'Contact' and dl.link_doctype = 'Customer'
		where dl.link_name = %(name)s
		order by c.is_primary_contact desc, c.name asc
		limit %(limit)s
		""",
		{"name": doc.name, "limit": RELATED_LIMIT},
		as_dict=True,
	)
	known = {cstr(contact["nom"]).casefold() for contact in contacts}
	for row in rows:
		if cstr(row.nom).casefold() in known:
			# Le contact principal de la fiche gagne sa fonction, s'il existe aussi comme contact.
			contacts[0]["fonction"] = contacts[0]["fonction"] or row.fonction
			continue
		row.principal = 0 if contacts else cint(row.principal)
		contacts.append(row)
	return contacts


def _commune_label(name):
	"""Le nom d'une commune est un code (COM-0001) : seul son champ `nom` se lit à l'écran."""
	return (frappe.db.get_value("Commune", name, "nom") if name else None) or name


def parse_gps(value):
	"""« lat, lon » saisi sur la fiche → (lat, lon), ou (None, None) si la saisie n'est pas lisible."""
	parts = [part.strip() for part in cstr(value).replace(";", ",").split(",")]
	if len(parts) != 2:
		return None, None
	try:
		lat, lon = float(parts[0]), float(parts[1])
	except ValueError:
		return None, None
	if not (-90 <= lat <= 90 and -180 <= lon <= 180):
		return None, None
	return lat, lon


def _ventes(name):
	"""Dernières pièces de vente par nature. `None` : la personne ne lit pas ce document, l'onglet n'en parle pas."""
	result = {}
	for key, (doctype, field, date_field) in VENTES.items():
		if not _readable(doctype):
			result[key] = None
			continue
		filters = {field: name, "docstatus": ["<", 2]}
		if doctype == "Quotation":
			filters["quotation_to"] = CUSTOMER
		fields = ["name", f"{date_field} as date", "grand_total as total", "status", "currency"]
		if doctype == "Sales Invoice":
			fields.append("outstanding_amount as reste")
		result[key] = frappe.get_list(
			doctype,
			filters=filters,
			fields=fields,
			order_by=f"{date_field} desc, creation desc",
			limit_page_length=RELATED_LIMIT,
		)
	return result


def _comptabilite(name):
	"""Solde et dernières écritures du client, une ligne par pièce comptable. `None` sans droit sur la comptabilité."""
	if not _readable(GL_ENTRY):
		return None
	filters = {"party_type": CUSTOMER, "party": name, "is_cancelled": 0}
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
		"solde": flt(flt(totals.debit) - flt(totals.credit), 2),
		"ecritures": [{**row, "debit": flt(row.debit, 2), "credit": flt(row.credit, 2)} for row in ecritures],
	}


def _client_payload(doc, full=False):
	"""Ce que montrent l'aperçu et, avec `full`, la fiche : ventes, comptabilité et commentaires en plus."""
	lat, lon = parse_gps(doc.custom_gps)
	solde = _soldes([doc.name]).get(doc.name, 0) if _readable(GL_ENTRY) else None
	payload = {
		"name": doc.name,
		"modified": doc.modified,
		"tags": row_tags(doc.as_dict()),
		"client": doc.customer_name or doc.name,
		"status": doc.custom_status,
		"forme_juridique": doc.custom_forme_juridique,
		"categorie": doc.customer_group,
		"commune": doc.custom_commune,
		"commune_label": _commune_label(doc.custom_commune),
		"wilaya": doc.custom_wilaya,
		"region": doc.get("custom_région"),
		"adresse": doc.primary_address and strip_html(doc.primary_address).strip(),
		"gps": doc.custom_gps,
		"map_url": f"https://www.google.com/maps?q={lat},{lon}" if lat is not None else None,
		"depuis": str(doc.creation)[:10],
		"contact": doc.custom_nom_contact_principal,
		"telephone": doc.get(MAIN_PHONE_FIELD) or doc.get(PHONE_FIELD),
		"email": doc.custom_email_principal_client or doc.custom_email,
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
				"ventes": _ventes(doc.name),
				"comptabilite": _comptabilite(doc.name),
				"comments": activity.comment_summary(CUSTOMER, doc.name),
			}
		)
	return payload


@frappe.whitelist()
def get_client(name, full=0):
	require_bureau()
	doc = frappe.get_doc(CUSTOMER, name)
	doc.check_permission("read")
	return _client_payload(doc, full=cint(full))


def _client_for_write(name, modified):
	"""Client à modifier : mêmes droits que le Desk, et version identique à celle affichée à l'écran."""
	require_bureau()
	doc = frappe.get_doc(CUSTOMER, name)
	doc.check_permission("write")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Ce client vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."
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


def _check_unique_name(customer_name, current=None):
	"""La raison sociale s'enregistre en majuscules (CustomCustomer) : deux clients ne la partagent pas."""
	label = cstr(customer_name).strip().upper()
	existing = frappe.db.get_value(CUSTOMER, {"customer_name": label}, "name")
	if existing and existing != current:
		frappe.throw(_("Un client « {0} » existe déjà ({1}).").format(label, existing))


def _check_choices(values):
	"""Les listes fermées de la fenêtre : le serveur refuse une valeur hors liste, même envoyée à la main."""
	for key, fieldname in (("status", "custom_status"), ("forme_juridique", "custom_forme_juridique")):
		if values.get(key) and values[key] not in _select_options(fieldname):
			frappe.throw(_("Valeur inconnue : {0}.").format(values[key]))
	if values.get("categorie") and not frappe.db.exists(
		"Customer Group", {"name": values["categorie"], "is_group": 0}
	):
		frappe.throw(_("Choisissez une catégorie de la liste."))
	if values.get("commune") and not frappe.db.exists("Commune", values["commune"]):
		frappe.throw(_("Choisissez une commune de la liste."))
	if values.get("gps") and parse_gps(values["gps"]) == (None, None):
		frappe.throw(_("Saisissez le GPS sous la forme « latitude, longitude »."))
	for key in ("email", "contact_email"):
		if values.get(key):
			validate_email_address(values[key], throw=True)


def _new_contact(customer, values):
	"""Le contact principal, comme le bouton « Ajouter Contact » du Desk : un document Contact lié au client."""
	if not frappe.has_permission("Contact", "create"):
		frappe.throw(
			_("Votre rôle ne peut pas créer de contact : laissez le contact vide."), frappe.PermissionError
		)
	contact = frappe.new_doc("Contact")
	contact.first_name = values["contact"]
	contact.designation = values.get("fonction") or None
	contact.is_primary_contact = 1
	contact.append("links", {"link_doctype": CUSTOMER, "link_name": customer.name})
	if values.get("contact_telephone"):
		contact.append("phone_nos", {"phone": values["contact_telephone"], "is_primary_mobile_no": 1})
	if values.get("contact_email"):
		contact.append("email_ids", {"email_id": values["contact_email"], "is_primary": 1})
	contact.insert()
	return contact


@frappe.whitelist(methods=["POST"])
def create_client(values=None):
	"""Crée un client actif, et son contact principal si un nom est saisi. Tout ou rien : un refus annule les deux."""
	require_bureau()
	frappe.has_permission(CUSTOMER, "create", throw=True)
	values = _clean_values(values)
	_check_required(values, REQUIRED_VALUES)
	if not values.get("contact") and any(
		values.get(key) for key in ("fonction", "contact_telephone", "contact_email")
	):
		frappe.throw(_("Saisissez le nom du contact."))
	_check_unique_name(values["customer_name"])
	_check_choices(values)
	doc = frappe.new_doc(CUSTOMER)
	doc.update(
		{
			"customer_name": values["customer_name"],
			"customer_type": "Company",
			"custom_status": NEW_STATUS,
			"custom_forme_juridique": values["forme_juridique"],
			"customer_group": values["categorie"],
			"custom_commune": values["commune"],
			"custom_gps": values.get("gps") or None,
			MAIN_PHONE_FIELD: values.get("telephone") or None,
			"custom_email_principal_client": values.get("email") or None,
			**{
				fieldname: values.get(key) or None for key, (_label, fieldname, _file) in ADMIN_PIECES.items()
			},
		}
	)
	doc.insert()
	if values.get("contact"):
		contact = _new_contact(doc, values)
		doc.customer_primary_contact = contact.name
		doc.custom_nom_contact_principal = values["contact"]
		doc.set(PHONE_FIELD, values.get("contact_telephone") or None)
		doc.custom_email = values.get("contact_email") or None
		doc.save()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_client(name, modified, values=None):
	doc = _client_for_write(name, modified)
	values = {key: value for key, value in _clean_values(values).items() if key in EDITABLE_FIELDS}
	_check_required(values, [key for key in REQUIRED_VALUES if key in values])
	if "status" in values and not values["status"]:
		frappe.throw(_("Choisissez le statut du client."))
	if "customer_name" in values:
		_check_unique_name(values["customer_name"], name)
	_check_choices(values)
	for key, value in values.items():
		doc.set(EDITABLE_FIELDS[key], value or None)
	doc.save()
	return _client_payload(doc, full=True)


def bind_file(doctype, name, fieldname, file_url):
	"""Rattache au champ le fichier déjà joint au document.

	Sans cela, Frappe crée une seconde ligne `File` à l'enregistrement, et le fil annonce le fichier deux fois.
	"""
	free = frappe.db.get_value(
		"File",
		{
			"file_url": file_url,
			"attached_to_doctype": doctype,
			"attached_to_name": name,
			"attached_to_field": ["is", "not set"],
		},
		"name",
	)
	if free:
		frappe.db.set_value("File", free, "attached_to_field", fieldname, update_modified=False)


@frappe.whitelist(methods=["POST"])
def set_client_piece(name, modified, piece, file_url):
	"""Range un fichier déjà envoyé dans la pièce administrative choisie."""
	doc = _client_for_write(name, modified)
	if piece not in ADMIN_PIECES:
		frappe.throw(_("Pièce inconnue."))
	if not frappe.db.exists(
		"File", {"file_url": file_url, "attached_to_doctype": CUSTOMER, "attached_to_name": name}
	):
		frappe.throw(_("Ce fichier n'est pas joint à ce client."))
	bind_file(CUSTOMER, name, ADMIN_PIECES[piece][2], file_url)
	doc.set(ADMIN_PIECES[piece][2], file_url)
	doc.save()
	return _client_payload(doc, full=True)


# Fil du client : mêmes commentaires que la timeline du Desk. Lire le client suffit pour commenter, comme sur le Desk.
@frappe.whitelist()
def get_client_activity(name):
	require_bureau()
	return activity.get_feed(CUSTOMER, name)


@frappe.whitelist(methods=["POST"])
def add_client_comment(name, text, mentions=None):
	require_bureau()
	return activity.add_comment(CUSTOMER, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_client_comment(name, comment, text, mentions=None):
	require_bureau()
	return activity.update_comment(CUSTOMER, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_client_comment(name, comment):
	require_bureau()
	return activity.delete_comment(CUSTOMER, name, comment)


@frappe.whitelist()
def get_mention_candidates():
	require_bureau()
	return activity.mention_candidates()
