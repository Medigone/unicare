# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import flt, nowdate

from unicare.conditionnement.constants import TYPES_AVEC_LOT


def get_parametres():
	return frappe.get_single("Parametres Conditionnement")


def get_company():
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)


def item_has_batch(item_code):
	return cint_bool(frappe.db.get_value("Item", item_code, "has_batch_no"))


def cint_bool(value):
	return int(value or 0) == 1


def get_item_uom(item_code):
	return frappe.db.get_value("Item", item_code, "stock_uom")


def ensure_batch(
	item_code,
	batch_no=None,
	expiry_date=None,
	manufacturing_date=None,
	supplier=None,
	lot_fournisseur=None,
	origine=None,
	ordre=None,
	qty_produite=None,
):
	if not batch_no:
		batch_no = make_autoname("LOT-.YYYY.-.#####")

	values = {
		"expiry_date": expiry_date,
		"manufacturing_date": manufacturing_date or nowdate(),
		"supplier": supplier,
		"lot_fournisseur": lot_fournisseur,
		"origine": origine,
		"ordre": ordre,
		"qty_produite": qty_produite,
	}

	if frappe.db.exists("Batch", batch_no):
		if not manufacturing_date:
			values["manufacturing_date"] = None
		_fill_batch_metadata(batch_no, **values)
		return batch_no

	doc = frappe.get_doc(
		{
			"doctype": "Batch",
			"batch_id": batch_no,
			"item": item_code,
			"expiry_date": expiry_date,
			"manufacturing_date": values["manufacturing_date"],
			"supplier": supplier,
		}
	)
	_set_batch_metadata(doc, **values)
	doc.insert(ignore_permissions=True)
	return doc.name


def _fill_batch_metadata(batch_no, **values):
	doc = frappe.get_doc("Batch", batch_no)
	if _set_batch_metadata(doc, **values):
		doc.db_update()


def _set_batch_metadata(
	doc,
	expiry_date=None,
	manufacturing_date=None,
	supplier=None,
	lot_fournisseur=None,
	origine=None,
	ordre=None,
	qty_produite=None,
):
	changed = False

	def set_if_empty(fieldname, value, custom=False):
		nonlocal changed
		if not value:
			return
		if custom and not doc.meta.has_field(fieldname):
			return
		if doc.get(fieldname):
			return
		doc.set(fieldname, value)
		changed = True

	set_if_empty("expiry_date", expiry_date)
	set_if_empty("manufacturing_date", manufacturing_date)
	set_if_empty("supplier", supplier)
	set_if_empty("custom_date_fabrication", manufacturing_date, custom=True)
	set_if_empty("custom_lot_fournisseur", lot_fournisseur, custom=True)
	set_if_empty("custom_origine", origine, custom=True)
	set_if_empty("custom_ordre_conditionnement", ordre, custom=True)
	set_if_empty("custom_qty_produite", qty_produite, custom=True)
	return changed


def get_lots_fournisseur_from_matieres(matieres):
	lots = []
	seen = set()
	for row in matieres or []:
		if getattr(row, "type_ingredient", None) != "Fût":
			continue
		batch_no = getattr(row, "batch_no", None)
		if not batch_no:
			continue
		lot = frappe.db.get_value("Batch", batch_no, "custom_lot_fournisseur") or batch_no
		if lot not in seen:
			seen.add(lot)
			lots.append(lot)
	return ", ".join(lots) or None


def make_fg_batch_name(item_code):
	code = item_code or ""
	if not code.upper().startswith("PF-"):
		code = f"PF-{code}"
	prefix = f"{code}-{nowdate().replace('-', '')}-"
	return make_autoname(prefix + ".###")


def get_batch_available_qty(item_code, warehouse, batch_no):
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	if not (item_code and warehouse and batch_no):
		return 0

	qty = get_batch_qty(batch_no=batch_no, warehouse=warehouse, item_code=item_code) or 0
	return flt(qty)


def create_stock_entry(purpose, items, company, remarks=None, ordre=None):
	if not items:
		frappe.throw(_("Aucun article à mouvementer en stock."))

	se = frappe.new_doc("Stock Entry")
	se.purpose = purpose
	se.company = company
	se.remarks = remarks or ""
	se.set_stock_entry_type()
	if ordre and se.meta.has_field("custom_ordre_conditionnement"):
		se.custom_ordre_conditionnement = ordre

	for item in items:
		qty = flt(item.get("qty"))
		if qty <= 0:
			continue

		row = se.append("items", {})
		row.item_code = item["item_code"]
		row.qty = qty
		row.uom = item.get("uom") or get_item_uom(item["item_code"])
		row.stock_uom = get_item_uom(item["item_code"])
		row.conversion_factor = item.get("conversion_factor") or 1
		row.transfer_qty = qty * flt(row.conversion_factor)
		row.s_warehouse = item.get("s_warehouse")
		row.t_warehouse = item.get("t_warehouse")
		row.is_finished_item = cint_bool(item.get("is_finished_item"))
		row.allow_zero_valuation_rate = 0 if row.is_finished_item else 1
		row.use_serial_batch_fields = 1
		if item.get("batch_no"):
			row.batch_no = item["batch_no"]

	if not se.items:
		frappe.throw(_("Aucun article avec une quantité positive à mouvementer."))

	se.insert(ignore_permissions=True)
	se.submit()
	return se


def cancel_stock_entry(stock_entry):
	if not stock_entry or not frappe.db.exists("Stock Entry", stock_entry):
		return

	doc = frappe.get_doc("Stock Entry", stock_entry)
	if doc.docstatus == 1:
		doc.cancel()
	elif doc.docstatus == 0:
		doc.delete()


def validate_item_type(item_code, allowed_types=None):
	item_type = frappe.db.get_value("Item", item_code, "custom_type_conditionnement")
	if allowed_types and item_type not in allowed_types:
		frappe.throw(
			_("L'article {0} n'est pas du type attendu ({1}).").format(
				item_code, ", ".join(allowed_types)
			)
		)
	if item_type in TYPES_AVEC_LOT and not item_has_batch(item_code):
		frappe.throw(_("L'article {0} doit être suivi par lot.").format(item_code))
