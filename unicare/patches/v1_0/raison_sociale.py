# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""La raison sociale imprimée sur les pièces : « Unicare Pharma » (la société s'appelle « Unicare » dans l'ERP)."""

import frappe


def execute():
	# les champs personnalisés de unicare/unicare/custom sont synchronisés après les patchs : on le fait d'abord
	from frappe.modules.utils import sync_customizations

	sync_customizations("unicare")
	for societe in frappe.get_all("Company", fields=["name", "unicare_raison_sociale"]):
		if not (societe.unicare_raison_sociale or "").strip():
			frappe.db.set_value(
				"Company", societe.name, "unicare_raison_sociale", "Unicare Pharma", update_modified=False
			)
