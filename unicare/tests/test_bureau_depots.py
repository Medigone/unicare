# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_bulk, bureau_depots, bureau_stock


class TestDepots(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_liste_vues_et_totaux(self):
		response = bureau_depots.get_depots(page_length=500)
		self.assertEqual(response["counts"]["all"], response["total"])
		self.assertTrue(all(row["name"] in bureau_stock.depots() or row["desactive"] for row in response["depots"]))
		avec_stock = bureau_depots.get_depots(view="avec_stock", page_length=500)
		self.assertTrue(all(row["articles"] > 0 for row in avec_stock["depots"]))
		with self.assertRaises(frappe.ValidationError):
			bureau_depots.get_depots(view="inconnue")

	def test_fiche_stock_et_mouvements(self):
		name = bureau_stock.depots()[0]
		fiche = bureau_depots.get_depot(name, full=1)
		self.assertIn("stock", fiche)
		self.assertIsInstance(fiche["mouvements"], list)
		self.assertTrue(all(row["depot"] == name for row in fiche["mouvements"]))

	def test_creation_modification_suppression(self):
		groupe = bureau_depots.get_depot_options()["groupes"][0]
		name = bureau_depots.create_depot(json.dumps({"depot": "Dépôt essai bureau", "parent": groupe}))["name"]
		doc = frappe.get_doc("Warehouse", name)
		self.assertEqual(doc.parent_warehouse, groupe)
		with self.assertRaises(frappe.ValidationError):
			bureau_depots.create_depot(json.dumps({"depot": ""}))
		with self.assertRaises(frappe.ValidationError):
			bureau_depots.update_depot(name, str(doc.modified), json.dumps({"parent": "Groupe inconnu"}))
		fiche = bureau_depots.update_depot(name, str(doc.modified), json.dumps({"desactive": 1}))
		self.assertEqual(fiche["desactive"], 1)
		with self.assertRaises(frappe.TimestampMismatchError):
			bureau_depots.delete_depot(name, str(doc.modified))
		bureau_depots.delete_depot(name, fiche["modified"])
		self.assertFalse(frappe.db.exists("Warehouse", name))

	def test_depot_avec_stock_ne_se_desactive_pas(self):
		plein = bureau_depots.get_depots(view="avec_stock", page_length=1)["depots"]
		if not plein:
			return
		doc = frappe.get_doc("Warehouse", plein[0]["name"])
		with self.assertRaises(frappe.ValidationError):
			bureau_depots.update_depot(doc.name, str(doc.modified), json.dumps({"desactive": 1}))

	def test_actions_groupees(self):
		bulk = {field["fieldname"] for field in bureau_bulk.get_bulk_options("Warehouse")["fields"]}
		self.assertNotIn("warehouse_name", bulk)
		self.assertNotIn("company", bulk)


class TestGrandLivre(FrappeTestCase):
	def test_lot_lu_dans_le_bundle(self):
		lot = frappe.db.get_value("Serial and Batch Entry", {"batch_no": ["is", "set"]}, "batch_no")
		if not lot:
			return
		rows = bureau_stock.ledger(lot=lot)
		self.assertTrue(rows)
		self.assertTrue(all(lot in row["lots"] for row in rows))
