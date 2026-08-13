# Copyright (c) 2026, IntraPro and contributors
# For license information, please see license.txt

import frappe


def execute():
	_delete_reception_documents()
	_clear_stock_entry_link()
	_delete_custom_field()
	_delete_doctype("Reception de Matieres")
	_delete_doctype("Ligne Reception Matiere")


def _delete_reception_documents():
	if frappe.db.table_exists("Ligne Reception Matiere"):
		frappe.db.sql("DELETE FROM `tabLigne Reception Matiere`")

	if frappe.db.table_exists("Reception de Matieres"):
		frappe.db.sql("DELETE FROM `tabReception de Matieres`")


def _clear_stock_entry_link():
	if frappe.db.has_column("Stock Entry", "custom_reception_de_matieres"):
		frappe.db.sql("UPDATE `tabStock Entry` SET custom_reception_de_matieres = NULL")


def _delete_custom_field():
	if frappe.db.exists("Custom Field", "Stock Entry-custom_reception_de_matieres"):
		frappe.delete_doc("Custom Field", "Stock Entry-custom_reception_de_matieres", force=1)


def _delete_doctype(name):
	if frappe.db.exists("DocType", name):
		frappe.delete_doc("DocType", name, force=1)
