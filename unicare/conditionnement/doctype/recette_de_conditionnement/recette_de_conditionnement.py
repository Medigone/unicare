# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class RecettedeConditionnement(Document):
	def validate(self):
		if flt(self.quantite_base) <= 0:
			frappe.throw(_("La quantité de base doit être supérieure à 0."))

		if not self.ingredients:
			frappe.throw(_("Ajoutez au moins un ingrédient à la recette."))

		has_fut = False
		for row in self.ingredients:
			if flt(row.qty) <= 0:
				frappe.throw(_("La quantité de l'ingrédient {0} doit être supérieure à 0.").format(row.item_code))
			if row.type_ingredient == "Fût":
				has_fut = True

		if not has_fut:
			frappe.throw(_("La recette doit contenir au moins une matière Fût."))
