# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_articles, bureau_contacts, bureau_fournisseurs
from unicare.tests.achats_outils import article, fournisseur


class TestContactsEtCodesBarres(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_contacts_du_fournisseur(self):
		tiers = fournisseur("Fournisseur essai contacts")
		premier = bureau_contacts.save_contact("Supplier", tiers, values=json.dumps({"prenom": "Nadia", "nom": "Saadi", "fonction": "Commerciale", "telephone": "0550 11 22 33", "email": "nadia@example.com", "principal": 1}))["name"]
		second = bureau_contacts.save_contact("Supplier", tiers, values=json.dumps({"prenom": "Karim"}))["name"]
		fiche = bureau_fournisseurs.get_fournisseur(tiers)
		self.assertEqual(fiche["contacts"][0]["name"], premier)
		self.assertEqual((fiche["contacts"][0]["nom"], fiche["contacts"][0]["telephone"], fiche["contacts"][0]["email"]), ("Nadia Saadi", "0550 11 22 33", "nadia@example.com"))
		self.assertEqual(frappe.db.get_value("Supplier", tiers, "supplier_primary_contact"), premier)

		bureau_contacts.save_contact("Supplier", tiers, second, json.dumps({"prenom": "Karim", "nom": "B.", "principal": 1}))
		self.assertEqual(frappe.db.get_value("Supplier", tiers, "supplier_primary_contact"), second)
		self.assertFalse(frappe.db.get_value("Contact", premier, "is_primary_contact"))
		with self.assertRaises(frappe.ValidationError):
			bureau_contacts.save_contact("Supplier", tiers, values=json.dumps({"prenom": "X", "email": "pas-un-email"}))
		autre = fournisseur("Autre fournisseur essai contacts")
		with self.assertRaises(frappe.PermissionError):
			bureau_contacts.delete_contact("Supplier", autre, premier)
		bureau_contacts.delete_contact("Supplier", tiers, premier)
		self.assertFalse(frappe.db.exists("Contact", premier))

	def test_codes_barres(self):
		code = article("Article essai codes-barres")
		fiche = bureau_articles.get_article(code, full=1)
		fiche = bureau_articles.set_barcodes(code, fiche["modified"], json.dumps(["2001234567893", " ", "2001234567893", "2001234567800"]))
		self.assertEqual(fiche["barcodes"], ["2001234567893", "2001234567800"])
		autre = article("Autre article essai codes-barres")
		with self.assertRaises(frappe.ValidationError):
			bureau_articles.set_barcodes(autre, bureau_articles.get_article(autre, full=1)["modified"], json.dumps(["2001234567893"]))
