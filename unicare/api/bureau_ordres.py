# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Ordres de conditionnement du poste de bureau (/bureau/ordres) : liste, aperçu, fiche guidée et cycle.

L'Ordre de Conditionnement n'est pas soumettable : son cycle passe par le Workflow `workflow_state`
(Brouillon → Préparé → En production → Terminé, ou Annulé). Les pièces de stock (transfert de préparation, production,
rebuts) naissent et s'annulent dans le doctype lui-même (`on_update`) : ce module ne fait qu'appliquer les transitions
du workflow (`apply_workflow`, avec ses rôles) et écrire les champs que chaque étape laisse modifier.

Pour un utilisateur non technique, les états prennent un nom d'étape (« À planifier », « Prêt à démarrer »…), et la
fiche dit en clair ce qui manque avant l'étape suivante (`manques`), avec les mêmes règles que le doctype.
"""

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.utils import add_days, cint, cstr, flt, get_fullname, getdate, now_datetime, today

from unicare.api import activity
from unicare.api.bureau_devis import _day
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
from unicare.api.bureau_stock import depots, lots_disponibles
from unicare.conditionnement.constants import (
	STATUT_ANNULE,
	STATUT_BROUILLON,
	STATUT_EN_PRODUCTION,
	STATUT_PREPARE,
	STATUT_TERMINE,
)
from unicare.conditionnement.stock import get_batch_available_qty, get_parametres, item_has_batch

ORDRE = "Ordre de Conditionnement"
RECETTE = "Recette de Conditionnement"
CHECKLIST = "Checklist Ordre Conditionnement"
RESPONSABLE = "Responsable Conditionnement"

# Nom d'étape montré à l'utilisateur pour chaque état du workflow.
ETAPES = {
	STATUT_BROUILLON: "À planifier",
	STATUT_PREPARE: "Prêt à démarrer",
	STATUT_EN_PRODUCTION: "En production",
	STATUT_TERMINE: "Terminé",
	STATUT_ANNULE: "Annulé",
}
EN_COURS = (STATUT_BROUILLON, STATUT_PREPARE, STATUT_EN_PRODUCTION)
# Action du workflow → clé de l'interface.
TRANSITIONS = {
	"Préparer": "preparer",
	"Démarrer la production": "demarrer",
	"Clôturer": "cloturer",
	"Annuler": "annuler",
}
WORKFLOW_ACTIONS = {key: action for action, key in TRANSITIONS.items()}

FIELDS = [
	"name",
	"modified",
	"creation",
	"workflow_state",
	"produit_fini",
	"nom_produit",
	"recette",
	"qty_prevue",
	"qty_reelle_pf",
	"qty_rebut",
	"rendement_reel",
	"uom",
	"date_prevue",
	"lot_pf",
	"_user_tags",
	BELL_FIELD,
]
VIEWS = ("all", "en_cours", "a_planifier", "prets", "en_production", "en_retard", "termines", "annules")
SORT_KEYS = {"name", "designation", "etape", "date_prevue", "qty_prevue", "qty_reelle", "rendement", "lot_pf", "creation", "modified"}


def _state(doc_or_row):
	return doc_or_row.get("workflow_state") or STATUT_BROUILLON


def _retard(state, date_prevue):
	return state in EN_COURS and bool(date_prevue) and getdate(date_prevue) < getdate(today())


def in_view(view, row):
	state = row["state"]
	return {
		"all": True,
		"en_cours": state in EN_COURS,
		"a_planifier": state == STATUT_BROUILLON,
		"prets": state == STATUT_PREPARE,
		"en_production": state == STATUT_EN_PRODUCTION,
		"en_retard": row["retard"],
		"termines": state == STATUT_TERMINE,
		"annules": state == STATUT_ANNULE,
	}[view]


def _list_row(ordre):
	state = _state(ordre)
	termine = state == STATUT_TERMINE
	return {
		"name": ordre.name,
		"modified": ordre.modified,
		"creation": str(ordre.creation),
		"tags": row_tags(ordre),
		"cloche": row_bell(ordre),
		"state": state,
		"etape": ETAPES.get(state, state),
		"produit": ordre.produit_fini,
		"designation": ordre.nom_produit or ordre.produit_fini,
		"recette": ordre.recette,
		"date_prevue": _day(ordre.date_prevue),
		"retard": _retard(state, ordre.date_prevue),
		"qty_prevue": flt(ordre.qty_prevue, 3),
		"qty_reelle": flt(ordre.qty_reelle_pf, 3) if termine else None,
		"rendement": flt(ordre.rendement_reel, 1) if termine else None,
		"unite": ordre.uom,
		"lot_pf": ordre.lot_pf or None,
	}


def order_ordres(rows, sort=None, direction=None):
	"""Par défaut : les plus récents d'abord. Une colonne demandée trie la vue entière ; les vides restent à la fin."""
	if sort not in SORT_KEYS:
		return sorted(rows, key=lambda row: (cstr(row["creation"]), cstr(row["name"])), reverse=True)
	descending = cstr(direction) == "desc"
	ordered = sorted(rows, key=lambda row: cstr(row["name"]), reverse=True)
	filled = [row for row in ordered if row.get(sort) not in (None, "")]
	empty = [row for row in ordered if row.get(sort) in (None, "")]

	def value(row):
		item = row[sort]
		return item if isinstance(item, (int, float)) else cstr(item).casefold()

	return sorted(filled, key=value, reverse=descending) + empty


