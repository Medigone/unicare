# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_bulk, bureau_commandes, bureau_livraisons
from unicare.tests.test_bureau_devis import _client

STOCK_PF = "Produits finis - U"


def _produit_fini():
	"""Un produit fini géré par lots, avec du stock en lots dans « Produits finis ». Sinon le test est sauté."""
	item = frappe.db.get_value(
		"Bin",
		{"warehouse": STOCK_PF, "actual_qty": [">=", 10]},
		"item_code",
	)
	if not item or not frappe.db.get_value("Item", item, "has_batch_no"):
		return None
	frappe.db.set_value("Item", item, "is_sales_item", 1)
	return item


class TestLivraisons(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.produit = _produit_fini()
		if not self.produit:
			self.skipTest("Aucun produit fini en stock par lots sur ce site.")
		self.client = _client()

	def tearDown(self):
		frappe.db.rollback()

	def _livraison(self, quantite=5):
		commande = bureau_commandes.create_commande(
			json.dumps(
				{
					"client": self.client,
					"livraison": add_days(today(), 3),
					"lignes": [{"article": self.produit, "quantite": quantite, "prix": 100}],
				}
			)
		)["name"]
		detail = bureau_commandes.validate_commande(
			commande, bureau_commandes.get_commande(commande)["modified"]
		)
		result = bureau_commandes.create_suivante(commande, detail["modified"], "livraison")
		self.assertEqual(result["doctype"], "Delivery Note")
		return commande, bureau_livraisons.get_livraison(result["name"])

	def _preparer(self, livraison, **extra):
		line = livraison["lignes"][0]
		lot = line["lots"][STOCK_PF][0]
		values = {"name": line["name"], "depot": STOCK_PF, "lot": lot["lot"], **extra}
		return bureau_livraisons.prepare_livraison(
			livraison["name"], livraison["modified"], json.dumps([values])
		)

	def test_preparation_lot_et_validation(self):
		commande, livraison = self._livraison()
		line = livraison["lignes"][0]
		self.assertEqual(line["avec_lot"], 1)
		self.assertIn(STOCK_PF, [entry["depot"] for entry in line["depots"]])
		self.assertTrue(livraison["blocked"])
		with self.assertRaises(frappe.ValidationError):
			bureau_livraisons.validate_livraison(livraison["name"], livraison["modified"])
		livraison = self._preparer(livraison)
		self.assertEqual(livraison["blocked"], [])
		livraison = bureau_livraisons.validate_livraison(livraison["name"], livraison["modified"])
		self.assertEqual(livraison["status"], "To Bill")
		self.assertEqual(livraison["commandes"], [commande])
		self.assertEqual(bureau_commandes.get_commande(commande)["livre"], 100)

	def test_quantite_au_dela_du_lot_bloque(self):
		_commande, livraison = self._livraison()
		lot = livraison["lignes"][0]["lots"][STOCK_PF][0]
		livraison = self._preparer(livraison, quantite=lot["qty"] + 1)
		self.assertTrue(any("disponible" in reason for reason in livraison["blocked"]))
		with self.assertRaises(frappe.ValidationError):
			self._preparer(
				livraison, lot=frappe.db.get_value("Batch", {"item": ["!=", self.produit]}, "name") or "x"
			)

	def test_facture_retour_annulation(self):
		_commande, livraison = self._livraison()
		livraison = self._preparer(livraison)
		livraison = bureau_livraisons.validate_livraison(livraison["name"], livraison["modified"])
		self.assertTrue({"facture", "retour", "annuler"} <= set(livraison["actions"]))
		facture = bureau_livraisons.create_suivante(livraison["name"], livraison["modified"], "facture")
		self.assertEqual(frappe.db.get_value("Sales Invoice", facture["name"], "docstatus"), 0)
		retour = bureau_livraisons.create_suivante(
			livraison["name"], facture["livraison"]["modified"], "retour"
		)
		detail = bureau_livraisons.get_livraison(retour["name"])
		self.assertEqual((detail["retour"], detail["retour_de"]), (1, livraison["name"]))
		with self.assertRaises(frappe.ValidationError):
			bureau_livraisons.prepare_livraison(
				detail["name"],
				detail["modified"],
				json.dumps([{"name": detail["lignes"][0]["name"], "quantite": 2}]),
			)
		detail = bureau_livraisons.prepare_livraison(
			detail["name"],
			detail["modified"],
			json.dumps([{"name": detail["lignes"][0]["name"], "quantite": -2}]),
		)
		detail = bureau_livraisons.validate_livraison(detail["name"], detail["modified"])
		self.assertEqual(detail["status"], "Return")
		self.assertEqual(
			[row["name"] for row in bureau_livraisons.get_livraison(livraison["name"])["retours"]],
			[detail["name"]],
		)
		frappe.delete_doc("Sales Invoice", facture["name"])
		courante = bureau_livraisons.get_livraison(livraison["name"])
		with self.assertRaises(frappe.ValidationError):
			# Le retour validé dépend du bon : ERPNext refuse l'annulation.
			bureau_livraisons.cancel_livraison(courante["name"], courante["modified"])

	def test_liste_suppression_et_groupe(self):
		_commande, livraison = self._livraison()
		response = bureau_livraisons.get_livraisons(page_length=500)
		row = next(row for row in response["livraisons"] if row["name"] == livraison["name"])
		self.assertEqual((row["status"], row["retour"]), ("Draft", 0))
		self.assertEqual(response["counts"]["all"], response["total"])
		with self.assertRaises(frappe.ValidationError):
			bureau_livraisons.prepare_livraison(
				livraison["name"],
				livraison["modified"],
				json.dumps([{"name": livraison["lignes"][0]["name"], "quantite": 0}]),
			)
		bureau_livraisons.delete_livraison(livraison["name"], livraison["modified"])
		self.assertFalse(frappe.db.exists("Delivery Note", livraison["name"]))
		self.assertIn("Delivery Note", bureau_bulk.BULK_DOCTYPES)
