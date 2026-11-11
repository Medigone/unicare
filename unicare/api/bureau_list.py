# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Socle des listes du poste de bureau (/bureau) : filtres, filtres enregistrés, vues, export, actions groupées.

Repris du poste de bureau d'aurescrm. Une liste s'inscrit dans `FILTER_LISTS` (ses filtres courants) ; tout le
reste se lit dans la meta du doctype, avec les droits de la personne. Les listes passent par `frappe.get_list`
pour conserver les permissions, et chaque écriture par `doc.save()`.
"""

import base64
import io
import json
import re
import unicodedata

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, getdate, strip_html
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from unicare.api.bureau_postes import require_bureau

APP_NAME = "unicare"

# Tailles de page : une liste trie ici, sur toute la vue, puis ne renvoie que la page demandée.
DEFAULT_PAGE_LENGTH = 20
MAX_PAGE_LENGTH = 500

# Actions groupées : chaque document est traité à part, et une requête en traite au plus BULK_LIMIT.
BULK_LIMIT = 100
BULK_SAVEPOINT = "bureau_bulk_item"

# Filtre « Cloche » : le cœur du Desk, propre à chaque personne, rangé dans `_liked_by`.
BELL_FILTER = "cloche"
BELL_FIELD = "_liked_by"

# Filtres courants de chaque liste : champ → libellé. Ils passent en tête, et restent proposés quel que soit le niveau de droit du champ.
# Une liste du bureau doit être inscrite ici : les filtres, vues et exports refusent tout autre doctype.
FILTER_LISTS = {
	"Customer": {
		"custom_status": "Statut",
		"customer_group": "Catégorie",
		"custom_wilaya": "Wilaya",
		"custom_commune": "Commune",
		"custom_région": "Région",
		"customer_name": "Raison sociale",
		"_user_tags": "Tag",
	},
	"Supplier": {
		"custom_statut": "Statut",
		"supplier_group": "Catégorie",
		"custom_wilaya": "Wilaya",
		"custom_commune": "Commune",
		"supplier_name": "Raison sociale",
		"_user_tags": "Tag",
	},
	"Item": {
		"custom_type_conditionnement": "Type",
		"item_group": "Groupe",
		"stock_uom": "Unité de stock",
		"has_batch_no": "Géré par lots",
		"is_stock_item": "Article de stock",
		"item_name": "Désignation",
		"_user_tags": "Tag",
	},
	"Quotation": {
		"status": "Statut",
		"party_name": "Client",
		"transaction_date": "Date",
		"valid_till": "Valable jusqu'au",
		"grand_total": "Total TTC",
		"owner": "Créé par",
		"_user_tags": "Tag",
	},
	"Sales Order": {
		"status": "Statut",
		"customer": "Client",
		"transaction_date": "Date",
		"delivery_date": "Livraison",
		"custom_wilaya": "Wilaya",
		"grand_total": "Total TTC",
		"po_no": "Référence client",
		"_user_tags": "Tag",
	},
	"Delivery Note": {
		"status": "Statut",
		"customer": "Client",
		"posting_date": "Date",
		"is_return": "Retour",
		"lr_no": "Nº de transport",
		"grand_total": "Total TTC",
		"_user_tags": "Tag",
	},
	"Sales Invoice": {
		"status": "Statut",
		"customer": "Client",
		"posting_date": "Date",
		"due_date": "Échéance",
		"is_return": "Avoir",
		"grand_total": "Total TTC",
		"outstanding_amount": "Reste dû",
		"_user_tags": "Tag",
	},
	"Payment Entry": {
		"payment_type": "Sens",
		"party_type": "Type de tiers",
		"party": "Tiers",
		"posting_date": "Date",
		"mode_of_payment": "Mode",
		"paid_amount": "Montant",
		"unallocated_amount": "Non affecté",
		"reference_no": "Référence",
		"_user_tags": "Tag",
	},
}

# Conditions du Desk par nature de champ (`frappe/ui/filters/filter.js`), la condition par défaut en tête.
TEXT_CONDITIONS = ["like", "not like", "=", "!=", "in", "not in", "is", ">", "<", ">=", "<="]
CHOICE_CONDITIONS = ["=", "!=", "in", "not in", "is", ">", "<", ">=", "<="]
LINK_CONDITIONS = ["=", "!=", "like", "not like", "in", "not in", "is"]
TREE_CONDITIONS = [
	"descendants of",
	"descendants of (inclusive)",
	"not descendants of",
	"ancestors of",
	"not ancestors of",
]
NUMBER_CONDITIONS = ["=", "!=", ">", "<", ">=", "<=", "is"]
DATE_CONDITIONS = ["Between", "Timespan", "=", "!=", "<", ">", "<=", ">=", "is"]
DATETIME_CONDITIONS = ["Between", "Timespan", "<", ">", "<=", ">=", "is"]
TIMESPANS = {
	"last 7 days", "last 14 days", "last 30 days", "last 90 days", "last week", "last month", "last quarter", "last 6 months", "last year",
	"yesterday", "today", "tomorrow",
	"this week", "this month", "this quarter", "this year",
	"next 7 days", "next 14 days", "next 30 days", "next week", "next month", "next quarter", "next 6 months", "next year",
}  # fmt: skip
LIST_FILTER = "List Filter"
LIST_VIEW = "Vue Liste Bureau"
LIST_VIEW_MAX_COLUMNS = 60
LIST_VIEW_WIDTHS = (56, 800)
LIST_COLUMN_KEY = re.compile(r"^\w{1,140}$")
LINK_SEARCH_LIMIT = 20
EXPORT_LINES_LIMIT = 500
NOBODY = "__nobody__"
INVALID_SHEET_CHARS = re.compile(r"[\\/*?:\[\]]")
NOT_FILTERABLE_TYPES = {
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Button",
	"Table",
	"Table MultiSelect",
	"Password",
	"Fold",
	"Heading",
	"Image",
	"Signature",
	"Geolocation",
}
NUMBER_TYPES = {"Int", "Float", "Currency", "Percent", "Rating", "Duration"}
DATE_TYPES = {"Date", "Datetime"}
SYSTEM_FILTER_FIELDS = [
	("name", "Code", "Data", None),
	("owner", "Créé par", "Link", "User"),
	("creation", "Créé le", "Datetime", None),
	("modified_by", "Modifié par", "Link", "User"),
	("modified", "Modifié le", "Datetime", None),
]


def _filter_conditions(fieldtype, link_doctype=None):
	"""(nature du champ, conditions permises), selon son type."""
	if fieldtype in NUMBER_TYPES:
		return "number", NUMBER_CONDITIONS
	if fieldtype == "Date":
		return "date", DATE_CONDITIONS
	if fieldtype == "Datetime":
		return "date", DATETIME_CONDITIONS
	if fieldtype == "Check":
		return "check", ["="]
	if fieldtype == "Select":
		return "choice", CHOICE_CONDITIONS
	if fieldtype == "Link":
		try:
			tree = bool(link_doctype and frappe.get_meta(link_doctype).is_tree)
		except frappe.DoesNotExistError:
			tree = False
		return "link", LINK_CONDITIONS + TREE_CONDITIONS if tree else LINK_CONDITIONS
	return "text", TEXT_CONDITIONS


def _filter_entry(doctype, fieldname, label, fieldtype, options=None, **extra):
	"""Un champ du panneau de filtres : sa nature, ses conditions et, s'il en a, ses valeurs."""
	link_doctype = options if fieldtype == "Link" else None
	kind, conditions = _filter_conditions(fieldtype, link_doctype)
	entry = {
		"value": f"{doctype}.{fieldname}",
		"doctype": doctype,
		"field": fieldname,
		"label": _(label or fieldname),
		"kind": kind,
		"operators": conditions,
		**extra,
	}
	if link_doctype:
		entry["link_doctype"] = link_doctype
	if kind == "check":
		entry["choices"] = [{"value": "1", "label": _("Oui")}, {"value": "0", "label": _("Non")}]
	elif kind == "choice":
		entry["choices"] = [
			{"value": option, "label": _(option)} for option in cstr(options).split("\n") if option
		]
	return entry


