# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_bulk, bureau_commandes, bureau_factures
from unicare.tests.test_bureau_commandes import _article
from unicare.tests.test_bureau_devis import _client


class TestFactures(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.client = _client()
		self.service = _article("Prestation essai facture", 1000, stock=False)

	def tearDown(self):
		frappe.db.rollback()

	def _facture(self, quantite=2, taxes=None):
		commande = bureau_commandes.create_commande(
			json.dumps(
				{
					"client": self.client,
					"livraison": add_days(today(), 3),
					"taxes": taxes or "",
					"lignes": [{"article": self.service, "quantite": quantite}],
				}
			)
		)["name"]
		detail = bureau_commandes.validate_commande(
			commande, bureau_commandes.get_commande(commande)["modified"]
		)
		result = bureau_commandes.create_suivante(commande, detail["modified"], "facture")
		return commande, bureau_factures.get_facture(result["name"])

	def _valider(self, facture):
		return bureau_factures.validate_facture(facture["name"], facture["modified"])

	def test_brouillon_echeance_et_validation(self):
		commande, facture = self._facture()
		self.assertEqual((facture["status"], facture["commandes"]), ("Draft", [commande]))
		self.assertIn("modifier", facture["actions"])
		with self.assertRaises(frappe.ValidationError):
			bureau_factures.update_facture(
				facture["name"], facture["modified"], echeance=add_days(today(), -5)
			)
		facture = bureau_factures.update_facture(
			facture["name"], facture["modified"], echeance=add_days(today(), 30)
		)
		self.assertEqual(facture["echeance"], add_days(today(), 30))
		with self.assertRaises(frappe.ValidationError):
			bureau_factures.update_facture(
				facture["name"],
				facture["modified"],
				lignes=json.dumps([{"name": facture["lignes"][0]["name"], "quantite": 1}]),
			)
		facture = self._valider(facture)
		self.assertEqual((facture["status"], facture["reste"]), ("Unpaid", 2000))
		self.assertTrue({"encaisser", "avoir", "annuler"} <= set(facture["actions"]))
		self.assertEqual(bureau_commandes.get_commande(commande)["facture"], 100)

	def test_encaissement_partiel_puis_total(self):
		_commande, facture = self._facture()
		facture = self._valider(facture)
		modes = {row["value"]: row["type"] for row in facture["modes"]}
		especes = next(name for name, kind in modes.items() if kind == "Cash")
		banque = next((name for name, kind in modes.items() if kind == "Bank"), None)
		for montant in (0, 2500):
			with self.subTest(montant=montant), self.assertRaises(frappe.ValidationError):
				bureau_factures.encaisser(facture["name"], facture["modified"], montant, especes)
		result = bureau_factures.encaisser(facture["name"], facture["modified"], 500, especes)
		facture = result["facture"]
		self.assertEqual((facture["status"], facture["reste"], facture["paye"]), ("Partly Paid", 1500, 500))
		self.assertEqual([row["name"] for row in facture["paiements"]], [result["paiement"]])
		if banque:
			with self.assertRaises(frappe.ValidationError):
				bureau_factures.encaisser(facture["name"], facture["modified"], 100, banque)
			facture = bureau_factures.encaisser(
				facture["name"], facture["modified"], 1500, banque, reference="CHQ-1234"
			)["facture"]
		else:
			facture = bureau_factures.encaisser(facture["name"], facture["modified"], 1500, especes)[
				"facture"
			]
		self.assertEqual((facture["status"], facture["reste"]), ("Paid", 0))
		self.assertNotIn("encaisser", facture["actions"])

	def test_avoir_partiel(self):
		_commande, facture = self._facture()
		facture = self._valider(facture)
		result = bureau_factures.create_avoir(facture["name"], facture["modified"])
		avoir = bureau_factures.get_facture(result["name"])
		self.assertEqual(
			(avoir["avoir"], avoir["avoir_de"], avoir["lignes"][0]["quantite"]), (1, facture["name"], -2)
		)
		avoir = bureau_factures.update_facture(
			avoir["name"],
			avoir["modified"],
			lignes=json.dumps([{"name": avoir["lignes"][0]["name"], "quantite": -1}]),
		)
		avoir = self._valider(avoir)
		self.assertEqual(avoir["total_ttc"], -1000)
		facture = bureau_factures.get_facture(facture["name"])
		self.assertEqual(facture["reste"], 1000)
		self.assertEqual([row["name"] for row in facture["avoirs"]], [avoir["name"]])

	def test_liste_annulation_suppression(self):
		_commande, brouillon = self._facture()
		_commande, facture = self._facture(quantite=1)
		facture = self._valider(facture)
		response = bureau_factures.get_factures(page_length=500)
		self.assertEqual(response["counts"]["all"], response["total"])
		self.assertIn(facture["name"], response["names"])
		self.assertGreaterEqual(response["reste_du"], 1000)
		self.assertEqual(
			bureau_factures.get_factures(view="impayees", page_length=500)["counts"]["impayees"],
			sum(1 for row in response["factures"] if bureau_factures.in_view("impayees", row)),
		)
		self.assertEqual(
			bureau_factures.cancel_facture(facture["name"], facture["modified"])["status"], "Cancelled"
		)
		bureau_factures.delete_facture(brouillon["name"], brouillon["modified"])
		self.assertFalse(frappe.db.exists("Sales Invoice", brouillon["name"]))
		self.assertIn("Sales Invoice", bureau_bulk.BULK_DOCTYPES)
