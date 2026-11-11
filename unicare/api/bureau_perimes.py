# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Lots périmés encore en stock : un transfert vers le dépôt des rebuts, préparé d'office et laissé en brouillon.

Chaque jour (hooks.py, `scheduler_events`), et à la demande depuis la fiche d'un lot, on cherche les lots dont la
péremption est passée et qui ont encore du stock ailleurs que dans le dépôt des rebuts (réglages de la production).
Pour chaque dépôt concerné, un mouvement « Transfert » vers ce dépôt est créé en brouillon, avec tous ses lots
périmés : quelqu'un le vérifie puis le valide ; rien ne bouge seul. Un lot déjà dans un brouillon n'est pas repris.
"""

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, today

from unicare.api.bureau_postes import require_bureau
from unicare.api.bureau_stock import company, depots, stock_par_lot

MOUVEMENT = "Stock Entry"
MARQUE = "Mise au rebut des lots périmés"
NOTIFIES = ("Magasinier Conditionnement", "Responsable Conditionnement", "Stock Manager")


def depot_rebuts():
	from unicare.conditionnement.stock import get_parametres

	depot = get_parametres().warehouse_rebuts
	return depot if depot and depot in depots(include_disabled=True) else None


def lots_perimes(lot=None):
	"""[(lot, article, dépôt, quantité)] des lots périmés en stock, hors du dépôt des rebuts et de l'atelier.

	L'atelier est laissé de côté : ce qui s'y trouve appartient à un ordre de production, qui le consomme ou le rend.
	"""
	from unicare.conditionnement.stock import get_parametres

	rebuts = depot_rebuts()
	atelier = get_parametres().warehouse_atelier
	# « is set » d'abord : sans lui, Frappe compare une péremption vide comme une date très ancienne.
	filters = [["expiry_date", "is", "set"], ["expiry_date", "<", today()], ["disabled", "=", 0]]
	if lot:
		filters.append(["name", "=", lot])
	batches = {row.name: row.item for row in frappe.get_all("Batch", filters=filters, fields=["name", "item"])}
	if not batches:
		return []
	connus = set(depots())
	found = []
	for name, par_depot in stock_par_lot(list(batches)).items():
		for depot, qty in par_depot.items():
			if depot not in (rebuts, atelier) and depot in connus and flt(qty) > 0:
				found.append((name, batches[name], depot, flt(qty, 3)))
	return sorted(found, key=lambda row: (row[2], row[0]))


def brouillons(lot=None):
	"""{(lot, dépôt de départ): mouvement} des lignes déjà prévues dans un mouvement en brouillon."""
	filters = [[MOUVEMENT, "docstatus", "=", 0], [MOUVEMENT, "company", "=", company()], ["Stock Entry Detail", "batch_no", "is", "set"]]
	if lot:
		filters.append(["Stock Entry Detail", "batch_no", "=", lot])
	rows = frappe.get_all(
		MOUVEMENT,
		filters=filters,
		fields=["name", "`tabStock Entry Detail`.batch_no as lot", "`tabStock Entry Detail`.s_warehouse as depot"],
	)
	return {(row.lot, row.depot): row.name for row in rows if row.depot}


def preparer(lot=None):
	"""Crée les brouillons manquants (un par dépôt de départ) ; renvoie les noms créés."""
	rebuts = depot_rebuts()
	if not rebuts:
		return []
	deja = brouillons(lot)
	par_depot = {}
	for name, article, depot, qty in lots_perimes(lot):
		if (name, depot) not in deja:
			par_depot.setdefault(depot, []).append((name, article, qty))
	created = []
	for depot, lignes in par_depot.items():
		doc = frappe.new_doc(MOUVEMENT)
		doc.update(
			{
				"company": company(),
				"posting_date": today(),
				"purpose": "Material Transfer",
				"stock_entry_type": "Material Transfer",
				"from_warehouse": depot,
				"to_warehouse": rebuts,
				"remarks": _("{0} : {1}. À vérifier puis valider.").format(MARQUE, ", ".join(sorted({row[0] for row in lignes}))),
			}
		)
		for name, article, qty in lignes:
			doc.append(
				"items",
				{"item_code": article, "qty": qty, "s_warehouse": depot, "t_warehouse": rebuts, "batch_no": name, "use_serial_batch_fields": 1},
			)
		doc.flags.ignore_permissions = True
		doc.insert()
		created.append(doc.name)
	return created


def _notifier(noms):
	if not noms:
		return
	users = frappe.get_all("Has Role", filters={"role": ["in", list(NOTIFIES)], "parenttype": "User"}, pluck="parent")
	for user in frappe.get_all("User", filters={"name": ["in", users or [""]], "enabled": 1}, pluck="name"):
		if user in ("Administrator", "Guest"):
			continue
		for name in noms:
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"for_user": user,
					"type": "Alert",
					"document_type": MOUVEMENT,
					"document_name": name,
					"subject": _("Lots périmés : transfert vers le rebut {0} à vérifier").format(name),
				}
			).insert(ignore_permissions=True)


def preparer_tous():
	"""Tâche quotidienne : prépare les mises au rebut et prévient le magasin."""
	try:
		_notifier(preparer())
	except Exception:
		frappe.log_error(title=MARQUE)


def etat_lot(lot):
	"""Pour la fiche d'un lot : le brouillon qui le met au rebut, ou s'il est à préparer."""
	if not lot or not getdate(frappe.db.get_value("Batch", lot, "expiry_date") or "2999-12-31") < getdate(today()):
		return {"mise_au_rebut": None, "a_mettre_au_rebut": False, "depot_rebuts": None}
	deja = brouillons(lot)
	restants = [row for row in lots_perimes(lot) if (row[0], row[2]) not in deja]
	return {
		"mise_au_rebut": next(iter(deja.values()), None),
		"a_mettre_au_rebut": bool(restants) and bool(depot_rebuts()),
		"depot_rebuts": depot_rebuts(),
	}


@frappe.whitelist(methods=["POST"])
def preparer_mise_au_rebut(lot):
	"""Depuis la fiche d'un lot périmé : prépare (en brouillon) son transfert vers le dépôt des rebuts."""
	require_bureau()
	frappe.has_permission(MOUVEMENT, "create", throw=True)
	frappe.get_doc("Batch", lot).check_permission("read")
	if not depot_rebuts():
		frappe.throw(_("Aucun dépôt des rebuts n'est réglé : choisissez-le dans les réglages de la production."))
	created = preparer(cstr(lot))
	existing = brouillons(cstr(lot))
	name = created[0] if created else next(iter(existing.values()), None)
	if not name:
		frappe.throw(_("Ce lot n'a plus de stock à mettre au rebut."))
	return {"name": name}
