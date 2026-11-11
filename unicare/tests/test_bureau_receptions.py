# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_achats, bureau_bulk, bureau_commandes_achat, bureau_receptions
from unicare.tests.achats_outils import article, fournisseur

RE = bureau_receptions
CA = bureau_commandes_achat


class TestVuesReceptions(FrappeTestCase):
	def test_vues(self):
		self.assertTrue(RE.in_view("a_facturer", {"status": "To Bill", "retour": 0}))
		self.assertFalse(RE.in_view("a_facturer", {"status": "To Bill", "retour": 1}))
		self.assertTrue(RE.in_view("retours", {"status": "Completed", "retour": 1}))
		self.assertTrue(RE.in_view("facturees", {"status": "Completed", "retour": 0}))
		self.assertTrue(RE.in_view("clos", {"status": "Return Issued", "retour": 0}))


class TestReception(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.fournisseur = fournisseur("Fournisseur Essai Réceptions")
		self.article = article("Flacon essai réception", 30, stock=True, lots=True)

	def tearDown(self):
		frappe.db.rollback()

	def _reception(self, quantite=10):
		name = CA.create_commande_achat(
			json.dumps(
				{
					"fournisseur": self.fournisseur,
					"reception": add_days(today(), 2),
					"lignes": [{"article": self.article, "quantite": quantite}],
				}
			)
		)["name"]
		fiche = CA.validate_commande_achat(name, CA.get_commande_achat(name)["modified"])
		return CA.create_suivante(name, fiche["modified"], "reception")["name"], name

	def test_lot_attendu_puis_cree_a_la_preparation(self):
		name, commande = self._reception()
		fiche = RE.get_reception(name)
		self.assertEqual(fiche["commandes"], [commande])
		self.assertTrue(fiche["lignes"][0]["avec_lot"])
		self.assertTrue(any("lot" in reason for reason in fiche["blocked"]))
		with self.assertRaises(frappe.ValidationError):
			RE.validate_reception(name, fiche["modified"])
		ligne = fiche["lignes"][0]
		fiche = RE.prepare_reception(
			name,
			fiche["modified"],
			json.dumps([{"name": ligne["name"], "quantite": 6, "lot": "LF-ESSAI-001", "peremption": add_days(today(), 400)}]),
			bl_fournisseur="BL-778",
		)
		self.assertEqual(fiche["lignes"][0]["quantite"], 6)
		self.assertEqual(fiche["lignes"][0]["lot"], "LF-ESSAI-001")
		self.assertEqual(fiche["lignes"][0]["peremption"], add_days(today(), 400))
		self.assertEqual(fiche["bl_fournisseur"], "BL-778")
		self.assertEqual(frappe.db.get_value("Batch", "LF-ESSAI-001", "item"), self.article)
		self.assertEqual(fiche["blocked"], [])
		fiche = RE.validate_reception(name, fiche["modified"])
		self.assertEqual(fiche["status"], "To Bill")
		self.assertEqual(frappe.db.get_value("Purchase Order", commande, "per_received"), 60)
		self.assertTrue({"facture", "retour", "annuler"} <= set(fiche["actions"]))
		facture = RE.create_suivante(name, fiche["modified"], "facture")
		self.assertEqual(facture["doctype"], "Purchase Invoice")
		retour = RE.create_suivante(name, facture["reception"]["modified"], "retour")
		self.assertEqual(frappe.db.get_value("Purchase Receipt", retour["name"], "is_return"), 1)
		self.assertEqual(len(retour["reception"]["retours"]), 1)

	def test_refus_et_actions_groupees(self):
		name, _commande = self._reception()
		fiche = RE.get_reception(name)
		ligne = fiche["lignes"][0]["name"]
		with self.assertRaises(frappe.ValidationError):
			RE.prepare_reception(name, fiche["modified"], json.dumps([{"name": ligne, "quantite": -1}]))
		with self.assertRaises(frappe.ValidationError):
			RE.prepare_reception(name, fiche["modified"], json.dumps([{"name": ligne, "depot": "Inconnu"}]))
		with self.assertRaises(frappe.ValidationError):
			RE.prepare_reception(name, fiche["modified"], json.dumps([{"name": ligne, "quantite": 0}]))
		with self.assertRaises(frappe.TimestampMismatchError):
			RE.prepare_reception(name, "2000-01-01 00:00:00", json.dumps([]))
		result = bureau_bulk.bulk_add_tags("Purchase Receipt", json.dumps([{"name": name, "modified": fiche["modified"]}]), json.dumps(["essai"]))
		self.assertEqual(result["done"], [name])


class TestTvaDesactivee(FrappeTestCase):
	"""Une réception antérieure au changement de TVA garde un modèle désactivé depuis : sa facture prend le modèle par défaut."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.fournisseur = fournisseur("Fournisseur Essai TVA")
		self.article = article("Bidon essai TVA", 80, stock=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_facture_depuis_reception_au_modele_desactive(self):
		company = CA._company()
		ancien = frappe.get_doc(
			{
				"doctype": "Purchase Taxes and Charges Template",
				"title": "TVA essai ancienne",
				"company": company,
				"taxes": [
					{
						"charge_type": "On Net Total",
						"account_head": frappe.db.get_value(
							"Account", {"company": company, "account_type": "Tax", "is_group": 0}, "name"
						),
						"description": "TVA ancienne",
						"rate": 17,
					}
				],
			}
		).insert()
		name = CA.create_commande_achat(
			json.dumps(
				{
					"fournisseur": self.fournisseur,
					"reception": add_days(today(), 2),
					"taxes": ancien.name,
					"lignes": [{"article": self.article, "quantite": 4}],
				}
			)
		)["name"]
		fiche = CA.validate_commande_achat(name, CA.get_commande_achat(name)["modified"])
		reception = CA.create_suivante(name, fiche["modified"], "reception")["name"]
		ligne = RE.get_reception(reception)["lignes"][0]["name"]
		fiche = RE.prepare_reception(
			reception,
			RE.get_reception(reception)["modified"],
			json.dumps([{"name": ligne, "depot": frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")}]),
		)
		fiche = RE.validate_reception(reception, fiche["modified"])
		frappe.db.set_value("Purchase Taxes and Charges Template", ancien.name, "disabled", 1)
		result = RE.create_suivante(reception, fiche["modified"], "facture")
		defaut = next(row.name for row in bureau_achats.purchase_taxes_templates(company) if row.is_default)
		self.assertEqual(frappe.db.get_value("Purchase Invoice", result["name"], "taxes_and_charges"), defaut)
		self.assertIn(ancien.name, result["note"])


class TestLotExpireSurFacture(FrappeTestCase):
	"""Le lot d'une réception expiré depuis ne bloque pas sa facture d'achat, qui ne touche pas au stock."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.fournisseur = fournisseur("Fournisseur Essai Lot Expiré")
		self.article = article("Flacon essai lot expiré", 25, stock=True, lots=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_facture_malgre_lot_expire(self):
		company = CA._company()
		name = CA.create_commande_achat(
			json.dumps(
				{
					"fournisseur": self.fournisseur,
					"reception": add_days(today(), 2),
					"lignes": [{"article": self.article, "quantite": 3}],
				}
			)
		)["name"]
		fiche = CA.validate_commande_achat(name, CA.get_commande_achat(name)["modified"])
		reception = CA.create_suivante(name, fiche["modified"], "reception")["name"]
		fiche = RE.get_reception(reception)
		fiche = RE.prepare_reception(
			reception,
			fiche["modified"],
			json.dumps(
				[
					{
						"name": fiche["lignes"][0]["name"],
						"lot": "LF-EXPIRE-01",
						"peremption": add_days(today(), 30),
						"depot": frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name"),
					}
				]
			),
		)
		fiche = RE.validate_reception(reception, fiche["modified"])
		frappe.db.set_value("Batch", "LF-EXPIRE-01", "expiry_date", add_days(today(), -1))
		frappe.clear_document_cache("Batch", "LF-EXPIRE-01")
		frappe.local.document_cache = {}
		frappe.cache.delete_value("Batch")
		result = RE.create_suivante(reception, fiche["modified"], "facture")
		facture = frappe.get_doc("Purchase Invoice", result["name"])
		self.assertFalse(facture.items[0].batch_no)
		self.assertEqual(facture.items[0].purchase_receipt, reception)
