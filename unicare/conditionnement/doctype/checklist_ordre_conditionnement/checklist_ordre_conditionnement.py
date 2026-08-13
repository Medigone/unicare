# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ChecklistOrdreConditionnement(Document):
	def validate(self):
		if not self.lignes:
			frappe.throw(_("Ajoutez au moins un contrôle à la checklist."))
		for row in self.lignes:
			if not (row.controle or "").strip():
				frappe.throw(_("Le libellé du contrôle est obligatoire."))
