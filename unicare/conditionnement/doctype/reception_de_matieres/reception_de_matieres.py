# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from unicare.conditionnement.stock import (
	cancel_stock_entry,
	create_stock_entry,
	ensure_batch,
	get_company,
	get_parametres,
	item_has_batch,
)


class ReceptiondeMatieres(Document):
	def before_insert(self):
		self.set_defaults()

	def validate(self):
		self.set_defaults()
		if not self.items:
			frappe.throw(_("Ajoutez au moins un article à réceptionner."))

		for row in self.items:
			if flt(row.qty) <= 0:
				frappe.throw(_("La quantité de {0} doit être supérieure à 0.").format(row.item_code))
			if not row.warehouse:
				row.warehouse = self.warehouse
			if not row.warehouse:
				frappe.throw(_("Indiquez un entrepôt pour {0}.").format(row.item_code))
			if item_has_batch(row.item_code):
				row.has_batch_no = 1

	def on_submit(self):
		self.create_receipt_stock_entry()

	def on_cancel(self):
		if self.stock_entry:
			cancel_stock_entry(self.stock_entry)
			self.db_set("stock_entry", None)

	def set_defaults(self):
		parametres = get_parametres()
		if not self.warehouse:
			self.warehouse = parametres.warehouse_mp

	def create_receipt_stock_entry(self):
		items = []
		for row in self.items:
			batch_no = None
			if item_has_batch(row.item_code):
				batch_no = ensure_batch(
					item_code=row.item_code,
					batch_no=row.batch_no,
					expiry_date=row.expiry_date,
					manufacturing_date=row.manufacturing_date,
					supplier=self.supplier,
					lot_fournisseur=row.lot_fournisseur,
					origine="Réception",
				)
				if row.batch_no != batch_no:
					row.db_set("batch_no", batch_no)

			items.append(
				{
					"item_code": row.item_code,
					"qty": row.qty,
					"uom": row.uom,
					"t_warehouse": row.warehouse,
					"batch_no": batch_no,
				}
			)

		se = create_stock_entry(
			purpose="Material Receipt",
			items=items,
			company=get_company(),
			remarks=_("Réception de matières {0}").format(self.name),
			reception=self.name,
		)
		self.db_set("stock_entry", se.name)


ALLOWED_RECEPTION_TYPES = ("Fût", "Conditionnement")


@frappe.whitelist()
def get_items_from_purchase_order(purchase_order, warehouse=None):
	if not purchase_order:
		frappe.throw(_("Sélectionnez une commande d'achat."))

	po = frappe.get_doc("Purchase Order", purchase_order)
	if po.docstatus != 1:
		frappe.throw(_("La commande d'achat {0} n'est pas validée.").format(purchase_order))

	parametres = get_parametres()
	item_codes = list({row.item_code for row in po.items if row.item_code})
	item_meta = {}
	if item_codes:
		item_meta = {
			d.name: d
			for d in frappe.get_all(
				"Item",
				filters={"name": ["in", item_codes]},
				fields=["name", "item_name", "stock_uom", "has_batch_no", "custom_type_conditionnement"],
			)
		}

	rows = []
	for item in po.items:
		meta = item_meta.get(item.item_code) or {}
		item_type = meta.get("custom_type_conditionnement")
		if item_type not in ALLOWED_RECEPTION_TYPES:
			continue

		remaining = flt(item.qty) - flt(item.received_qty)
		if remaining <= 0:
			continue

		row_warehouse = warehouse
		if not row_warehouse:
			if item_type == "Conditionnement":
				row_warehouse = parametres.warehouse_conditionnement
			else:
				row_warehouse = parametres.warehouse_mp
		if not row_warehouse:
			row_warehouse = item.warehouse

		rows.append(
			{
				"item_code": item.item_code,
				"item_name": meta.get("item_name") or item.item_name,
				"qty": remaining,
				"uom": item.uom or meta.get("stock_uom"),
				"has_batch_no": 1 if item_has_batch(item.item_code) else 0,
				"warehouse": row_warehouse,
			}
		)

	if not rows:
		frappe.throw(
			_("Aucun article Fût ou Conditionnement à réceptionner sur {0}.").format(purchase_order)
		)

	return {"supplier": po.supplier, "items": rows}
