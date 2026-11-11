# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Socle stock du poste de bureau : dépôts, stock par dépôt, lots disponibles et grand livre de stock.

Les écrans Stock (dépôts, état du stock, lots, mouvements, inventaires) lisent tous ces mêmes données. Rien ici n'écrit :
les écritures passent par les pièces d'ERPNext (Stock Entry, Stock Reconciliation…) et leurs règles.
"""

import frappe
from frappe.utils import cint, cstr, flt

from unicare.api.bureau_devis import _company, _day

WAREHOUSE = "Warehouse"
BIN = "Bin"
SLE = "Stock Ledger Entry"
BATCH = "Batch"
LEDGER_LIMIT = 200

# Pièce du grand livre → fiche du bureau qui l'ouvre (route de l'interface).
FICHES = {
	"Purchase Receipt": "ReceptionFiche",
	"Delivery Note": "LivraisonFiche",
	"Stock Entry": "MouvementFiche",
	"Stock Reconciliation": "InventaireFiche",
	"Sales Invoice": "FactureFiche",
	"Purchase Invoice": "FactureAchatFiche",
}


def readable(doctype):
	return bool(frappe.has_permission(doctype, "read"))


def company():
	return _company()


def depots(company_name=None, include_disabled=False):
	"""Dépôts de la société qui reçoivent du stock (pas les groupes), par ordre alphabétique."""
	filters = {"company": company_name or company(), "is_group": 0}
	if not include_disabled:
		filters["disabled"] = 0
	return frappe.get_all(WAREHOUSE, filters=filters, order_by="name asc", pluck="name")


def check_depot(depot, company_name=None, label=None):
	"""Un dépôt de la liste : de la société, actif, pas un groupe."""
	depot = cstr(depot).strip()
	if not depot:
		frappe.throw(frappe._("Choisissez le {0}.").format(label or frappe._("dépôt")))
	if depot not in depots(company_name):
		frappe.throw(frappe._("Dépôt inconnu ou désactivé : {0}.").format(depot))
	return depot


def bins(item_code=None, warehouse=None):
	"""Lignes de stock (Bin) d'un article, d'un dépôt, ou des deux, la plus fournie d'abord."""
	filters = {}
	if item_code:
		filters["item_code"] = item_code
	if warehouse:
		filters["warehouse"] = warehouse
	rows = frappe.get_all(
		BIN,
		filters=filters,
		fields=[
			"item_code",
			"warehouse",
			"actual_qty",
			"reserved_qty",
			"ordered_qty",
			"projected_qty",
			"valuation_rate",
			"stock_value",
			"stock_uom",
		],
		order_by="actual_qty desc",
	)
	for row in rows:
		for key in ("actual_qty", "reserved_qty", "ordered_qty", "projected_qty"):
			row[key] = flt(row[key], 3)
		row.valuation_rate = flt(row.valuation_rate, 2)
		row.stock_value = flt(row.stock_value, 2)
	return rows


def lots_disponibles(item_code, warehouse=None):
	"""Lots en stock d'un article, par dépôt, hors lots désactivés : la péremption la plus proche d'abord (FEFO)."""
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	lots = {}
	for row in get_batch_qty(item_code=item_code, warehouse=warehouse) or []:
		if flt(row.get("qty")) <= 0:
			continue
		lots.setdefault(row.get("warehouse"), []).append(
			{"lot": row.get("batch_no"), "qty": flt(row.get("qty"), 3), "peremption": _day(row.get("expiry_date"))}
		)
	disabled = set(
		frappe.get_all(
			BATCH,
			filters={"name": ["in", [entry["lot"] for entries in lots.values() for entry in entries] or [""]], "disabled": 1},
			pluck="name",
		)
	)
	for depot, entries in lots.items():
		entries[:] = [entry for entry in entries if entry["lot"] not in disabled]
		entries.sort(key=lambda entry: (entry["peremption"] is None, cstr(entry["peremption"]), entry["lot"]))
	return lots


def lot_disponible(item_code, warehouse, lot):
	from unicare.conditionnement.stock import get_batch_available_qty

	return get_batch_available_qty(item_code, warehouse, lot)


