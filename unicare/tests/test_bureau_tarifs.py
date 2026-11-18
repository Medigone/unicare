# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_achats, bureau_devis
from unicare.api import bureau_tarifs as T


def _article(nom, vendu=1, achete=1):
	"""Un article d'essai, retrouvé par sa désignation : son code suit le type (AU-…)."""
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
				"is_sales_item": vendu,
				"is_purchase_item": achete,
				"custom_type_conditionnement": "Autre",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _tarif(nom, sens):
	if not frappe.db.exists("Price List", nom):
		T.create_tarif(nom, sens)
	return nom


class TestTarifs(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.vente = _tarif("Tarif essai vente", "vente")
		self.achat = _tarif("Tarif essai achat", "achat")
		self.article = _article("Essai tarif zircon")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _ligne(self, liste, search="Essai tarif zircon"):
		return next(row for row in T.get_prix(liste, search)["lignes"] if row["article"] == self.article)

	def test_poser_changer_retirer_un_prix(self):
		ligne = self._ligne(self.vente)
		self.assertIsNone(ligne["prix"])
		ligne = T.set_prix(self.vente, self.article, "1 250,50")
		self.assertEqual(ligne["prix"], 1250.5)
		self.assertEqual(ligne["unite_prix"], frappe.db.get_value("Item", self.article, "stock_uom"))
		ligne = T.set_prix(self.vente, self.article, "1300", ligne["modified"])
		self.assertEqual(self._ligne(self.vente)["prix"], 1300)
		ligne = T.set_prix(self.vente, self.article, "", ligne["modified"])
		self.assertIsNone(ligne["prix"])
		self.assertFalse(
			frappe.db.exists("Item Price", {"price_list": self.vente, "item_code": self.article})
		)

	def test_prix_refuses(self):
		for prix in ("0", "-5", "abc"):
			with self.assertRaises(frappe.ValidationError):
				T.set_prix(self.vente, self.article, prix)
		ligne = T.set_prix(self.vente, self.article, "100")
		with self.assertRaises(frappe.TimestampMismatchError):
			T.set_prix(self.vente, self.article, "200", "2000-01-01 00:00:00")
		with self.assertRaises(frappe.TimestampMismatchError):
			T.set_prix(self.vente, self.article, "200")
		self.assertEqual(self._ligne(self.vente)["prix"], ligne["prix"])

	def test_vues_et_sens(self):
		seulement_vendu = _article("Essai tarif zircon vendu", vendu=1, achete=0)
		T.set_prix(self.vente, self.article, "100")
		reponse = T.get_prix(self.vente, "Essai tarif zircon", "sans_prix")
		self.assertEqual([row["article"] for row in reponse["lignes"]], [seulement_vendu])
		self.assertEqual(reponse["compte"], {"tous": 2, "sans_prix": 1, "avec_prix": 1})
		self.assertEqual(
			[row["article"] for row in T.get_prix(self.achat, "Essai tarif zircon")["lignes"]], [self.article]
		)
		with self.assertRaises(frappe.ValidationError):
			T.get_prix(self.vente, vue="inconnue")

	def test_la_ligne_modifiee_est_celle_que_lisent_les_pieces(self):
		uom = frappe.db.get_value("Item", self.article, "stock_uom")
		for rate, debut, fin in ((10, "2026-01-01", "2026-05-31"), (20, "2026-06-01", None)):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"price_list": self.vente,
					"item_code": self.article,
					"uom": uom,
					"price_list_rate": rate,
					"valid_from": debut,
					"valid_upto": fin,
				}
			).insert()
		ligne = self._ligne(self.vente)
		self.assertEqual(ligne["prix"], 20)
		T.set_prix(self.vente, self.article, "25", ligne["modified"])
		with patch.object(bureau_devis, "_price_list", return_value=self.vente):
			self.assertEqual(bureau_devis._prices([self.article])[self.article], 25)

	def test_tarif_par_defaut(self):
		T.set_prix(self.achat, self.article, "40")
		reglages = T.set_tarif_defaut("achat", self.achat)
		self.assertEqual(reglages["defauts"]["achat"], self.achat)
		self.assertEqual(bureau_achats.buying_price_list(), self.achat)
		self.assertEqual(bureau_achats.buying_prices([self.article])[self.article], 40)
		T.set_tarif_defaut("vente", self.vente)
		self.assertEqual(bureau_devis._price_list(), self.vente)
		with self.assertRaises(frappe.ValidationError):
			T.set_tarif_defaut("vente", self.achat)

	def test_creation_de_tarif(self):
		with self.assertRaises(frappe.ValidationError):
			T.create_tarif(self.vente, "vente")
		with self.assertRaises(frappe.ValidationError):
			T.create_tarif("  ", "vente")
		with self.assertRaises(frappe.ValidationError):
			T.create_tarif("Tarif essai autre", "location")
		tarifs = T.create_tarif("Tarif essai revendeurs", "vente")
		row = next(row for row in tarifs["tarifs"] if row["name"] == "Tarif essai revendeurs")
		self.assertEqual((row["sens"], row["prix"], row["defaut"]), ("vente", 0, False))

	def test_fiche_article(self):
		with (
			patch.object(T, "_price_list", return_value=self.vente),
			patch.object(T, "buying_price_list", return_value=self.achat),
		):
			T.set_prix(self.vente, self.article, "90")
			prix = T.prix_article(self.article)
		self.assertEqual(prix["vente"], {"tarif": self.vente, "prix": 90, "concerne": True})
		self.assertIsNone(prix["achat"]["prix"])

	def test_sans_droit(self):
		def refus(*args, throw=False, **kwargs):
			if throw:
				frappe.throw("Refusé", frappe.PermissionError)
			return False

		with patch("frappe.has_permission", side_effect=refus):
			self.assertIsNone(T.prix_article(self.article))
			with self.assertRaises(frappe.PermissionError):
				T.get_tarifs()