def _filterable(df, permitted):
	return df.fieldtype not in NOT_FILTERABLE_TYPES and not df.is_virtual and df.fieldname in permitted


def _is_own_doctype(meta):
	"""Vrai pour un doctype de cette application : ses champs ne sont pas ceux d'ERPNext."""
	return frappe.db.get_value("Module Def", meta.module, "app_name", cache=True) == APP_NAME


def doctype_filter_fields(doctype, choices=None):
	"""Tout ce qu'on peut filtrer sur une liste : ses filtres courants, puis les champs lisibles du doctype et de ses tables enfants."""
	meta = frappe.get_meta(doctype)
	common = FILTER_LISTS[doctype]
	permitted = set(meta.get_permitted_fieldnames())
	entries = []
	for fieldname, label in common.items():
		df = meta.get_field(fieldname)
		if df:
			entries.append(_filter_entry(doctype, fieldname, label, df.fieldtype, df.options))
		elif fieldname == "_user_tags":
			entries.append(_filter_entry(doctype, fieldname, label, "Data"))
	entries.append(
		{
			"value": f"{doctype}.{BELL_FILTER}",
			"doctype": doctype,
			"field": BELL_FILTER,
			"label": _("Cloche"),
			"kind": "choice",
			"operators": ["=", "!="],
			"choices": [{"value": "1", "label": _("activée")}],
		}
	)
	own_doctype = _is_own_doctype(meta)
	tab = section = None
	for df in meta.fields:
		if df.fieldtype == "Tab Break":
			tab, section = df.label, None
		elif df.fieldtype == "Section Break":
			section = df.label
		if df.fieldname not in common and _filterable(df, permitted):
			entries.append(
				_filter_entry(
					doctype,
					df.fieldname,
					df.label,
					df.fieldtype,
					df.options,
					group=_(section or tab or "Autres champs"),
					own=own_doctype or df.fieldname.startswith("custom_"),
				)
			)
	for fieldname, label, fieldtype, options in SYSTEM_FILTER_FIELDS:
		if fieldname not in common:
			entries.append(
				_filter_entry(doctype, fieldname, label, fieldtype, options, group=_("Suivi"), own=True)
			)
	# `get_permitted_fieldnames` ne contient pas les tables : leur droit se lit à leur niveau d'accès.
	levels = set(meta.get_permlevel_access())
	for table in meta.get_table_fields():
		if table.fieldtype != "Table" or table.permlevel not in levels:
			continue
		child = frappe.get_meta(table.options)
		readable = set(child.get_permitted_fieldnames(parenttype=doctype))
		label = _(table.label or table.options)
		own = table.fieldname.startswith("custom_") or _is_own_doctype(child)
		entries.extend(
			_filter_entry(
				table.options,
				df.fieldname,
				df.label,
				df.fieldtype,
				df.options,
				group=label,
				table=label,
				own=own,
			)
			for df in child.fields
			if _filterable(df, readable)
		)
	for entry in entries:
		if entry["doctype"] == doctype and entry["field"] in (choices or {}):
			entry["choices"] = choices[entry["field"]]
	return entries


