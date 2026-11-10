# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_articles, bureau_bulk


def _values(**extra):
	return {
		"type": "Conditionnement",
		"designation": "Flacon essai bureau 250 ml",
		"groupe": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
		"uom": frappe.db.get_value("UOM", {"enabled": 1}, "name"),
		**extra,
	}


class TestListeArticles(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_vues(self):
		self.assertTrue(bureau_articles.VIEWS["fut"]({"type": "Fût", "disabled": 0}))
		self.assertFalse(bureau_articles.VIEWS["fut"]({"type": "Fût", "disabled": 1}))
		self.assertFalse(bureau_articles.VIEWS["all"]({"type": "Autre", "disabled": 1}))
		self.assertTrue(bureau_articles.VIEWS["desactive"]({"type": "Autre", "disabled": 1}))

	def test_liste_et_compteurs(self):
		response = bureau_articles.get_articles(page_length=500)
		self.assertEqual(response["counts"]["all"], response["total"])
		self.assertEqual(
			response["counts"]["all"],
			sum(response["counts"][key] for key in bureau_articles.TYPE_VIEWS)
			+ sum(1 for row in response["articles"] if not row["type"]),
		)
		with self.assertRaises(frappe.ValidationError):
			bureau_articles.get_articles(view="inconnue")

	def test_tri_et_stock_sans_droit(self):
		rows = [
			{"designation": "b", "stock": 2},
			{"designation": "A", "stock": None},
			{"designation": "c", "stock": 10},
		]
		ordered = bureau_articles.order_articles(rows, "stock", "desc")
		self.assertEqual([row["designation"] for row in ordered], ["c", "b", "A"])
		with patch.object(bureau_articles, "_readable", return_value=False):
			self.assertIsNone(bureau_articles._stocks())
			response = bureau_articles.get_articles()
		self.assertTrue(all(row["stock"] is None for row in response["articles"]))

	def test_options(self):
		options = bureau_articles.get_article_options()
		self.assertEqual(options["types"], ["Fût", "Conditionnement", "Produit fini", "Autre"])
		fields = {entry["field"] for entry in options["filter_fields"]}
		self.assertTrue({"custom_type_conditionnement", "item_group"} <= fields)


class TestFicheArticle(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_creation_code_par_type_et_lots_forces(self):
		name = bureau_articles.create_article(
			json.dumps(
				_values(
					type="Produit fini", has_batch_no=0, shelf_life_in_days="730", barcode="6130000000017"
				)
			)
		)["name"]
		doc = frappe.get_doc("Item", name)
		self.assertTrue(name.startswith("PF-"))
		self.assertEqual((doc.has_batch_no, doc.is_stock_item, doc.shelf_life_in_days), (1, 1, 730))
		self.assertEqual(doc.barcodes[0].barcode, "6130000000017")
		self.assertTrue(
			bureau_articles.create_article(json.dumps(_values(designation="Autre essai")))["name"].startswith(
				"CO-"
			)
		)

	def test_creation_refusee(self):
		with self.assertRaises(frappe.ValidationError):
			bureau_articles.create_article(json.dumps(_values(type="")))
		with self.assertRaises(frappe.ValidationError):
			bureau_articles.create_article(json.dumps(_values(type="Inventé")))
		with self.assertRaises(frappe.ValidationError):
			bureau_articles.create_article(json.dumps(_values(uom="Unité inconnue")))
		bureau_articles.create_article(json.dumps(_values()))
		with self.assertRaises(frappe.ValidationError):
			bureau_articles.create_article(json.dumps(_values()))

	def test_modification_et_fiche(self):
		name = bureau_articles.create_article(json.dumps(_values()))["name"]
		self.assertNotIn("recettes", bureau_articles.get_article(name))
		doc = frappe.get_doc("Item", name)
		updated = bureau_articles.update_article(
			name,
			str(doc.modified),
			json.dumps({"designation": "Flacon renommé", "type": "Fût", "disabled": "1"}),
		)
		self.assertEqual(
			(updated["designation"], updated["type"], updated["disabled"]),
			("Flacon renommé", "Conditionnement", 1),
		)
		self.assertEqual(set(updated["recettes"]), {"produit", "ingredient"})
		self.assertEqual(set(updated["mouvements"]), {key for key, *_rest in bureau_articles.MOUVEMENTS})
		self.assertIsNone(updated["lots"])
		with self.assertRaises(frappe.TimestampMismatchError):
			bureau_articles.update_article(name, str(doc.modified), json.dumps({"designation": "x"}))
		feed = bureau_articles.add_article_comment(name, "Nouveau fournisseur")
		self.assertEqual(feed["comment_count"], 1)

	def test_actions_groupees_et_doublons(self):
		self.assertIn("Item", bureau_bulk.BULK_DOCTYPES)
		name = bureau_articles.create_article(json.dumps(_values()))["name"]
		found = bureau_articles.search_articles("essai bureau")
		self.assertIn(name, [row["name"] for row in found])
		self.assertEqual(bureau_articles.search_articles(" "), [])
