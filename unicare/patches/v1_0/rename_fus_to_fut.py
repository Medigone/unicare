# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe


def execute():
	if frappe.db.has_column("Item", "custom_type_conditionnement"):
		frappe.db.sql(
			"UPDATE `tabItem` SET custom_type_conditionnement = %s WHERE custom_type_conditionnement = %s",
			("Fût", "FUS"),
		)

	if frappe.db.table_exists("Ingredient Recette"):
		frappe.db.sql(
			"UPDATE `tabIngredient Recette` SET type_ingredient = %s WHERE type_ingredient = %s",
			("Fût", "FUS"),
		)

	if frappe.db.table_exists("Matiere Ordre Conditionnement"):
		frappe.db.sql(
			"UPDATE `tabMatiere Ordre Conditionnement` SET type_ingredient = %s WHERE type_ingredient = %s",
			("Fût", "FUS"),
		)