@frappe.whitelist()
def get_ordres(view="en_cours", conditions=None, search=None, start=0, page_length=None, sort=None, direction=None):
	"""Une page de la liste, le total, l'ordre de toute la vue, et les compteurs de toutes les vues pour les mêmes filtres."""
	require_bureau()
	if view not in VIEWS:
		frappe.throw(_("Vue inconnue."))
	value = cstr(search).strip()
	pattern = f"%{value}%"
	conditions = condition_filters(_parse(conditions), ORDRE)
	ordres = frappe.get_list(
		ORDRE,
		filters=conditions,
		distinct=has_child_filter(conditions, ORDRE),
		or_filters=[
			["name", "like", pattern],
			["nom_produit", "like", pattern],
			["produit_fini", "like", pattern],
			["lot_pf", "like", pattern],
		]
		if value
		else None,
		fields=FIELDS,
		limit_page_length=0,
	)
	rows = [_list_row(row) for row in ordres]
	counts = {name: sum(1 for row in rows if in_view(name, row)) for name in VIEWS}
	ordered = order_ordres([row for row in rows if in_view(view, row)], sort, direction)
	first, length = page_bounds(len(ordered), start, page_length)
	return {
		"ordres": ordered[first : first + length],
		"counts": counts,
		"total": len(ordered),
		"start": first,
		"page_length": length,
		"names": [row["name"] for row in ordered],
	}


# Choix proposés dans les fenêtres ---------------------------------------------------------------------------------


def _recettes(produit=None):
	filters = {"actif": 1}
	if produit:
		filters["produit_fini"] = produit
	return frappe.get_all(
		RECETTE,
		filters=filters,
		fields=["name", "produit_fini", "nom_produit", "quantite_base", "uom", "rendement_theorique"],
		order_by="modified desc",
	)


@frappe.whitelist()
def get_ordre_options():
	"""Produits ayant une recette active, recettes, modèles de checklist et dépôts : des noms seulement."""
	require_bureau()
	recettes = _recettes()
	produits = {}
	for row in recettes:
		produits.setdefault(row.produit_fini, {"value": row.produit_fini, "label": row.nom_produit or row.produit_fini})
	return {
		"produits": sorted(produits.values(), key=lambda item: cstr(item["label"]).casefold()),
		"recettes": [
			{
				"value": row.name,
				"produit": row.produit_fini,
				"label": f"{row.name} · pour {_qty(row.quantite_base)} {row.uom or ''}".strip(),
			}
			for row in recettes
		],
		"checklists": frappe.get_all(CHECKLIST, filters={"actif": 1}, order_by="name asc", pluck="name"),
		"depots": depots(),
		"filter_fields": doctype_filter_fields(ORDRE),
	}


def _qty(value):
	return f"{flt(value, 3):g}".replace(".", ",")


def _stock(item_code, warehouse, lot=None):
	if not warehouse:
		return 0
	if lot:
		return flt(get_batch_available_qty(item_code, warehouse, lot), 3)
	return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"), 3)


def _besoins(recette, quantite):
	"""Matières d'une recette pour une quantité, avec leur dépôt par défaut et le stock disponible."""
	from unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement import charger_recette

	data = charger_recette(recette, quantite)
	lignes = []
	for row in data["matieres"]:
		avec_lot = bool(row.get("has_batch_no"))
		lots = lots_disponibles(row["item_code"], row["warehouse"]).get(row["warehouse"], []) if avec_lot else []
		disponible = sum(lot["qty"] for lot in lots) if avec_lot else _stock(row["item_code"], row["warehouse"])
		lignes.append(
			{
				"article": row["item_code"],
				"designation": row.get("item_name") or row["item_code"],
				"type": row.get("type_ingredient"),
				"quantite": flt(row["qty_theorique"], 3),
				"unite": row.get("uom"),
				"depot": row["warehouse"],
				"disponible": flt(disponible, 3),
				"avec_lot": avec_lot,
			}
		)
	return data, lignes


@frappe.whitelist()
def get_besoins(recette, quantite):
	"""Aperçu de la fenêtre « Nouvel ordre » : ce qu'il faut, et ce qu'il y a en stock."""
	require_bureau()
	frappe.has_permission(ORDRE, "create", throw=True)
	if flt(quantite) <= 0:
		return {"lignes": []}
	_data, lignes = _besoins(recette, quantite)
	return {"lignes": lignes}


# Fiche ------------------------------------------------------------------------------------------------------------


