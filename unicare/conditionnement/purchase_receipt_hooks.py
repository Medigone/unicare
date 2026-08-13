# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from unicare.conditionnement.stock import ensure_batch, get_parametres, item_has_batch

CONDITIONNEMENT_RECEIPT_TYPES = ("Fût", "Conditionnement")


def before_submit(doc, method=None):
	if getattr(doc, "is_return", 0):
		return

	parametres = get_parametres()
	for row in doc.items:
		_prepare_receipt_item(row, doc.supplier, parametres)


def _prepare_receipt_item(row, supplier, parametres):
	if not row.item_code:
		return

	item_type = frappe.db.get_value("Item", row.item_code, "custom_type_conditionnement")
	if item_type in CONDITIONNEMENT_RECEIPT_TYPES and not row.warehouse:
		row.warehouse = _default_warehouse(item_type, parametres)

	if not item_has_batch(row.item_code):
		return

	row.use_serial_batch_fields = 1
	if item_type not in CONDITIONNEMENT_RECEIPT_TYPES:
		return

	if not row.batch_no:
		frappe.throw(_("Indiquez le n° de lot fournisseur pour {0}.").format(row.item_code))

	_ensure_native_batch(row, supplier)


def _default_warehouse(item_type, parametres):
	if item_type == "Conditionnement":
		return parametres.warehouse_conditionnement
	return parametres.warehouse_mp


def _ensure_native_batch(row, supplier):
	existing_item = frappe.db.get_value("Batch", row.batch_no, "item")
	if existing_item:
		if existing_item != row.item_code:
			frappe.throw(
				_("Le lot {0} appartient à l'article {1}, pas à {2}.").format(
					row.batch_no, existing_item, row.item_code
				)
			)
		return

	ensure_batch(
		item_code=row.item_code,
		batch_no=row.batch_no,
		supplier=supplier,
		lot_fournisseur=row.batch_no,
		origine="Réception",
	)
