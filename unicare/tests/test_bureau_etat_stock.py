# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_articles, bureau_etat_stock

E = bureau_etat_stock


def _row(**values):
	return {"designation": "A", "depot": "D", "quantite": 0, "reserve": 0, "commande": 0, "projete": 0, "seuil": None, **values}


class TestEtatStock(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_vues(self):
		self.assertTrue(E.VIEWS["rupture"](_row(quantite=0)))
		self.assertTrue(E.VIEWS["negatif"](_row(quantite=-1)))
		self.assertTrue(E.VIEWS["sous_seuil"](_row(quantite=4, seuil=10)))
		self.assertFalse(E.VIEWS["sous_seuil"](_row(quantite=4, seuil=None)))
		self.assertTrue(E.VIEWS["reserve"](_row(quantite=4, reserve=1)))
		self.assertFalse(E._active(_row()))

	def test_ordre(self):
		rows = [_row(designation="b", quantite=5), _row(designation="A", quantite=50), _row(designation="c", quantite=1)]
		self.assertEqual([row["designation"] for row in E.order_lignes(rows)], ["A", "b", "c"])
		self.assertEqual([row["quantite"] for row in E.order_lignes(rows, "quantite", "desc")], [50, 5, 1])

	def test_liste_et_fiche(self):
		response = E.get_etat_stock(page_length=500)
		self.assertEqual(response["counts"]["all"], response["total"])
		self.assertAlmostEqual(response["valeur"], sum(row["valeur"] for row in response["lignes"]), places=2)
		if not response["names"]:
			return
		ligne = E.get_ligne_stock(response["names"][0], full=1)
		self.assertIsInstance(ligne["mouvements"], list)
		self.assertTrue(all(row["article"] == ligne["article"] and row["depot"] == ligne["depot"] for row in ligne["mouvements"]))
		recherche = E.get_etat_stock(search=ligne["article"], page_length=500)
		self.assertIn(ligne["name"], recherche["names"])
		with self.assertRaises(frappe.ValidationError):
			E.get_etat_stock(view="inconnue")

	def test_fiche_article_mene_aux_lignes(self):
		code = frappe.db.get_value("Bin", {"actual_qty": [">", 0]}, "item_code")
		if not code:
			return
		bins = bureau_articles.get_article(code, full=1)["bins"]
		self.assertTrue(all(frappe.db.exists("Bin", row["name"]) for row in bins))
