# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_achats, bureau_bulk, bureau_commandes_achat
from unicare.tests.achats_outils import article, fournisseur

CA = bureau_commandes_achat


class TestVuesCommandesAchat(FrappeTestCase):
	def test_vues(self):
		day = today()
		self.assertTrue(CA.in_view("a_recevoir", {"status": "To Receive and Bill"}, day))
		self.assertFalse(CA.in_view("a_recevoir", {"status": "To Bill"}, day))
		self.assertTrue(CA.in_view("a_facturer", {"status": "To Bill"}, day))
		self.assertTrue(CA.in_view("en_retard", {"status": "To Receive", "reception": add_days(day, -1)}, day))
		self.assertFalse(CA.in_view("en_retard", {"status": "To Bill", "reception": add_days(day, -1)}, day))
		self.assertTrue(CA.in_view("clos", {"status": "Closed"}, day))
		self.assertTrue(CA.in_view("en_attente", {"status": "On Hold"}, day))


class TestCommandeAchat(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.fournisseur = fournisseur("Fournisseur Essai Commandes")
		self.article = article("Carton essai commande", 50, stock=True)

	def tearDown(self):
		frappe.db.rollback()

	def _commande(self, **extra):
		values = {
			"fournisseur": self.fournisseur,
			"reception": add_days(today(), 5),
			"taxes": bureau_achats.taxes_options(CA._company())["taxes_defaut"],
			"lignes": [{"article": self.article, "quantite": 20}],
			**extra,
		}
		return CA.create_commande_achat(json.dumps(values))["name"]

	def test_creation_et_refus(self):
		fiche = CA.get_commande_achat(self._commande())
		self.assertEqual(fiche["lignes"][0]["prix"], 50)
		self.assertEqual(fiche["lignes"][0]["reception"], add_days(today(), 5))
		self.assertEqual(fiche["actions"], ["modifier", "valider", "supprimer"])
		with self.assertRaises(frappe.ValidationError):
			self._commande(reception="")
		with self.assertRaises(frappe.ValidationError):
			self._commande(reception=add_days(today(), -2))

	def test_cycle_reception_facture_statuts(self):
		name = self._commande()
		fiche = CA.update_commande_achat(
			name,
			CA.get_commande_achat(name)["modified"],
			json.dumps({"lignes": [{"article": self.article, "quantite": 10, "prix": 45}]}),
		)
		self.assertEqual(fiche["total"], 450)
		fiche = CA.validate_commande_achat(name, fiche["modified"])
		self.assertEqual(fiche["status"], "To Receive and Bill")
		self.assertIn("reception", fiche["actions"])
		self.assertIn("attente", fiche["actions"])
		fiche = CA.set_commande_achat_status(name, fiche["modified"], "attente")
		self.assertEqual(fiche["status"], "On Hold")
		self.assertNotIn("reception", fiche["actions"])
		fiche = CA.set_commande_achat_status(name, fiche["modified"], "reprendre")
		self.assertEqual(fiche["status"], "To Receive and Bill")
		result = CA.create_suivante(name, fiche["modified"], "reception")
		self.assertEqual(result["doctype"], "Purchase Receipt")
		self.assertEqual([row["name"] for row in result["commande"]["receptions"]], [result["name"]])
		facture = CA.create_suivante(name, result["commande"]["modified"], "facture")
		self.assertEqual(facture["doctype"], "Purchase Invoice")
		self.assertEqual(frappe.db.get_value("Purchase Invoice", facture["name"], "docstatus"), 0)
		liste = CA.get_commandes_achat(view="a_recevoir", page_length=500)
		self.assertIn(name, liste["names"])

	def test_version_et_actions_groupees(self):
		name = self._commande()
		with self.assertRaises(frappe.TimestampMismatchError):
			CA.validate_commande_achat(name, "2000-01-01 00:00:00")
		fiche = CA.validate_commande_achat(name, CA.get_commande_achat(name)["modified"])
		result = bureau_bulk.bulk_delete("Purchase Order", json.dumps([{"name": name, "modified": fiche["modified"]}]))
		self.assertEqual(result["done"], [])
