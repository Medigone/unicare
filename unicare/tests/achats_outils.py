# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Aides communes aux tests des pièces d'achat du bureau : un fournisseur et des articles d'achat."""

import json

import frappe

from unicare.api import bureau_achats, bureau_articles, bureau_fournisseurs


def fournisseur(nom="Fournisseur Essai Achats"):
	return bureau_fournisseurs.create_fournisseur(
		json.dumps(
			{
				"supplier_name": nom,
				"categorie": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
			}
		)
	)["name"]


def article(designation, prix=None, stock=False, lots=False):
	"""Article d'achat ; `prix` : prix au tarif d'achat. `stock` : article stocké, pour les réceptions."""
	name = bureau_articles.create_article(
		json.dumps(
			{
				"type": "Autre",
				"designation": designation,
				"groupe": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"uom": frappe.db.get_value("Item", {}, "stock_uom"),
				"is_stock_item": 1 if stock else 0,
			}
		)
	)["name"]
	frappe.db.set_value("Item", name, {"is_purchase_item": 1, "has_batch_no": 1 if lots else 0})
	if prix is not None:
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": name,
				"price_list": bureau_achats.buying_price_list(),
				"price_list_rate": prix,
				"buying": 1,
			}
		).insert()
	return name