def _transitions(doc):
	"""Actions du workflow permises à cette personne sur cet état (rôles du workflow compris)."""
	try:
		return {TRANSITIONS[row.action] for row in get_transitions(doc) if row.action in TRANSITIONS}
	except frappe.ValidationError:
		return set()


def actions(doc):
	state = _state(doc)
	found = set(_transitions(doc))
	write = bool(doc.has_permission("write"))
	if write and state == STATUT_BROUILLON:
		found |= {"modifier", "controler"}
	if write and state in (STATUT_PREPARE, STATUT_EN_PRODUCTION):
		found.add("complement")
	if write and state == STATUT_EN_PRODUCTION:
		found.add("saisir")
	if write and state in EN_COURS and item_has_batch(doc.produit_fini):
		found.add("generer_lot")
	if state == STATUT_BROUILLON and doc.has_permission("delete"):
		found.add("supprimer")
	if frappe.has_permission(ORDRE, "create"):
		found.add("dupliquer")
	order = ["preparer", "demarrer", "cloturer", "modifier", "controler", "saisir", "complement", "generer_lot", "dupliquer", "annuler", "supprimer"]
	return [key for key in order if key in found]


def _matiere(row, state, atelier):
	"""Une ligne de matière. À planifier : stock et lots au dépôt de départ ; ensuite : à l'atelier."""
	avec_lot = item_has_batch(row.item_code)
	lots = []
	if state == STATUT_BROUILLON:
		depot = row.warehouse
		if avec_lot and depot:
			lots = lots_disponibles(row.item_code, depot).get(depot, [])
		disponible = (
			(next((lot["qty"] for lot in lots if lot["lot"] == row.batch_no), 0) if row.batch_no else 0)
			if avec_lot
			else _stock(row.item_code, depot)
		)
	else:
		disponible = _stock(row.item_code, atelier, row.batch_no if avec_lot else None) if state in (STATUT_PREPARE, STATUT_EN_PRODUCTION) else None
	return {
		"name": row.name,
		"article": row.item_code,
		"designation": row.item_name or row.item_code,
		"type": row.type_ingredient or None,
		"avec_lot": avec_lot,
		"lot": row.batch_no or None,
		"lots": lots,
		"depot": row.warehouse or None,
		"prevu": flt(row.qty_theorique, 3),
		"complement": flt(row.qty_complement, 3),
		"utilise": flt(row.qty_reelle, 3),
		"unite": row.uom,
		"disponible": disponible,
	}


def manques_preparation(doc, matieres=None):
	"""Ce qui empêche d'envoyer les matières à l'atelier, en clair (mêmes règles que `validate_preparation`)."""
	found = []
	if not doc.recette:
		found.append({"texte": _("Choisissez la recette."), "cible": "planning"})
	elif not frappe.db.get_value(RECETTE, doc.recette, "actif"):
		found.append({"texte": _("La recette {0} n'est plus active : choisissez-en une autre.").format(doc.recette), "cible": "planning"})
	if not doc.modele_checklist or not frappe.db.get_value(CHECKLIST, doc.modele_checklist, "actif"):
		found.append({"texte": _("Choisissez une checklist active."), "cible": "planning"})
	if not doc.warehouse_atelier or not doc.warehouse_pf:
		found.append({"texte": _("Les dépôts de l'atelier et des produits finis ne sont pas réglés (Réglages de la production)."), "cible": None})
	if not doc.matieres:
		found.append({"texte": _("Aucune matière : vérifiez la recette et la quantité."), "cible": "matieres"})
	for line in matieres or [_matiere(row, STATUT_BROUILLON, None) for row in doc.matieres]:
		nom = line["designation"]
		if line["prevu"] <= 0:
			found.append({"texte": _("{0} : la quantité est à zéro.").format(nom), "cible": line["name"]})
		elif not line["depot"]:
			found.append({"texte": _("{0} : choisissez le dépôt de départ.").format(nom), "cible": line["name"]})
		elif line["avec_lot"] and not line["lot"]:
			found.append({"texte": _("{0} : choisissez le lot.").format(nom), "cible": line["name"]})
		elif line["disponible"] + 0.0001 < line["prevu"]:
			found.append(
				{
					"texte": _("{0} : {1} en stock pour {2} nécessaires ({3}).").format(
						nom, _qty(line["disponible"]), _qty(line["prevu"]), line["depot"]
					),
					"cible": line["name"],
				}
			)
	restants = [row.controle for row in doc.checklist if cint(row.obligatoire) and not cint(row.conforme)]
	if restants:
		found.append(
			{
				"texte": _("{0} contrôle(s) obligatoire(s) à cocher : {1}.").format(len(restants), ", ".join(restants)),
				"cible": "checklist",
			}
		)
	return found


