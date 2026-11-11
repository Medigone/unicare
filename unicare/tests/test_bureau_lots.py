# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_bulk, bureau_lots, bureau_stock
from unicare.conditionnement.stock import ensure_batch
from unicare.tests.achats_outils import article

L = bureau_lots


class TestVuesLots(FrappeTestCase):
	def test_vues(self):
		day = today()
		self.assertTrue(L.in_view("perimes", {"quantite": 5, "peremption": add_days(day, -1), "desactive": 0}, day))
		self.assertFalse(L.in_view("perimes", {"quantite": 0, "peremption": add_days(day, -1), "desactive": 0}, day))
		self.assertTrue(L.in_view("expirent", {"quantite": 5, "peremption": add_days(day, 10), "desactive": 0}, day))
		self.assertFalse(L.in_view("expirent", {"quantite": 5, "peremption": add_days(day, 60), "desactive": 0}, day))
		self.assertTrue(L.in_view("vides", {"quantite": 0, "peremption": None, "desactive": 0}, day))
		self.assertTrue(L.in_view("desactives", {"quantite": 0, "peremption": None, "desactive": 1}, day))


class TestLots(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_liste_et_stock_perimes_compris(self):
		response = L.get_lots(page_length=500)
		self.assertEqual(response["counts"]["all"], response["total"])
		stocks = bureau_stock.stock_par_lot()
		for row in response["lots"]:
			if row["name"] in stocks:
				self.assertAlmostEqual(sum(stocks[row["name"]].values()), row["quantite"], places=3)

	def test_fiche_modification_suppression(self):
		item = article("Article essai lots", stock=True, lots=True)
		lot = ensure_batch(item_code=item, batch_no="LOT-ESSAI-BUREAU", origine="Réception")
		fiche = L.get_lot(lot, full=1)
		self.assertEqual(fiche["depots"], [])
		self.assertEqual(fiche["mouvements"], [])
		fiche = L.update_lot(lot, fiche["modified"], json.dumps({"peremption": add_days(today(), 90), "lot_fournisseur": "F-9"}))
		self.assertEqual(fiche["peremption"], add_days(today(), 90))
		self.assertEqual(fiche["lot_fournisseur"], "F-9")
		with self.assertRaises(frappe.ValidationError):
			L.update_lot(lot, fiche["modified"], json.dumps({"fabrication": add_days(today(), 200)}))
		with self.assertRaises(frappe.TimestampMismatchError):
			L.delete_lot(lot, "2000-01-01 00:00:00")
		L.delete_lot(lot, fiche["modified"])
		self.assertFalse(frappe.db.exists("Batch", lot))

	def test_actions_groupees(self):
		bulk = {field["fieldname"] for field in bureau_bulk.get_bulk_options("Batch")["fields"]}
		self.assertIn("expiry_date", bulk)
		self.assertNotIn("item", bulk)
		self.assertNotIn("custom_origine", bulk)
