# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.naming import make_autoname

from erpnext.stock.doctype.item.item import Item

from unicare.conditionnement.constants import TYPES_AVEC_LOT

ITEM_NAMING_BY_TYPE = {
	"Fût": "FU-.######",
	"Conditionnement": "CO-.######",
	"Produit fini": "PF-.######",
	"Autre": "AU-.######",
}


class CustomItem(Item):
	def autoname(self):
		if self.variant_of:
			super().autoname()
			return

		item_type = self.get("custom_type_conditionnement")
		if not item_type:
			frappe.throw(_("Le Type conditionnement est obligatoire pour générer le code article."))

		series = ITEM_NAMING_BY_TYPE.get(item_type)
		if not series:
			frappe.throw(_("Type conditionnement invalide : {0}").format(item_type))

		self.name = make_autoname(series)
		self.item_code = self.name

	def validate(self):
		if not self.get("custom_type_conditionnement") and not self.variant_of:
			frappe.throw(_("Le Type conditionnement est obligatoire."))

		super().validate()


def validate_item(doc, method=None):
	if doc.get("custom_type_conditionnement") in TYPES_AVEC_LOT:
		doc.has_batch_no = 1
		if not doc.is_stock_item:
			frappe.throw(
				_("Les articles de type {0} doivent être des articles de stock.").format(
					doc.custom_type_conditionnement
				)
			)