def _filter_catalog(doctype):
	return {(entry["doctype"], entry["field"]): entry for entry in doctype_filter_fields(doctype)}


def _require_filter_list(doctype):
	if doctype not in FILTER_LISTS:
		frappe.throw(_("Liste inconnue."))


def _filter_value(entry, op, value):
	"""La valeur attendue par `frappe.get_list`, ou None quand le filtre n'est pas complet. Une valeur mal formée est refusée."""
	text = ",".join(cstr(item) for item in value) if isinstance(value, (list, tuple)) else cstr(value).strip()
	if not text:
		return None
	if op == "is":
		if text not in ("set", "not set"):
			frappe.throw(_("Condition de filtre invalide."))
		return text
	if op == "Timespan":
		if text not in TIMESPANS:
			frappe.throw(_("Condition de filtre invalide."))
		return text
	if op == "Between":
		bounds = [part.strip() for part in text.split(",")]
		if len(bounds) != 2 or not all(bounds):
			return None
		return [str(getdate(bound)) for bound in bounds]
	if op in ("in", "not in"):
		return [part.strip() for part in text.split(",") if part.strip()] or None
	if op in ("like", "not like"):
		return text if "%" in text else f"%{text}%"
	if entry["kind"] == "number":
		return flt(text)
	if entry["kind"] == "date":
		return str(getdate(text))
	if entry["kind"] == "check":
		return cint(text)
	return text