def _etapes(doc):
	"""Les quatre étapes du bandeau : faite, en cours ou à venir (annulée pour celles qu'un ordre annulé n'a pas faites)."""
	state = _state(doc)
	# Étape en cours selon l'état : préparé ou en production, on est à « Produire ».
	courante = {STATUT_BROUILLON: 0, STATUT_PREPARE: 2, STATUT_EN_PRODUCTION: 2, STATUT_TERMINE: 4}.get(state)
	points = [
		("planifier", _("Planifier"), doc.date_heure_preparation, cint(doc.duree_planification)),
		("preparer", _("Préparer"), doc.date_heure_preparation, cint(doc.duree_preparation)),
		("produire", _("Produire"), doc.date_heure_production, cint(doc.duree_production)),
		("cloturer", _("Clôturer"), doc.date_heure_cloture, None),
	]
	etapes = []
	for index, (key, label, quand, duree) in enumerate(points):
		if courante is None:
			statut = "fait" if quand else "annule"
		elif index < courante:
			statut = "fait"
		elif index == courante:
			statut = "en_cours"
		else:
			statut = "a_venir"
		etapes.append({"key": key, "label": label, "statut": statut, "quand": str(quand) if quand else None, "duree": duree or None})
	return etapes


def _mouvements(doc):
	found = []
	for field, role, label in (
		("stock_entry_preparation", "preparation", _("Préparation : matières vers l'atelier")),
		("stock_entry_production", "production", _("Production : matières → produit fini")),
		("stock_entry_rebuts", "rebuts", _("Rebuts : atelier → dépôt des rebuts")),
	):
		if doc.get(field):
			found.append({"name": doc.get(field), "role": role, "label": label})
	for row in doc.complements:
		if row.stock_entry:
			found.append(
				{
					"name": row.stock_entry,
					"role": "complement",
					"label": _("Complément : {0} {1}").format(_qty(row.qty), row.item_name or row.item_code),
				}
			)
	dates = {
		row.name: str(row.posting_date)
		for row in frappe.get_all("Stock Entry", filters={"name": ["in", [entry["name"] for entry in found] or [""]]}, fields=["name", "posting_date"])
	}
	for entry in found:
		entry["date"] = dates.get(entry["name"])
	return found


def _tracabilite(doc):
	"""Lots des matières qui ont servi, avec le lot fournisseur : ce qu'un rappel de lot doit retrouver."""
	lots = [row.batch_no for row in doc.matieres if row.batch_no]
	info = {
		row.name: row
		for row in frappe.get_all("Batch", filters={"name": ["in", lots or [""]]}, fields=["name", "custom_lot_fournisseur", "expiry_date"])
	}
	return [
		{
			"article": row.item_code,
			"designation": row.item_name or row.item_code,
			"lot": row.batch_no,
			"lot_fournisseur": info[row.batch_no].custom_lot_fournisseur if row.batch_no in info else None,
		}
		for row in doc.matieres
		if row.batch_no
	]


def _ordre_payload(doc):
	state = _state(doc)
	allowed = actions(doc)
	parametres = get_parametres()
	matieres = [_matiere(row, state, doc.warehouse_atelier) for row in doc.matieres]
	rendement_vise = (flt(frappe.db.get_value(RECETTE, doc.recette, "rendement_theorique")) if doc.recette else 0) or 100
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"creation": str(doc.creation),
		"tags": row_tags(doc.as_dict()),
		"state": state,
		"etape": ETAPES.get(state, state),
		"produit": doc.produit_fini,
		"designation": doc.nom_produit or doc.produit_fini,
		"produit_avec_lot": item_has_batch(doc.produit_fini) if doc.produit_fini else False,
		"recette": doc.recette,
		"modele_checklist": doc.modele_checklist,
		"date_prevue": _day(doc.date_prevue),
		"retard": _retard(state, doc.date_prevue),
		"qty_prevue": flt(doc.qty_prevue, 3),
		"qty_reelle": flt(doc.qty_reelle_pf, 3),
		"qty_rebut": flt(doc.qty_rebut, 3),
		"rendement": flt(doc.rendement_reel, 1),
		"rendement_vise": rendement_vise,
		"tolerance": flt(parametres.rendement_tolerance_pct) or 10,
		"unite": doc.uom,
		"lot_pf": doc.lot_pf or None,
		"depots": {
			"mp": doc.warehouse_mp,
			"conditionnement": doc.warehouse_conditionnement,
			"atelier": doc.warehouse_atelier,
			"pf": doc.warehouse_pf,
			"rebuts": doc.warehouse_rebuts,
		},
		"etapes": _etapes(doc),
		"duree_totale": cint(doc.duree_totale),
		"matieres": matieres,
		"checklist": [
			{
				"name": row.name,
				"controle": row.controle,
				"obligatoire": bool(cint(row.obligatoire)),
				"conforme": bool(cint(row.conforme)),
				"par": get_fullname(row.controle_par) if row.controle_par else None,
				"quand": str(row.date_heure) if row.date_heure else None,
				"observation": row.observation or None,
			}
			for row in doc.checklist
		],
		"rebuts": [
			{
				"name": row.name,
				"article": row.item_code,
				"designation": row.item_name or row.item_code,
				"lot": row.batch_no or None,
				"quantite": flt(row.qty, 3),
				"unite": row.uom,
			}
			for row in doc.rebuts
		],
		"complements": [
			{
				"name": row.name,
				"article": row.item_code,
				"designation": row.item_name or row.item_code,
				"lot": row.batch_no or None,
				"quantite": flt(row.qty, 3),
				"unite": row.uom,
				"depot": row.warehouse,
				"mouvement": row.stock_entry or None,
				"par": get_fullname(row.owner),
				"quand": str(row.creation),
			}
			for row in doc.complements
		],
		"mouvements": _mouvements(doc),
		"tracabilite": _tracabilite(doc) if state == STATUT_TERMINE else [],
		"manques": manques_preparation(doc, matieres) if state == STATUT_BROUILLON else [],
		"actions": allowed,
		"cree_par": get_fullname(doc.owner),
		"can_print": bool(doc.has_permission("print")),
		"comments": activity.comment_summary(ORDRE, doc.name),
	}


