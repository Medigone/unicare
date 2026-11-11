# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_achats, bureau_bulk, bureau_commandes_achat, bureau_factures_achat
from unicare.tests.achats_outils import article, fournisseur

FA = bureau_factures_achat
CA = bureau_commandes_achat


class TestVuesFacturesAchat(FrappeTestCase):
	def test_vues(self):
		self.assertTrue(FA.in_view("a_payer", {"status": "Partly Paid", "avoir": 0}))
		self.assertFalse(FA.in_view("a_payer", {"status": "Unpaid", "avoir": 1}))
		self.assertTrue(FA.in_view("en_retard", {"status": "Overdue", "avoir": 0}))
		self.assertTrue(FA.in_view("avoirs", {"status": "Return", "avoir": 1}))
		self.assertFalse(FA.in_view("clos", {"status": "Return", "avoir": 1}))
		self.assertTrue(FA.in_view("clos", {"status": "Debit Note Issued", "avoir": 0}))


class TestFactureAchat(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.fournisseur = fournisseur("Fournisseur Essai Factures")
		self.article = article("Service essai facture", 1000)

	def tearDown(self):
		frappe.db.rollback()

	def _facture(self):
		name = CA.create_commande_achat(
			json.dumps(
				{
					"fournisseur": self.fournisseur,
					"reception": add_days(today(), 3),
					"taxes": bureau_achats.taxes_options(CA._company())["taxes_defaut"],
					"lignes": [{"article": self.article, "quantite": 2}],
				}
			)
		)["name"]
		fiche = CA.validate_commande_achat(name, CA.get_commande_achat(name)["modified"])
		return CA.create_suivante(name, fiche["modified"], "facture")["name"]

	def test_numero_fournisseur_exige_puis_paiement_et_avoir(self):
		name = self._facture()
		fiche = FA.get_facture_achat(name)
		self.assertTrue(any("numéro" in reason for reason in fiche["blocked"]))
		with self.assertRaises(frappe.ValidationError):
			FA.validate_facture_achat(name, fiche["modified"])
		fiche = FA.update_facture_achat(
			name,
			fiche["modified"],
			json.dumps({"numero_fournisseur": "FF-2026-118", "date_fournisseur": today(), "echeance": add_days(today(), 30)}),
		)
		self.assertEqual(fiche["numero_fournisseur"], "FF-2026-118")
		self.assertEqual(fiche["blocked"], [])
		fiche = FA.validate_facture_achat(name, fiche["modified"])
		self.assertEqual(fiche["status"], "Unpaid")
		self.assertIn("payer", fiche["actions"])
		total = fiche["total_ttc"]
		self.assertGreater(total, 2000)
		with self.assertRaises(frappe.ValidationError):
			FA.payer(name, fiche["modified"], total + 1, "Espèces")
		result = FA.payer(name, fiche["modified"], 1000, "Espèces")
		self.assertEqual(frappe.db.get_value("Payment Entry", result["paiement"], "payment_type"), "Pay")
		self.assertEqual(result["facture"]["status"], "Partly Paid")
		self.assertEqual(result["facture"]["paiements"][0]["montant"], 1000)
		avoir = FA.create_avoir(name, result["facture"]["modified"])
		self.assertEqual(frappe.db.get_value("Purchase Invoice", avoir["name"], "is_return"), 1)
		self.assertEqual(len(avoir["facture"]["avoirs"]), 1)
		liste = FA.get_factures_achat(view="a_payer", page_length=500)
		self.assertIn(name, liste["names"])

	def test_refus_et_actions_groupees(self):
		name = self._facture()
		fiche = FA.get_facture_achat(name)
		with self.assertRaises(frappe.ValidationError):
			FA.update_facture_achat(name, fiche["modified"], json.dumps({"echeance": add_days(today(), -5)}))
		with self.assertRaises(frappe.ValidationError):
			FA.update_facture_achat(name, fiche["modified"], json.dumps({"lignes": [{"name": "x", "quantite": 1}]}))
		with self.assertRaises(frappe.TimestampMismatchError):
			FA.validate_facture_achat(name, "2000-01-01 00:00:00")
		bulk = {field["fieldname"] for field in bureau_bulk.get_bulk_options("Purchase Invoice")["fields"]}
		self.assertNotIn("bill_no", bulk)