def condition_filters(conditions, doctype):
	"""Traduit les filtres choisis dans une liste, au format du Desk. Tout ce qui n'est pas dans le catalogue de la personne est refusé."""
	if not conditions:
		return []
	_require_filter_list(doctype)
	catalog = _filter_catalog(doctype)
	filters = []
	for condition in conditions:
		table, fieldname, op = (
			cstr(condition.get("doctype")),
			cstr(condition.get("field")),
			cstr(condition.get("op")),
		)
		entry = catalog.get((table, fieldname))
		if not entry:
			frappe.throw(_("Filtre inconnu."))
		if op not in entry["operators"]:
			frappe.throw(_("Condition de filtre invalide."))
		if fieldname == BELL_FILTER:
			# Toujours la personne connectée : le navigateur n'envoie pas d'utilisateur.
			if cstr(condition.get("value")).strip():
				filters.append(
					[doctype, BELL_FIELD, "like" if op == "=" else "not like", f'%"{frappe.session.user}"%']
				)
			continue
		value = _filter_value(entry, op, condition.get("value"))
		if value is None:
			continue
		if value == NOBODY and op in ("=", "!="):
			op, value = "is", "not set" if op == "=" else "set"
		filters.append([table, fieldname, op, value])
	return filters


def has_child_filter(filters, doctype):
	"""Vrai si un filtre passe par une table enfant : plusieurs de ses lignes peuvent alors répondre pour un même document."""
	return any(row[0] != doctype for row in filters if len(row) == 4)


def _condition_from_stored(row, doctype, catalog):
	"""Une ligne de `List Filter`, écrite ici ou sur le Desk, relue comme une condition. None si le champ n'est plus disponible."""
	if not isinstance(row, (list, tuple)) or len(row) < 4:
		return None
	table, fieldname, op, value = row[:4]
	if fieldname == BELL_FIELD:
		if op not in ("like", "not like"):
			return None
		return {"doctype": doctype, "field": BELL_FILTER, "op": "=" if op == "like" else "!=", "value": "1"}
	entry = catalog.get((table, fieldname))
	if not entry:
		return None
	op = next((known for known in entry["operators"] if known.lower() == cstr(op).lower()), None)
	if not op:
		return None
	if isinstance(value, (list, tuple)):
		value = ",".join(cstr(item) for item in value)
	elif op in ("like", "not like"):
		value = cstr(value).strip("%")
	return {"doctype": table, "field": fieldname, "op": op, "value": cstr(value)}


def _can_share_filters():
	return "System Manager" in frappe.get_roles()


@frappe.whitelist()
def get_saved_filters(doctype):
	"""Les filtres enregistrés de la personne et ceux de tout le monde : les mêmes que dans le Desk."""
	require_bureau()
	_require_filter_list(doctype)
	user = frappe.session.user
	catalog = _filter_catalog(doctype)
	rows = frappe.get_all(
		LIST_FILTER,
		filters={"reference_doctype": doctype},
		fields=["name", "filter_name", "for_user", "filters"],
		order_by="filter_name asc",
		limit_page_length=0,
	)
	can_share = _can_share_filters()
	saved = []
	for row in rows:
		if row.for_user and row.for_user != user:
			continue
		stored = _parse(row.filters) or []
		conditions = [
			condition
			for condition in (_condition_from_stored(item, doctype, catalog) for item in stored)
			if condition
		]
		saved.append(
			{
				"name": row.name,
				"label": row.filter_name,
				"is_global": not row.for_user,
				"can_delete": bool(row.for_user) or can_share,
				"conditions": conditions,
				"dropped": len(stored) - len(conditions),
			}
		)
	return {"filters": saved, "can_share": can_share}