@frappe.whitelist()
def get_ordre(name):
	require_bureau()
	doc = frappe.get_doc(ORDRE, name)
	doc.check_permission("read")
	return _ordre_payload(doc)


def _load(name, modified):
	require_bureau()
	doc = frappe.get_doc(ORDRE, name)
	doc.check_permission("read")
	if modified and cstr(modified) != str(doc.modified):
		frappe.throw(
			_("Cet ordre vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."),
			frappe.TimestampMismatchError,
		)
	return doc


def _for_work(name, modified, action):
	doc = _load(name, modified)
	if action not in actions(doc):
		frappe.throw(_("Cette action n'est pas possible sur cet ordre à cette étape."), frappe.PermissionError)
	return doc


def _reload(doc):
	return _ordre_payload(frappe.get_doc(ORDRE, doc.name))


# Création et planification ----------------------------------------------------------------------------------------


def _check_recette(recette, produit=None):
	recette = cstr(recette).strip()
	row = frappe.db.get_value(RECETTE, recette, ["produit_fini", "actif"], as_dict=True) if recette else None
	if not row:
		frappe.throw(_("Choisissez une recette de la liste."))
	if not cint(row.actif):
		frappe.throw(_("La recette {0} n'est plus active.").format(recette))
	if produit and row.produit_fini != produit:
		frappe.throw(_("La recette {0} ne fabrique pas ce produit.").format(recette))
	return recette, row.produit_fini


def _propose_lots(doc):
	"""Lot proposé à une matière suivie par lots qui n'en a pas : le premier, par péremption, qui couvre la quantité."""
	for row in doc.matieres:
		if row.batch_no or not row.warehouse or not item_has_batch(row.item_code):
			continue
		for lot in lots_disponibles(row.item_code, row.warehouse).get(row.warehouse, []):
			if lot["qty"] + 0.0001 >= flt(row.qty_theorique):
				row.batch_no = lot["lot"]
				break


def _reset_matieres(doc):
	from unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement import charger_recette

	data = charger_recette(doc.recette, doc.qty_prevue)
	doc.set("matieres", [])
	for row in data["matieres"]:
		row.pop("stock_disponible", None)
		doc.append("matieres", row)
	_propose_lots(doc)


