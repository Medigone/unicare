# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_articles, bureau_bulk, bureau_commandes, bureau_devis
from unicare.tests.test_bureau_devis import _client


def _article(designation, prix, stock=True):
	name = bureau_articles.create_article(
		json.dumps(
			{
				"type": "Conditionnement" if stock else "Autre",
				"designation": designation,
				"groupe": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"uom": frappe.db.get_value("Item", {}, "stock_uom"),
				"is_stock_item": 1 if stock else 0,
			}
		)
	)["name"]
	frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": name,
			"price_list": bureau_devis._price_list(),
			"price_list_rate": prix,
		}
	).insert()
	return name


class TestCommandes(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.client = _client()
		self.flacon = _article("Flacon essai commande", 120)
		self.service = _article("Étiquetage essai commande", 30, stock=False)

	def tearDown(self):
		frappe.db.rollback()

	def _commande(self, **extra):
		values = {
			"client": self.client,
			"livraison": add_days(today(), 10),
			"taxes": bureau_commandes.get_commande_options()["taxes"][0]["value"],
			"reference": "BC-2026-14",
			"lignes": [
				{"article": self.flacon, "quantite": 100},
				{"article": self.service, "quantite": 100, "prix": 25},
			],
			**extra,
		}
		return bureau_commandes.create_commande(json.dumps(values))["name"]

	def _valider(self, name):
		return bureau_commandes.validate_commande(name, bureau_commandes.get_commande(name)["modified"])

	def test_creation(self):
		commande = bureau_commandes.get_commande(self._commande())
		self.assertEqual(commande["status"], "Draft")
		self.assertEqual([line["prix"] for line in commande["lignes"]], [120, 25])
		self.assertEqual(commande["total"], 14500)
		self.assertEqual(commande["reference"], "BC-2026-14")
		self.assertTrue(all(line["livraison"] == commande["livraison"] for line in commande["lignes"]))
		self.assertEqual(commande["blocked"], [])
		for values in ({"client": ""}, {"livraison": add_days(today(), -1)}, {"lignes": []}):
			with self.subTest(values=values), self.assertRaises(frappe.ValidationError):
				self._commande(**values)

	def test_modification_du_brouillon(self):
		name = self._commande()
		commande = bureau_commandes.update_commande(
			name,
			bureau_commandes.get_commande(name)["modified"],
			json.dumps(
				{"livraison": add_days(today(), 20), "lignes": [{"article": self.flacon, "quantite": 5}]}
			),
		)
		self.assertEqual((commande["total"], len(commande["lignes"])), (600, 1))
		self.assertEqual(commande["lignes"][0]["livraison"], commande["livraison"])

	def test_cycle_livraison_facture_statuts(self):
		name = self._commande()
		commande = self._valider(name)
		self.assertEqual(commande["status"], "To Deliver and Bill")
		self.assertTrue(
			{"livraison", "facture", "attente", "cloturer", "annuler"} <= set(commande["actions"])
		)
		livraison = bureau_commandes.create_suivante(name, commande["modified"], "livraison")
		self.assertEqual(frappe.db.get_value("Delivery Note", livraison["name"], "docstatus"), 0)
		self.assertEqual([row["name"] for row in livraison["commande"]["livraisons"]], [livraison["name"]])
		facture = bureau_commandes.create_suivante(name, livraison["commande"]["modified"], "facture")
		self.assertEqual(facture["doctype"], "Sales Invoice")
		commande = bureau_commandes.set_commande_status(name, facture["commande"]["modified"], "attente")
		self.assertEqual((commande["status"], commande["actions"]), ("On Hold", ["reprendre", "annuler"]))
		commande = bureau_commandes.set_commande_status(name, commande["modified"], "reprendre")
		self.assertEqual(commande["status"], "To Deliver and Bill")
		commande = bureau_commandes.set_commande_status(name, commande["modified"], "cloturer")
		self.assertEqual(commande["status"], "Closed")
		with self.assertRaises(frappe.PermissionError):
			bureau_commandes.create_suivante(name, commande["modified"], "livraison")

	def test_annuler_supprimer_et_liste(self):
		name = self._commande()
		commande = self._valider(name)
		self.assertEqual(bureau_commandes.cancel_commande(name, commande["modified"])["status"], "Cancelled")
		brouillon = self._commande()
		response = bureau_commandes.get_commandes(page_length=500)
		self.assertEqual(response["counts"]["all"], response["total"])
		row = next(row for row in response["commandes"] if row["name"] == brouillon)
		self.assertEqual((row["status"], row["lignes"], row["reference"]), ("Draft", 2, "BC-2026-14"))
		self.assertEqual(
			response["counts"]["clos"],
			sum(1 for r in response["commandes"] if r["status"] in bureau_commandes.CLOS),
		)
		bureau_commandes.delete_commande(brouillon, bureau_commandes.get_commande(brouillon)["modified"])
		self.assertFalse(frappe.db.exists("Sales Order", brouillon))
		self.assertTrue(
			bureau_commandes.in_view(
				"en_retard", {"status": "To Deliver", "livraison": add_days(today(), -2)}
			)
		)
		self.assertFalse(
			bureau_commandes.in_view("en_retard", {"status": "To Bill", "livraison": add_days(today(), -2)})
		)
		self.assertIn("Sales Order", bureau_bulk.BULK_DOCTYPES)

	def test_commande_depuis_un_devis(self):
		devis = bureau_devis.create_devis(
			json.dumps(
				{
					"client": self.client,
					"valable": add_days(today(), 30),
					"lignes": [{"article": self.flacon, "quantite": 3}],
				}
			)
		)["name"]
		detail = bureau_devis.validate_devis(devis, bureau_devis.get_devis(devis)["modified"])
		name = bureau_devis.create_commande(devis, detail["modified"], add_days(today(), 5))["commande"]
		commande = bureau_commandes.get_commande(name)
		self.assertEqual(commande["devis"], [devis])
		with self.assertRaises(frappe.ValidationError):
			bureau_commandes.update_commande(
				name, commande["modified"], json.dumps({"lignes": [{"article": self.flacon, "quantite": 1}]})
			)
