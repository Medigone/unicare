# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_articles, bureau_bulk, bureau_clients, bureau_devis


def _client():
	return bureau_clients.create_client(
		json.dumps(
			{
				"customer_name": "Pharmacie Devis Essai",
				"forme_juridique": "SARL",
				"categorie": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
				"commune": frappe.db.get_value("Commune", {}, "name"),
			}
		)
	)["name"]


def _article(designation, prix=None):
	name = bureau_articles.create_article(
		json.dumps(
			{
				"type": "Autre",
				"designation": designation,
				"groupe": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"uom": frappe.db.get_value("Item", {}, "stock_uom"),
				"is_stock_item": 0,
			}
		)
	)["name"]
	if prix is not None:
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": name,
				"price_list": bureau_devis._price_list(),
				"price_list_rate": prix,
			}
		).insert()
	return name


class TestDevis(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.client = _client()
		self.avec_prix = _article("Lotion essai devis", 450)
		self.sans_prix = _article("Gel essai devis")

	def tearDown(self):
		frappe.db.rollback()

	def _devis(self, **extra):
		values = {
			"client": self.client,
			"valable": add_days(today(), 30),
			"taxes": bureau_devis.get_devis_options()["taxes"][0]["value"],
			"lignes": [{"article": self.avec_prix, "quantite": 10}],
			**extra,
		}
		return bureau_devis.create_devis(json.dumps(values))["name"]

	def test_creation_prix_du_tarif_et_tva(self):
		devis = bureau_devis.get_devis(self._devis())
		self.assertEqual(devis["status"], "Draft")
		self.assertEqual(devis["lignes"][0]["prix"], 450)
		self.assertEqual(devis["total"], 4500)
		self.assertTrue(devis["taxes"])
		self.assertGreater(devis["total_ttc"], devis["total"])
		self.assertIn("valider", devis["actions"])
		self.assertEqual(devis["blocked"], [])

	def test_creation_refusee(self):
		for values in (
			{"client": ""},
			{"lignes": []},
			{"lignes": [{"article": self.avec_prix, "quantite": 0}]},
			{"valable": add_days(today(), -1)},
			{"taxes": "Modèle inconnu"},
		):
			with self.subTest(values=values), self.assertRaises(frappe.ValidationError):
				self._devis(**values)

	def test_ligne_sans_prix_bloque_la_validation(self):
		name = self._devis(lignes=[{"article": self.sans_prix, "quantite": 2}])
		devis = bureau_devis.get_devis(name)
		self.assertEqual(devis["blocked"], ["1 ligne(s) sans prix."])
		with self.assertRaises(frappe.ValidationError):
			bureau_devis.validate_devis(name, devis["modified"])
		devis = bureau_devis.update_devis(
			name,
			devis["modified"],
			json.dumps({"lignes": [{"article": self.sans_prix, "quantite": 2, "prix": 120}]}),
		)
		self.assertEqual((devis["total"], devis["blocked"]), (240, []))

	def test_cycle_valide_commande(self):
		name = self._devis()
		devis = bureau_devis.validate_devis(name, bureau_devis.get_devis(name)["modified"])
		self.assertEqual(devis["status"], "Open")
		self.assertIn("commande", devis["actions"])
		with self.assertRaises(frappe.PermissionError):
			bureau_devis.update_devis(name, devis["modified"], json.dumps({"valable": add_days(today(), 40)}))
		result = bureau_devis.create_commande(name, devis["modified"], add_days(today(), 10))
		commande = frappe.get_doc("Sales Order", result["commande"])
		self.assertEqual((commande.docstatus, commande.customer), (0, self.client))
		self.assertEqual([row["name"] for row in result["devis"]["commandes"]], [commande.name])

	def test_perdu_annule_supprime(self):
		reason = (
			frappe.db.get_value("Quotation Lost Reason", {}, "name")
			or frappe.get_doc({"doctype": "Quotation Lost Reason", "order_lost_reason": "Prix trop élevé"})
			.insert()
			.name
		)
		name = self._devis()
		devis = bureau_devis.validate_devis(name, bureau_devis.get_devis(name)["modified"])
		devis = bureau_devis.mark_lost(name, devis["modified"], reason, "Concurrent moins cher")
		self.assertEqual((devis["status"], devis["perte"]["raisons"]), ("Lost", [reason]))
		autre = self._devis()
		devis = bureau_devis.validate_devis(autre, bureau_devis.get_devis(autre)["modified"])
		self.assertEqual(bureau_devis.cancel_devis(autre, devis["modified"])["status"], "Cancelled")
		brouillon = self._devis()
		bureau_devis.delete_devis(brouillon, bureau_devis.get_devis(brouillon)["modified"])
		self.assertFalse(frappe.db.exists("Quotation", brouillon))

	def test_liste_vues_et_groupe(self):
		name = self._devis()
		response = bureau_devis.get_devis_list(page_length=500)
		self.assertIn(name, response["names"])
		self.assertEqual(response["counts"]["all"], response["total"])
		row = next(row for row in response["devis"] if row["name"] == name)
		self.assertEqual((row["status"], row["lignes"]), ("Draft", 1))
		self.assertTrue(bureau_devis.in_view("expirent", {"status": "Open", "valable": add_days(today(), 3)}))
		self.assertFalse(
			bureau_devis.in_view("expirent", {"status": "Draft", "valable": add_days(today(), 3)})
		)
		doc = frappe.get_doc("Quotation", name)
		self.assertIsNone(bureau_devis.bulk_guard(doc, "update"))
		doc.docstatus = 1
		self.assertTrue(bureau_devis.bulk_guard(doc, "update"))
		self.assertIn("Quotation", bureau_bulk.BULK_DOCTYPES)
		articles = bureau_devis.search_devis_articles("essai devis")
		self.assertEqual({row["name"]: row["prix"] for row in articles}[self.avec_prix], 450)