@frappe.whitelist(methods=["POST"])
def create_ordre(values=None):
	"""Nouvel ordre à planifier : produit (par sa recette), quantité, date et checklist. Les matières suivent la recette."""
	require_bureau()
	frappe.has_permission(ORDRE, "create", throw=True)
	values = _parse(values) or {}
	recette, produit = _check_recette(values.get("recette"), cstr(values.get("produit")).strip() or None)
	quantite = flt(values.get("quantite"))
	if quantite <= 0:
		frappe.throw(_("Indiquez la quantité à produire."))
	checklist = cstr(values.get("checklist")).strip() or (frappe.get_all(CHECKLIST, filters={"actif": 1}, order_by="name asc", pluck="name") or [None])[0]
	if not checklist or not frappe.db.get_value(CHECKLIST, checklist, "actif"):
		frappe.throw(_("Aucune checklist active : créez-en une dans les réglages de la production."))
	doc = frappe.new_doc(ORDRE)
	doc.update(
		{
			"produit_fini": produit,
			"recette": recette,
			"qty_prevue": quantite,
			"date_prevue": getdate(values.get("date_prevue") or today()),
			"modele_checklist": checklist,
		}
	)
	doc.set_defaults()
	_reset_matieres(doc)
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def update_ordre(name, modified, values=None):
	"""À planifier : recette, quantité, date, checklist et lignes de matières (lot, dépôt, quantité, ajout, retrait).

	Changer la recette ou la quantité recalcule toutes les matières d'après la recette.
	"""
	doc = _for_work(name, modified, "modifier")
	values = _parse(values) or {}
	recalcul = False
	if "recette" in values and cstr(values["recette"]) != cstr(doc.recette):
		doc.recette, doc.produit_fini = _check_recette(values["recette"])
		recalcul = True
	if "quantite" in values:
		quantite = flt(values["quantite"])
		if quantite <= 0:
			frappe.throw(_("Indiquez la quantité à produire."))
		recalcul = recalcul or quantite != flt(doc.qty_prevue)
		doc.qty_prevue = quantite
	if values.get("date_prevue"):
		doc.date_prevue = getdate(values["date_prevue"])
	if values.get("checklist") and values["checklist"] != doc.modele_checklist:
		if not frappe.db.get_value(CHECKLIST, values["checklist"], "actif"):
			frappe.throw(_("Choisissez une checklist active."))
		doc.modele_checklist = values["checklist"]
	if recalcul:
		_reset_matieres(doc)
	else:
		rows = {row.name: row for row in doc.matieres}
		for ligne in values.get("lignes") or []:
			row = rows.get(cstr(ligne.get("name")))
			if not row:
				frappe.throw(_("Cette ligne n'est plus dans l'ordre : rechargez-le."))
			if "quantite" in ligne:
				if flt(ligne["quantite"]) <= 0:
					frappe.throw(_("La quantité de {0} doit être supérieure à 0.").format(row.item_name or row.item_code))
				row.qty_theorique = row.qty_reelle = flt(ligne["quantite"])
			if "depot" in ligne:
				depot = cstr(ligne["depot"]).strip()
				if depot not in depots():
					frappe.throw(_("Dépôt inconnu ou désactivé : {0}.").format(depot))
				if depot != row.warehouse:
					row.warehouse = depot
					row.batch_no = None
			if "lot" in ligne:
				_set_lot(row, ligne["lot"])
		retirer = {cstr(item) for item in values.get("retirer") or []}
		if retirer:
			doc.set("matieres", [row for row in doc.matieres if row.name not in retirer])
		for ajout in values.get("ajouts") or []:
			_ajouter_matiere(doc, ajout)
	doc.save()
	return _reload(doc)


def _set_lot(row, lot):
	lot = cstr(lot).strip() or None
	if lot:
		if not item_has_batch(row.item_code):
			frappe.throw(_("{0} n'est pas suivi par lots.").format(row.item_name or row.item_code))
		if frappe.db.get_value("Batch", lot, "item") != row.item_code:
			frappe.throw(_("Le lot {0} n'est pas un lot de {1}.").format(lot, row.item_name or row.item_code))
	row.batch_no = lot


def _ajouter_matiere(doc, ajout):
	article = cstr((ajout or {}).get("article")).strip()
	item = frappe.db.get_value("Item", {"name": article, "disabled": 0, "is_stock_item": 1}, ["item_name", "stock_uom", "custom_type_conditionnement"], as_dict=True)
	if not item:
		frappe.throw(_("L'article {0} n'est pas un article stocké actif.").format(article))
	quantite = flt(ajout.get("quantite"))
	if quantite <= 0:
		frappe.throw(_("Indiquez la quantité de {0}.").format(item.item_name))
	type_ingredient = "Fût" if item.custom_type_conditionnement == "Fût" else "Conditionnement"
	depot = cstr(ajout.get("depot")).strip() or (doc.warehouse_mp if type_ingredient == "Fût" else doc.warehouse_conditionnement)
	row = doc.append(
		"matieres",
		{
			"item_code": article,
			"item_name": item.item_name,
			"type_ingredient": type_ingredient,
			"has_batch_no": 1 if item_has_batch(article) else 0,
			"qty_theorique": quantite,
			"qty_reelle": quantite,
			"uom": item.stock_uom,
			"warehouse": depot,
		},
	)
	if ajout.get("lot"):
		_set_lot(row, ajout["lot"])


@frappe.whitelist(methods=["POST"])
def set_controle(name, modified, ligne, conforme=None, observation=None):
	"""Coche (ou décoche) un contrôle de la checklist, avec qui et quand ; ou en note l'observation."""
	doc = _for_work(name, modified, "controler")
	row = next((row for row in doc.checklist if row.name == cstr(ligne)), None)
	if not row:
		frappe.throw(_("Ce contrôle n'est plus dans la checklist : rechargez l'ordre."))
	if conforme is not None:
		row.conforme = 1 if cint(conforme) else 0
		row.controle_par = frappe.session.user if row.conforme else None
		row.date_heure = now_datetime() if row.conforme else None
	if observation is not None:
		row.observation = cstr(observation).strip() or None
	doc.save()
	return _reload(doc)


@frappe.whitelist(methods=["POST"])
def generer_lot(name, modified):
	"""Crée le lot du produit fini (PF-<code>-AAAAMMJJ-###) et le rattache à l'ordre."""
	from unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement import generer_lot_pf

	doc = _for_work(name, modified, "generer_lot")
	doc.lot_pf = generer_lot_pf(doc.produit_fini, doc.name)
	doc.flags.ignore_stock_events = True
	doc.save()
	return _reload(doc)


# Étapes du workflow -----------------------------------------------------------------------------------------------


