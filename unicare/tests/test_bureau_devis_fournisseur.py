# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_achats, bureau_bulk, bureau_devis_fournisseur, bureau_fournisseurs
from unicare.tests.achats_outils import article, fournisseur

DF = bureau_devis_fournisseur


class TestVuesDevisFournisseur(FrappeTestCase):
	def test_vues(self):
		day = today()
		self.assertTrue(DF.in_view("brouillons", {"status": "Draft"}, day))
		self.assertTrue(DF.in_view("ouverts", {"status": "Submitted", "commande": False}, day))
		self.assertFalse(DF.in_view("ouverts", {"status": "Submitted", "commande": True}, day))
		self.assertTrue(DF.in_view("commandes", {"status": "Submitted", "commande": True}, day))
		self.assertTrue(
			DF.in_view("expirent", {"status": "Submitted", "commande": False, "valable": add_days(day, 3)}, day)
		)
		self.assertFalse(
			DF.in_view("expirent", {"status": "Submitted", "commande": False, "valable": add_days(day, 30)}, day)
		)
		self.assertTrue(DF.in_view("clos", {"status": "Expired"}, day))

	def test_ordre(self):
		rows = [{"name": "A", "date": "2026-01-02", "total": 5}, {"name": "B", "date": "2026-03-01", "total": 9}]
		self.assertEqual([row["name"] for row in DF.order_devis(rows)], ["B", "A"])
		self.assertEqual([row["name"] for row in DF.order_devis(rows, "total", "asc")], ["A", "B"])


class TestDevisFournisseur(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.fournisseur = fournisseur()
		self.avec_prix = article("Flacon essai achat", 120)
		self.sans_prix = article("Bouchon essai achat")

	def tearDown(self):
		frappe.db.rollback()

	def _devis(self, **extra):
		values = {
			"fournisseur": self.fournisseur,
			"valable": add_days(today(), 15),
			"reference": "DEV-F-42",
			"taxes": bureau_achats.taxes_options(DF._company())["taxes_defaut"],
			"lignes": [{"article": self.avec_prix, "quantite": 10, "prix": None}],
			**extra,
		}
		return DF.create_devis_fournisseur(json.dumps(values))["name"]

	def test_prix_d_achat_et_tva(self):
		fiche = DF.get_devis_fournisseur(self._devis())
		self.assertEqual(fiche["lignes"][0]["prix"], 120)
		self.assertEqual(fiche["reference"], "DEV-F-42")
		self.assertTrue(fiche["taxes"])
		self.assertGreater(fiche["total_ttc"], fiche["total"])
		self.assertEqual(fiche["actions"], ["modifier", "valider", "supprimer"])

	def test_ligne_sans_prix_bloque_la_validation(self):
		name = self._devis(lignes=[{"article": self.sans_prix, "quantite": 2}])
		fiche = DF.get_devis_fournisseur(name)
		self.assertTrue(fiche["blocked"])
		with self.assertRaises(frappe.ValidationError):
			DF.validate_devis_fournisseur(name, fiche["modified"])

	def test_refus(self):
		with self.assertRaises(frappe.ValidationError):
			self._devis(lignes=[])
		with self.assertRaises(frappe.ValidationError):
			self._devis(valable="2000-01-01")
		doc = frappe.get_doc("Supplier", self.fournisseur)
		bureau_fournisseurs.update_fournisseur(doc.name, str(doc.modified), json.dumps({"status": "Exclu"}))
		with self.assertRaises(frappe.ValidationError):
			self._devis()

	def test_cycle_jusqu_a_la_commande(self):
		name = self._devis()
		fiche = DF.get_devis_fournisseur(name)
		fiche = DF.update_devis_fournisseur(
			name, fiche["modified"], json.dumps({"lignes": [{"article": self.avec_prix, "quantite": 4, "prix": 100}]})
		)
		self.assertEqual(fiche["total"], 400)
		with self.assertRaises(frappe.TimestampMismatchError):
			DF.validate_devis_fournisseur(name, "2000-01-01 00:00:00")
		fiche = DF.validate_devis_fournisseur(name, fiche["modified"])
		self.assertEqual(fiche["status"], "Submitted")
		self.assertIn("commande", fiche["actions"])
		result = DF.create_commande_achat(name, fiche["modified"], add_days(today(), 7))
		commande = frappe.get_doc("Purchase Order", result["commande"])
		self.assertEqual(commande.supplier, self.fournisseur)
		self.assertEqual(commande.items[0].supplier_quotation, name)
		self.assertEqual(str(commande.schedule_date), add_days(today(), 7))
		self.assertEqual([row["name"] for row in result["devis"]["commandes"]], [commande.name])
		liste = DF.get_devis_fournisseurs(view="commandes", page_length=500)
		self.assertIn(name, liste["names"])

	def test_actions_groupees_et_bulk(self):
		name = self._devis()
		fiche = DF.validate_devis_fournisseur(name, DF.get_devis_fournisseur(name)["modified"])
		result = bureau_bulk.bulk_delete("Supplier Quotation", json.dumps([{"name": name, "modified": fiche["modified"]}]))
		self.assertEqual(result["done"], [])
		self.assertEqual(len(result["skipped"]), 1)
