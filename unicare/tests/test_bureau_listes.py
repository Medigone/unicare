# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_listes as L


def _valeur(valeurs, nom):
	return next((row for row in valeurs if row["name"] == nom), None)


class TestListes(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_resume(self):
		listes = L.get_listes()
		self.assertEqual([row["code"] for row in listes], ["raisons", "clients", "fournisseurs", "articles", "unites"])
		self.assertTrue(all(row["droits"]["creer"] for row in listes))

	def test_creer_renommer_supprimer(self):
		for code in ("raisons", "clients", "fournisseurs", "articles", "unites"):
			valeurs = L.create_valeur(code, f"Essai liste {code}")
			row = _valeur(valeurs, f"Essai liste {code}")
			self.assertEqual(row["usages"], 0)
			with self.assertRaises(frappe.ValidationError):
				L.create_valeur(code, f"Essai liste {code}")
			valeurs = L.rename_valeur(code, row["name"], row["modified"], f"Essai liste {code} bis")
			row = _valeur(valeurs, f"Essai liste {code} bis")
			self.assertIsNotNone(row, code)
			self.assertIsNone(_valeur(valeurs, f"Essai liste {code}"))
			valeurs = L.delete_valeur(code, row["name"], row["modified"])
			self.assertIsNone(_valeur(valeurs, row["name"]))

	def test_groupe_cree_sous_la_racine(self):
		L.create_valeur("clients", "Essai liste pharmacies")
		doc = frappe.get_doc("Customer Group", "Essai liste pharmacies")
		self.assertEqual((doc.is_group, doc.parent_customer_group), (0, L._racine("clients")))
		racine = frappe.get_doc("Customer Group", L._racine("clients"))
		with self.assertRaises(frappe.ValidationError):
			L.delete_valeur("clients", racine.name, str(racine.modified))

	def test_valeur_utilisee(self):
		valeurs = L.get_valeurs("articles")
		utilise = next((row for row in valeurs if row["usages"]), None)
		if not utilise:
			self.skipTest("aucun groupe utilisé")
		with self.assertRaises(frappe.ValidationError):
			L.delete_valeur("articles", utilise["name"], utilise["modified"])
		with self.assertRaises(frappe.TimestampMismatchError):
			L.rename_valeur("articles", utilise["name"], "2000-01-01 00:00:00", "Autre nom")

	def test_unites(self):
		valeurs = L.create_valeur("unites", "Essai liste flacon")
		row = _valeur(valeurs, "Essai liste flacon")
		valeurs = L.set_unite(row["name"], row["modified"], entier=1)
		row = _valeur(valeurs, "Essai liste flacon")
		self.assertTrue(row["entier"])
		reponse = L.desactiver_unites_inutilisees()
		self.assertGreaterEqual(reponse["desactivees"], 1)
		self.assertFalse(_valeur(reponse["valeurs"], "Essai liste flacon")["actif"])
		defaut = frappe.db.get_single_value("Stock Settings", "stock_uom")
		if defaut:
			self.assertTrue(_valeur(reponse["valeurs"], defaut)["actif"])
		for row in reponse["valeurs"]:
			if row["usages"]:
				self.assertTrue(row["actif"], row["name"])

	def test_sans_droit(self):
		def refus(*args, throw=False, **kwargs):
			if throw:
				frappe.throw("Refusé", frappe.PermissionError)
			return False

		with patch("frappe.has_permission", side_effect=refus):
			with self.assertRaises(frappe.PermissionError):
				L.get_listes()
			with self.assertRaises(frappe.PermissionError):
				L.create_valeur("raisons", "Essai refus")