def _appliquer(doc, key):
	before = _state(doc)
	apply_workflow(doc, WORKFLOW_ACTIONS[key])
	doc = frappe.get_doc(ORDRE, doc.name)
	if _state(doc) == before:
		frappe.throw(_("L'étape n'a pas changé : rechargez l'ordre."))
	return doc


@frappe.whitelist(methods=["POST"])
def preparer(name, modified):
	"""Envoie les matières à l'atelier (transfert) : l'ordre devient « Prêt à démarrer »."""
	doc = _for_work(name, modified, "preparer")
	reasons = manques_preparation(doc)
	if reasons:
		frappe.throw(" ".join(reason["texte"] for reason in reasons))
	return _ordre_payload(_appliquer(doc, "preparer"))


@frappe.whitelist(methods=["POST"])
def demarrer(name, modified):
	doc = _for_work(name, modified, "demarrer")
	return _ordre_payload(_appliquer(doc, "demarrer"))


@frappe.whitelist(methods=["POST"])
def annuler(name, modified):
	"""Annule l'ordre : les mouvements de stock déjà faits sont annulés, les matières reviennent."""
	doc = _for_work(name, modified, "annuler")
	return _ordre_payload(_appliquer(doc, "annuler"))


def _set_utilise(doc, lignes):
	rows = {row.name: row for row in doc.matieres}
	for ligne in lignes or []:
		row = rows.get(cstr((ligne or {}).get("name")))
		if not row:
			frappe.throw(_("Cette ligne n'est plus dans l'ordre : rechargez-le."))
		utilise = flt(ligne.get("utilise"))
		if utilise < 0:
			frappe.throw(_("Une quantité utilisée ne peut pas être négative."))
		row.qty_reelle = utilise


@frappe.whitelist(methods=["POST"])
def saisir(name, modified, lignes=None):
	"""En production : quantités réellement utilisées."""
	doc = _for_work(name, modified, "saisir")
	_set_utilise(doc, _parse(lignes))
	doc.save()
	return _reload(doc)


@frappe.whitelist(methods=["POST"])
def add_rebut(name, modified, article, quantite, lot=None):
	"""En production : une matière abîmée, qui partira au dépôt des rebuts à la clôture."""
	doc = _for_work(name, modified, "saisir")
	matiere = next((row for row in doc.matieres if row.item_code == cstr(article)), None)
	if not matiere:
		frappe.throw(_("Un rebut doit être une des matières de l'ordre."))
	if flt(quantite) <= 0:
		frappe.throw(_("Indiquez la quantité de rebut."))
	avec_lot = item_has_batch(matiere.item_code)
	lot = cstr(lot).strip() or (matiere.batch_no if avec_lot else None)
	if avec_lot and not lot:
		frappe.throw(_("Indiquez le lot du rebut."))
	doc.append(
		"rebuts",
		{
			"item_code": matiere.item_code,
			"item_name": matiere.item_name,
			"has_batch_no": 1 if avec_lot else 0,
			"qty": flt(quantite),
			"uom": matiere.uom,
			"batch_no": lot if avec_lot else None,
		},
	)
	doc.save()
	return _reload(doc)


@frappe.whitelist(methods=["POST"])
def remove_rebut(name, modified, ligne):
	doc = _for_work(name, modified, "saisir")
	doc.set("rebuts", [row for row in doc.rebuts if row.name != cstr(ligne)])
	doc.save()
	return _reload(doc)


@frappe.whitelist(methods=["POST"])
def complement(name, modified, article, quantite, depot=None, lot=None):
	"""Envoie une quantité en plus à l'atelier (transfert immédiat) pour une matière de l'ordre."""
	doc = _for_work(name, modified, "complement")
	doc.add_complement(cstr(article), flt(quantite), warehouse=cstr(depot).strip() or None, batch_no=cstr(lot).strip() or None)
	return _reload(doc)


def _responsables():
	users = frappe.get_all("Has Role", filters={"role": RESPONSABLE, "parenttype": "User"}, pluck="parent")
	return frappe.get_all("User", filters={"name": ["in", users or [""]], "enabled": 1}, pluck="name")


def hors_tolerance(doc, qty_reelle_pf):
	parametres = get_parametres()
	tolerance = flt(parametres.rendement_tolerance_pct) or 10
	vise = flt(frappe.db.get_value(RECETTE, doc.recette, "rendement_theorique")) or 100
	rendement = flt(qty_reelle_pf) / flt(doc.qty_prevue) * 100 if flt(doc.qty_prevue) else 0
	return abs(rendement - vise) > tolerance, rendement, vise, tolerance


