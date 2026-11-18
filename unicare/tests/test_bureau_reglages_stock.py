# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_reglages_stock as S
from unicare.api.bureau_stock import depots


def _article(nom):
	existing = frappe.db.get_value("Item", {"item_name": nom}, "name")
	if existing:
		return existing
	return (
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": nom,
				"item_name": nom,
				"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
				"stock_uom": frappe.db.get_value("UOM", {"enabled": 1}, "name"),
				"is_stock_item": 1,
				"custom_type_conditionnement": "Autre",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


class TestReglagesStock(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.depot = depots()[0]
		self.article = _article("Essai seuil quartz")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _ligne(self):
		return next(row for row in S.get_seuils(self.depot, "Essai seuil quartz")["lignes"] if row["article"] == self.article)

	def test_poser_changer_retirer_un_seuil(self):
		ligne = self._ligne()
		self.assertIsNone(ligne["seuil"])
		ligne = S.set_seuil(self.depot, self.article, ligne["modified"], "10")
		self.assertEqual((ligne["seuil"], ligne["quantite"]), (10, 10))
		ligne = S.set_seuil(self.depot, self.article, ligne["modified"], "12,5", "50")
		self.assertEqual((ligne["seuil"], ligne["quantite"]), (12.5, 50))
		reponse = S.get_seuils(self.depot, "Essai seuil quartz", "sous_seuil")
		self.assertEqual([row["article"] for row in reponse["lignes"]], [self.article])
		self.assertEqual(reponse["compte"], {"tous": 1, "avec_seuil": 1, "sous_seuil": 1})
		ligne = S.set_seuil(self.depot, self.article, ligne["modified"], "")
		self.assertIsNone(ligne["seuil"])
		self.assertFalse(frappe.db.exists("Item Reorder", {"parent": self.article}))

	def test_refus(self):
		ligne = self._ligne()
		with self.assertRaises(frappe.ValidationError):
			S.set_seuil(self.depot, self.article, ligne["modified"], "-1")
		with self.assertRaises(frappe.ValidationError):
			S.set_seuil(self.depot, self.article, ligne["modified"], "abc")
		with self.assertRaises(frappe.ValidationError):
			S.set_seuil("Dépôt inexistant", self.article, ligne["modified"], "5")
		with self.assertRaises(frappe.TimestampMismatchError):
			S.set_seuil(self.depot, self.article, "2000-01-01 00:00:00", "5")
		with self.assertRaises(frappe.ValidationError):
			S.get_seuils(self.depot, vue="inconnue")

	def test_parametres(self):
		reglages = S.get_reglages_stock()
		p = reglages["parametres"]
		autre = next(d for d in reglages["depots"] if d != p["default_warehouse"])
		reglages = S.save_parametres(
			p["modified"],
			{"default_warehouse": autre, "stock_uom": p["stock_uom"], "allow_negative_stock": False, "auto_indent": False},
		)
		self.assertEqual(reglages["parametres"]["default_warehouse"], autre)
		self.assertFalse(reglages["parametres"]["auto_indent"])
		from unicare.api.bureau_commandes_achat import _default_warehouse

		self.assertEqual(_default_warehouse(), autre)
		with self.assertRaises(frappe.TimestampMismatchError):
			S.save_parametres(p["modified"], {"default_warehouse": autre})
		with self.assertRaises(frappe.ValidationError):
			S.save_parametres(reglages["parametres"]["modified"], {"default_warehouse": "Dépôt inexistant"})

	def test_sans_droit(self):
		def refus(*args, throw=False, **kwargs):
			if throw:
				frappe.throw("Refusé", frappe.PermissionError)
			return False

		with patch("frappe.has_permission", side_effect=refus):
			with self.assertRaises(frappe.PermissionError):
				S.get_reglages_stock()
			with self.assertRaises(frappe.PermissionError):
				S.get_seuils(self.depot)