def ledger(item_code=None, warehouse=None, lot=None, limit=LEDGER_LIMIT):
	"""Dernières lignes du grand livre de stock, la plus récente d'abord, avec le lot de chaque ligne.

	En v15, le lot d'une ligne est dans son Serial and Batch Bundle ; une ligne sur plusieurs lots en donne la liste.
	Avec `lot`, seules les lignes de ce lot, avec la quantité de ce lot.
	"""
	conditions = ["sle.is_cancelled = 0"]
	values = {"limit": cint(limit) or LEDGER_LIMIT}
	if item_code:
		conditions.append("sle.item_code = %(item_code)s")
		values["item_code"] = item_code
	if warehouse:
		conditions.append("sle.warehouse = %(warehouse)s")
		values["warehouse"] = warehouse
	lot_join = ""
	lot_qty = "sle.actual_qty"
	if lot:
		lot_join = (
			"left join `tabSerial and Batch Entry` sbe"
			" on sbe.parent = sle.serial_and_batch_bundle and sbe.batch_no = %(lot)s"
		)
		conditions.append("(sle.batch_no = %(lot)s or sbe.name is not null)")
		lot_qty = "coalesce(sbe.qty, sle.actual_qty)"
		values["lot"] = lot
	rows = frappe.db.sql(
		f"""
		select sle.name, sle.posting_date as date, sle.posting_time as heure, sle.voucher_type, sle.voucher_no,
			sle.item_code as article, item.item_name as designation, sle.warehouse as depot,
			{lot_qty} as quantite, sle.qty_after_transaction as solde, sle.stock_value_difference as valeur,
			sle.valuation_rate as taux, sle.stock_uom as unite, sle.batch_no, sle.serial_and_batch_bundle
		from `tabStock Ledger Entry` sle
		left join `tabItem` item on item.name = sle.item_code
		{lot_join}
		where {" and ".join(conditions)}
		order by sle.posting_datetime desc, sle.creation desc
		limit %(limit)s
		""",
		values,
		as_dict=True,
	)
	bundles = [row.serial_and_batch_bundle for row in rows if row.serial_and_batch_bundle]
	bundle_lots = {}
	if bundles:
		for entry in frappe.get_all(
			"Serial and Batch Entry",
			filters={"parent": ["in", bundles], "batch_no": ["is", "set"]},
			fields=["parent", "batch_no"],
			order_by="idx asc",
		):
			bundle_lots.setdefault(entry.parent, []).append(entry.batch_no)
	return [
		{
			"date": _day(row.date),
			"heure": cstr(row.heure)[:5] if row.heure else None,
			"piece_type": row.voucher_type,
			"piece": row.voucher_no,
			"fiche": FICHES.get(row.voucher_type),
			"article": row.article,
			"designation": row.designation or row.article,
			"depot": row.depot,
			"quantite": flt(row.quantite, 3),
			"solde": flt(row.solde, 3),
			"valeur": flt(row.valeur, 2),
			"unite": row.unite,
			"lots": [row.batch_no] if row.batch_no else bundle_lots.get(row.serial_and_batch_bundle, []),
		}
		for row in rows
	]


def stock_par_lot(lots=None):
	"""Stock réel de chaque lot par dépôt, lots périmés compris : {lot: {dépôt: quantité}}.

	`get_batch_qty` d'ERPNext ignore les lots périmés (il sert au choix d'un lot à sortir) ; ici on veut tout ce qui est
	physiquement en stock. On lit les Serial and Batch Bundle validés, plus les anciennes lignes sans bundle.
	"""
	lot_filter = "and sbe.batch_no in %(lots)s" if lots is not None else ""
	legacy_filter = "and batch_no in %(lots)s" if lots is not None else ""
	if lots is not None and not lots:
		return {}
	values = {"lots": tuple(lots or ())}
	rows = frappe.db.sql(
		f"""
		select sbe.batch_no as lot, sbe.warehouse as depot, sum(sbe.qty) as qty
		from `tabSerial and Batch Entry` sbe
		join `tabSerial and Batch Bundle` sbb on sbb.name = sbe.parent
		where sbb.is_cancelled = 0 and sbb.docstatus = 1 and ifnull(sbe.batch_no, '') != '' {lot_filter}
		group by sbe.batch_no, sbe.warehouse
		""",
		values,
		as_dict=True,
	) + frappe.db.sql(
		f"""
		select batch_no as lot, warehouse as depot, sum(actual_qty) as qty
		from `tabStock Ledger Entry`
		where is_cancelled = 0 and ifnull(batch_no, '') != '' and ifnull(serial_and_batch_bundle, '') = '' {legacy_filter}
		group by batch_no, warehouse
		""",
		values,
		as_dict=True,
	)
	result = {}
	for row in rows:
		depots_lot = result.setdefault(row.lot, {})
		depots_lot[row.depot] = flt(depots_lot.get(row.depot, 0) + flt(row.qty), 3)
	return {lot: {depot: qty for depot, qty in entries.items() if qty} for lot, entries in result.items()}