@frappe.whitelist(methods=["POST"])
def cloturer(name, modified, qty_reelle_pf, lignes=None, remarque=None):
	"""Clôture : quantité bonne produite et quantités utilisées, puis étape « Terminé ».

	Le doctype crée alors la pièce de production (matières → produit fini, avec son lot) et le transfert des rebuts.
	Hors tolérance de rendement, une remarque est exigée : elle va au fil de l'ordre et les responsables sont prévenus.
	"""
	doc = _for_work(name, modified, "cloturer")
	quantite = flt(qty_reelle_pf)
	if quantite <= 0:
		frappe.throw(_("Indiquez combien d'unités bonnes ont été produites."))
	ecart, rendement, vise, tolerance = hors_tolerance(doc, quantite)
	remarque = cstr(remarque).strip()
	if ecart and not remarque:
		frappe.throw(
			_("Rendement {0} % hors de la tolérance de ± {1} % (objectif {2} %) : expliquez l'écart en une phrase.").format(
				_qty(round(rendement, 1)), _qty(tolerance), _qty(vise)
			)
		)
	_set_utilise(doc, _parse(lignes))
	doc.qty_reelle_pf = quantite
	if doc.produit_fini and item_has_batch(doc.produit_fini) and not doc.lot_pf:
		from unicare.conditionnement.doctype.ordre_de_conditionnement.ordre_de_conditionnement import generer_lot_pf

		doc.lot_pf = generer_lot_pf(doc.produit_fini, doc.name)
	doc.flags.ignore_stock_events = True
	doc.save()
	doc.flags.ignore_stock_events = False
	doc = _appliquer(frappe.get_doc(ORDRE, doc.name), "cloturer")
	if ecart:
		texte = _("Clôture hors tolérance : rendement {0} % (objectif {1} %, ± {2} %). {3}").format(
			_qty(round(rendement, 1)), _qty(vise), _qty(tolerance), remarque
		)
		doc.add_comment("Comment", texte)
		for user in _responsables():
			if user == frappe.session.user:
				continue
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"for_user": user,
					"type": "Alert",
					"document_type": ORDRE,
					"document_name": doc.name,
					"subject": _("{0} : rendement {1} % hors tolérance").format(doc.name, _qty(round(rendement, 1))),
					"email_content": texte,
				}
			).insert(ignore_permissions=True)
	return _ordre_payload(doc)


# Suppression, duplication, actions groupées -----------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def delete_ordre(name, modified):
	doc = _for_work(name, modified, "supprimer")
	frappe.delete_doc(ORDRE, doc.name)
	return {"deleted": doc.name}


@frappe.whitelist(methods=["POST"])
def dupliquer(name, modified=None):
	"""« Refaire cet ordre » : un nouvel ordre à planifier, même produit, recette, quantité et checklist, pour aujourd'hui."""
	doc = _for_work(name, None, "dupliquer")
	recette = doc.recette if doc.recette and frappe.db.get_value(RECETTE, doc.recette, "actif") else None
	if not recette:
		active = _recettes(doc.produit_fini)
		if not active:
			frappe.throw(_("Ce produit n'a plus de recette active."))
		recette = active[0].name
	return create_ordre(
		{
			"produit": doc.produit_fini,
			"recette": recette,
			"quantite": doc.qty_prevue,
			"date_prevue": today(),
			"checklist": doc.modele_checklist if frappe.db.get_value(CHECKLIST, doc.modele_checklist, "actif") else None,
		}
	)


def ordre_for_bulk(name, modified):
	return _load(name, modified)


def bulk_guard(doc, operation):
	"""Un ordre se mène sur sa fiche ; en groupe, seulement la suppression des ordres à planifier."""
	if operation != "delete":
		return _("Un ordre se modifie sur sa fiche.")
	if _state(doc) != STATUT_BROUILLON:
		return _("Seul un ordre à planifier se supprime ; les autres s'annulent sur leur fiche.")
	return None


# Fil d'activité ---------------------------------------------------------------------------------------------------


def _check_activity(name):
	require_bureau()
	frappe.get_doc(ORDRE, name).check_permission("read")


@frappe.whitelist()
def get_ordre_activity(name):
	require_bureau()
	return activity.get_feed(ORDRE, name)


@frappe.whitelist(methods=["POST"])
def add_ordre_comment(name, text, mentions=None):
	_check_activity(name)
	return activity.add_comment(ORDRE, name, text, mentions)


@frappe.whitelist(methods=["POST"])
def update_ordre_comment(name, comment, text, mentions=None):
	_check_activity(name)
	return activity.update_comment(ORDRE, name, comment, text, mentions)


@frappe.whitelist(methods=["POST"])
def delete_ordre_comment(name, comment):
	_check_activity(name)
	return activity.delete_comment(ORDRE, name, comment)


def stats_production(debut, fin):
	"""Ordres terminés entre deux dates (date de clôture) : pour le tableau de bord."""
	return frappe.get_list(
		ORDRE,
		filters=[["workflow_state", "=", STATUT_TERMINE], ["date_heure_cloture", "between", [debut, add_days(fin, 1)]]],
		fields=["name", "produit_fini", "nom_produit", "qty_prevue", "qty_reelle_pf", "rendement_reel", "recette", "date_heure_cloture"],
		limit_page_length=0,
	)