@frappe.whitelist(methods=["POST"])
def save_filter(doctype, label, conditions, is_global=0):
	"""Enregistre les conditions dans `List Filter`, au format du Desk. Un filtre pour tout le monde demande le rôle System Manager."""
	require_bureau()
	_require_filter_list(doctype)
	label = cstr(label).strip()
	if not label:
		frappe.throw(_("Donnez un nom à ce filtre."))
	if cint(is_global) and not _can_share_filters():
		frappe.throw(_("Seul un System Manager peut partager un filtre."), frappe.PermissionError)
	user = frappe.session.user
	existing = frappe.get_all(
		LIST_FILTER,
		filters={"reference_doctype": doctype, "filter_name": label},
		fields=["for_user"],
		limit_page_length=0,
	)
	if any(not row.for_user or row.for_user == user for row in existing):
		frappe.throw(_("Un filtre porte déjà ce nom."))
	filters = condition_filters(_parse(conditions), doctype)
	if not filters:
		frappe.throw(_("Ce filtre n'a aucune condition complète."))
	# Le rôle Desk User n'est pas exigé sur /bureau : les règles ci-dessus tiennent lieu de droits.
	doc = frappe.get_doc(
		{
			"doctype": LIST_FILTER,
			"reference_doctype": doctype,
			"filter_name": label,
			"for_user": "" if cint(is_global) else user,
			"filters": json.dumps([[*row, False] for row in filters]),
		}
	).insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist(methods=["POST"])
def delete_saved_filter(name):
	"""Retire un filtre : le sien, ou un filtre commun pour un System Manager."""
	require_bureau()
	doc = frappe.get_doc(LIST_FILTER, name)
	if doc.reference_doctype not in FILTER_LISTS:
		frappe.throw(_("Liste inconnue."))
	if doc.for_user != frappe.session.user and (doc.for_user or not _can_share_filters()):
		frappe.throw(_("Ce filtre ne vous appartient pas."), frappe.PermissionError)
	doc.delete(ignore_permissions=True)


def _list_view_default_key(doctype):
	return f"bureau_vue:{doctype}"


def _clean_list_view_config(doctype, config):
	"""Les réglages d'une vue, réduits à ce qu'on attend : le navigateur n'écrit jamais autre chose dans le document."""
	config = _parse(config)
	if not isinstance(config, dict):
		frappe.throw(_("Réglages de vue invalides."))
	catalog = _filter_catalog(doctype)
	fields = {entry["value"] for entry in catalog.values() if entry["field"] != BELL_FILTER}
	columns, seen = [], set()
	for column in config.get("columns") or []:
		key = cstr(column.get("key")) if isinstance(column, dict) else ""
		if key in seen or not (key in fields or LIST_COLUMN_KEY.match(key)):
			frappe.throw(_("Colonne inconnue : {0}").format(key))
		seen.add(key)
		cleaned = {"key": key}
		if column.get("width"):
			cleaned["width"] = min(max(cint(column["width"]), LIST_VIEW_WIDTHS[0]), LIST_VIEW_WIDTHS[1])
		columns.append(cleaned)
	if not columns or len(columns) > LIST_VIEW_MAX_COLUMNS:
		frappe.throw(_("Une vue compte de 1 à {0} colonnes.").format(LIST_VIEW_MAX_COLUMNS))
	sort = config.get("sort")
	if sort and (
		not isinstance(sort, dict)
		or sort.get("dir") not in ("asc", "desc")
		or not LIST_COLUMN_KEY.match(cstr(sort.get("key")))
	):
		frappe.throw(_("Tri invalide."))
	conditions = [
		{
			"doctype": cstr(item.get("doctype")),
			"field": cstr(item.get("field")),
			"op": cstr(item.get("op")),
			"value": cstr(item.get("value")),
		}
		for item in config.get("conditions") or []
		if isinstance(item, dict)
	]
	# Refuse un champ ou une condition absents du catalogue de la personne.
	condition_filters(conditions, doctype)
	return {
		"columns": columns,
		"sort": {"key": sort["key"], "dir": sort["dir"]} if sort else None,
		"view": cstr(config.get("view")),
		"conditions": conditions,
	}


def _list_view_for_reader(row, catalog):
	"""Une vue telle que la personne peut l'ouvrir : sans les colonnes ni les filtres dont le champ ne lui est plus disponible."""
	config = _parse(row.config) or {}
	fields = {entry["value"] for entry in catalog.values() if entry["field"] != BELL_FILTER}
	stored_columns = config.get("columns") or []
	columns = [
		column
		for column in stored_columns
		if "." not in cstr(column.get("key")) or column.get("key") in fields
	]
	stored_conditions = config.get("conditions") or []
	conditions = []
	for condition in stored_conditions:
		entry = catalog.get((cstr(condition.get("doctype")), cstr(condition.get("field"))))
		if entry and cstr(condition.get("op")) in entry["operators"]:
			conditions.append(condition)
	return {
		"name": row.name,
		"label": row.label,
		"is_global": not row.for_user,
		"can_edit": bool(row.for_user) or _can_share_filters(),
		"config": {
			"columns": columns,
			"sort": config.get("sort"),
			"view": cstr(config.get("view")),
			"conditions": conditions,
		},
		"dropped": len(stored_columns) - len(columns) + len(stored_conditions) - len(conditions),
	}


