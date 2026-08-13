# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe

CHECKLIST_STANDARD = "Checklist standard"

LIGNES_STANDARD = [
	{"controle": "Ligne dégagée", "obligatoire": 1},
	{"controle": "Lots vérifiés", "obligatoire": 1},
	{"controle": "Quantités conformes", "obligatoire": 1},
	{"controle": "Matériel OK", "obligatoire": 1},
]


def execute():
	if not frappe.db.exists("DocType", "Checklist Ordre Conditionnement"):
		return

	if not frappe.db.exists("Checklist Ordre Conditionnement", CHECKLIST_STANDARD):
		frappe.get_doc(
			{
				"doctype": "Checklist Ordre Conditionnement",
				"titre": CHECKLIST_STANDARD,
				"actif": 1,
				"lignes": LIGNES_STANDARD,
			}
		).insert(ignore_permissions=True)

	if frappe.db.has_column("Ordre de Conditionnement", "modele_checklist"):
		frappe.db.sql(
			"""
			UPDATE `tabOrdre de Conditionnement`
			SET modele_checklist = %s
			WHERE ifnull(modele_checklist, '') = ''
			""",
			CHECKLIST_STANDARD,
		)