def _check_list_view_label(doctype, label, current=None):
	label = cstr(label).strip()
	if not label:
		frappe.throw(_("Donnez un nom à cette vue."))
	user = frappe.session.user
	rows = frappe.get_all(
		LIST_VIEW,
		filters={"reference_doctype": doctype, "label": label},
		fields=["name", "for_user"],
		limit_page_length=0,
	)
	if any(row.name != current and (not row.for_user or row.for_user == user) for row in rows):
		frappe.throw(_("Une vue porte déjà ce nom."))
	return label


def _list_view_for_write(name):
	"""La vue à modifier : la sienne, ou une vue commune pour un System Manager."""
	doc = frappe.get_doc(LIST_VIEW, name)
	if doc.for_user != frappe.session.user and (doc.for_user or not _can_share_filters()):
		frappe.throw(_("Cette vue ne vous appartient pas."), frappe.PermissionError)
	return doc


@frappe.whitelist()
def get_list_views(doctype):
	"""Les vues de la personne, celles de tout le monde et sa vue par défaut."""
	require_bureau()
	_require_filter_list(doctype)
	user = frappe.session.user
	catalog = _filter_catalog(doctype)
	rows = frappe.get_all(
		LIST_VIEW,
		filters={"reference_doctype": doctype},
		or_filters=[["for_user", "=", user], ["for_user", "is", "not set"]],
		fields=["name", "label", "for_user", "config"],
		order_by="label asc",
		limit_page_length=0,
	)
	views = [_list_view_for_reader(row, catalog) for row in rows]
	default = frappe.defaults.get_user_default(_list_view_default_key(doctype))
	return {
		"views": views,
		"default": default if any(view["name"] == default for view in views) else None,
		"can_share": _can_share_filters(),
	}


@frappe.whitelist(methods=["POST"])
def save_list_view(doctype, label, config, is_global=0, name=None):
	"""Crée une vue, ou met à jour son nom et ses réglages quand `name` est donné. Une vue pour tout le monde demande le rôle System Manager."""
	require_bureau()
	_require_filter_list(doctype)
	config = _clean_list_view_config(doctype, config)
	if name:
		doc = _list_view_for_write(name)
		if doc.reference_doctype != doctype:
			frappe.throw(_("Liste inconnue."))
		doc.label = _check_list_view_label(doctype, label, current=doc.name)
		doc.config = json.dumps(config)
		doc.save(ignore_permissions=True)
		return doc.name
	if cint(is_global) and not _can_share_filters():
		frappe.throw(_("Seul un System Manager peut partager une vue."), frappe.PermissionError)
	# Le rôle Desk User n'est pas exigé sur /bureau : les règles ci-dessus tiennent lieu de droits.
	return (
		frappe.get_doc(
			{
				"doctype": LIST_VIEW,
				"reference_doctype": doctype,
				"label": _check_list_view_label(doctype, label),
				"for_user": "" if cint(is_global) else frappe.session.user,
				"config": json.dumps(config),
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


@frappe.whitelist(methods=["POST"])
def delete_list_view(name):
	"""Retire une vue : la sienne, ou une vue commune pour un System Manager."""
	require_bureau()
	doc = _list_view_for_write(name)
	if frappe.defaults.get_user_default(_list_view_default_key(doc.reference_doctype)) == doc.name:
		frappe.defaults.clear_user_default(_list_view_default_key(doc.reference_doctype))
	doc.delete(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def set_default_list_view(doctype, name=None):
	"""Choisit la vue par défaut de la personne sur cette liste ; sans `name`, revient à la Vue standard."""
	require_bureau()
	_require_filter_list(doctype)
	key = _list_view_default_key(doctype)
	if not name:
		frappe.defaults.clear_user_default(key)
		return
	view = frappe.db.get_value(LIST_VIEW, name, ["reference_doctype", "for_user"], as_dict=True)
	if (
		not view
		or view.reference_doctype != doctype
		or (view.for_user and view.for_user != frappe.session.user)
	):
		frappe.throw(_("Vue inconnue."))
	frappe.defaults.set_user_default(key, name)


def _export_cell(value, fieldtype):
	"""Une valeur lisible dans un fichier : un nombre reste un nombre, et un texte mis en forme perd ses balises."""
	if value is None:
		return ""
	if isinstance(value, (int, float)):
		return value
	return strip_html(cstr(value)) if fieldtype in ("Text Editor", "HTML Editor") else cstr(value)


@frappe.whitelist(methods=["POST"])
def get_export_values(doctype, names, fields):
	"""Valeurs des champs choisis, pour des lignes que la personne peut lire. Plusieurs lignes d'une table enfant se suivent, séparées par des virgules."""
	require_bureau()
	_require_filter_list(doctype)
	names, fields = _parse(names) or [], _parse(fields) or []
	if len(names) > EXPORT_LINES_LIMIT:
		frappe.throw(_("Trop de lignes demandées."))
	catalog = _filter_catalog(doctype)
	own, children = [], {}
	for item in fields:
		table, fieldname = cstr(item.get("doctype")), cstr(item.get("field"))
		if (table, fieldname) not in catalog or fieldname == BELL_FILTER:
			frappe.throw(_("Filtre inconnu."))
		if table == doctype:
			own.append(fieldname)
		else:
			children.setdefault(table, []).append(fieldname)
	# `get_list` applique les droits : une ligne interdite ne revient pas, ni ses lignes enfants.
	rows = frappe.get_list(
		doctype, filters=[["name", "in", names]], fields=["name", *own], limit_page_length=0
	)
	readable = [row.name for row in rows]
	meta = frappe.get_meta(doctype)
	values = {}
	for row in rows:
		values[row.name] = {
			f"{doctype}.{fieldname}": _export_cell(
				row.get(fieldname),
				meta.get_field(fieldname).fieldtype if meta.get_field(fieldname) else "Data",
			)
			for fieldname in own
		}
	for table, fieldnames in children.items():
		child = frappe.get_meta(table)
		for row in frappe.get_all(
			table,
			filters={"parent": ["in", readable], "parenttype": doctype},
			fields=["parent", *fieldnames],
			order_by="idx asc",
			limit_page_length=0,
		):
			for fieldname in fieldnames:
				cell = _export_cell(row.get(fieldname), child.get_field(fieldname).fieldtype)
				if cell == "":
					continue
				key = f"{table}.{fieldname}"
				current = values[row.parent].get(key)
				values[row.parent][key] = cell if current is None else f"{current}, {cell}"
	return values


def link_search_values(target, search, limit=LINK_SEARCH_LIMIT):
	"""Valeurs d'un doctype lié, avec les droits de lecture de la personne."""
	meta = frappe.get_meta(target)
	title = meta.title_field if meta.title_field and meta.has_field(meta.title_field) else None
	value = cstr(search).strip()
	or_filters = None
	if value:
		or_filters = [["name", "like", f"%{value}%"]]
		if title:
			or_filters.append([title, "like", f"%{value}%"])
	filters = []
	if meta.has_field("enabled"):
		filters.append(["enabled", "=", 1])
	if meta.has_field("disabled"):
		filters.append(["disabled", "=", 0])
	rows = frappe.get_list(
		target,
		filters=filters,
		or_filters=or_filters,
		fields=["name", title] if title else ["name"],
		order_by=f"{title or 'name'} asc",
		limit_page_length=limit,
	)
	return [
		{"value": row.name, "label": cstr(row.get(title)) or row.name if title else row.name} for row in rows
	]


@frappe.whitelist()
def search_filter_link(list_doctype, doctype, field, search=None):
	"""Valeurs proposées pour un champ lien du panneau de filtres. Sans droit de lecture sur la cible, on saisit la valeur à la main."""
	require_bureau()
	_require_filter_list(list_doctype)
	entry = _filter_catalog(list_doctype).get((cstr(doctype), cstr(field)))
	if not entry or not entry.get("link_doctype"):
		frappe.throw(_("Filtre inconnu."))
	try:
		return link_search_values(entry["link_doctype"], search)
	except frappe.PermissionError:
		frappe.clear_messages()
		return []


def _sort_text(value):
	"""Texte comparable : sans accents ni casse, pour que « Étui » se range avec les E."""
	decomposed = unicodedata.normalize("NFD", cstr(value))
	return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def page_bounds(total, start, page_length):
	"""Début et taille valides : une page devenue vide ramène à la dernière page qui existe."""
	length = min(max(cint(page_length) or DEFAULT_PAGE_LENGTH, 1), MAX_PAGE_LENGTH)
	first = max(cint(start), 0)
	if first >= total:
		first = max(total - 1, 0) // length * length
	return first, length


def _parse(value):
	return json.loads(value) if isinstance(value, str) and value else value


def row_tags(row):
	"""Tags d'une ligne de liste : la colonne `_user_tags` les range sous la forme « ,tag1,tag2 »."""
	return [tag for tag in cstr(row.get("_user_tags")).split(",") if tag]


def row_bell(row):
	"""La cloche de la personne connectée sur une ligne de liste, lue dans le `_liked_by` du Desk."""
	return frappe.session.user in (_parse(row.get(BELL_FIELD)) or [])


@frappe.whitelist()
def export_xlsx(title, headers, rows):
	"""Classeur Excel des lignes que la liste a déjà lues, en base 64. Un nombre reste un nombre, et tout le reste du texte : rien ne s'exécute à l'ouverture."""
	require_bureau()
	workbook = Workbook()
	sheet = workbook.active
	sheet.title = INVALID_SHEET_CHARS.sub(" ", cstr(title))[:31] or "Export"
	rows = _parse(rows) or []
	headers = _parse(headers) or []
	for row_index, values in enumerate([headers, *rows], start=1):
		for column_index, value in enumerate(values, start=1):
			if isinstance(value, (int, float)):
				cell = sheet.cell(row=row_index, column=column_index, value=value)
			else:
				cell = sheet.cell(
					row=row_index, column=column_index, value=ILLEGAL_CHARACTERS_RE.sub("", cstr(value))
				)
				cell.data_type = "s"
			if row_index == 1:
				cell.font = Font(bold=True)
	sheet.freeze_panes = "A2"
	for column_index, header in enumerate(headers, start=1):
		longest = max(
			(len(cstr(row[column_index - 1])) for row in rows if len(row) >= column_index), default=0
		)
		sheet.column_dimensions[get_column_letter(column_index)].width = min(
			max(longest, len(cstr(header))) + 2, 60
		)
	output = io.BytesIO()
	workbook.save(output)
	return base64.b64encode(output.getvalue()).decode()


def _bulk_apply(items, apply, load):
	"""Applique une écriture à chaque document, séparément : un refus n'empêche pas de traiter les autres.

	`items` : [{name, modified}] tels qu'affichés dans la liste. `load(name, modified)` charge le document et contrôle
	droits et version. `apply(doc)` renvoie la raison de ne pas le traiter, ou None. Chaque
	document est validé à part, pour qu'une requête interrompue garde ce qui est déjà fait.
	"""
	rows = _parse(items) or []
	if not rows:
		frappe.throw(_("Aucune ligne sélectionnée."))
	if len(rows) > BULK_LIMIT:
		frappe.throw(_("Sélectionnez au plus {0} lignes à la fois.").format(BULK_LIMIT))

	done, skipped = [], []
	for row in rows:
		name = cstr(row.get("name"))
		frappe.db.savepoint(BULK_SAVEPOINT)
		try:
			reason = apply(load(name, row.get("modified")))
		except (frappe.ValidationError, frappe.PermissionError) as error:
			frappe.db.rollback(save_point=BULK_SAVEPOINT)
			reason = strip_html(cstr(error)) or _("Action refusée.")
		except Exception:
			frappe.db.rollback(save_point=BULK_SAVEPOINT)
			frappe.log_error(title=f"Poste de bureau : action groupée sur {name}")
			reason = _("Erreur inattendue.")
		# Les messages d'un document ne doivent pas remonter comme une erreur de toute la requête.
		frappe.clear_messages()
		if reason:
			skipped.append({"name": name, "reason": reason})
		else:
			done.append(name)
		frappe.db.commit()
	return {"done": done, "skipped": skipped}
