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
		return next(
			row
			for row in S.get_seuils(self.depot, "Essai seuil quartz")["lignes"]
			if row["article"] == self.article
		)

	def test_poser_changer_retirer_un_seuil(self):
		ligne = self._ligne()
		self.assertIsNone(ligne["seuil"])
		ligne = S.set_seuil(self.depot, self.article, ligne["modified"], "10")
		self.assertEqual((ligne["seuil"], ligne["quantite"]), (10, 10))
		ligne = S.set_seuil(self.depot, self.article, ligne["modified"], "12,5", "50")
		self.assertEqual((ligne["seuil"], ligne["quantite"]), (12.5, 50))
		reponse = S.get_seuils(self.depot, "Essai seuil quartz", "sous_seuil")
		self.assertEqual([row["article"] for row in reponse["lignes"]], [self.article])
		self.assertEqual(reponse["compte"], {"tous": 1, "avec_seuil": 1, "sous_seuil": 1, "sans_seuil": 0})
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
			{
				"default_warehouse": autre,
				"stock_uom": p["stock_uom"],
				"allow_negative_stock": False,
				"auto_indent": False,
			},
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


class TestSeuilsParDepot(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.depot = depots()[0]
		self.article = _article("Essai seuil jaspe")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_resume_sans_seuil_et_a_commander(self):
		avant = S._resume_depots().get(self.depot, {"seuils": 0, "sous": 0})
		reponse = S.get_seuils(self.depot, "Essai seuil jaspe", "sans_seuil")
		self.assertEqual([row["article"] for row in reponse["lignes"]], [self.article])
		ligne = reponse["lignes"][0]
		S.set_seuil(self.depot, self.article, ligne["modified"], "10", "40")
		apres = S.get_reglages_stock()["resume"][self.depot]
		self.assertEqual((apres["seuils"], apres["sous"]), (avant["seuils"] + 1, avant["sous"] + 1))
		self.assertEqual(S.get_seuils(self.depot, "Essai seuil jaspe", "sans_seuil")["lignes"], [])
		a_commander = S.get_a_commander(self.depot)
		ligne = next(row for row in a_commander["lignes"] if row["article"] == self.article)
		self.assertEqual((ligne["seuil"], ligne["quantite"], ligne["stock"]), (10, 40, 0))

	def test_commande_preparee_dans_le_depot(self):
		from unicare.api import bureau_commandes_achat as C

		fournisseur = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		if not fournisseur or len(depots()) < 2:
			self.skipTest("Il faut un fournisseur et deux dépôts.")
		depot = depots()[1]
		nom = C.create_commande_achat(
			{
				"fournisseur": fournisseur,
				"reception": frappe.utils.add_days(frappe.utils.today(), 7),
				"depot": depot,
				"lignes": [{"article": self.article, "quantite": 5, "prix": 10}],
			}
		)["name"]
		doc = frappe.get_doc("Purchase Order", nom)
		self.assertEqual(doc.set_warehouse, depot)
		self.assertEqual({row.warehouse for row in doc.items}, {depot})
		with self.assertRaises(frappe.ValidationError):
			C.create_commande_achat({"fournisseur": fournisseur, "depot": "Dépôt inexistant", "lignes": []})


class TestDepots(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _noeud(self, label):
		return next((row for row in S.get_reglages_stock()["arbre"] if row["label"] == label), None)

	def test_creer_ranger_supprimer(self):
		from unicare.api import bureau_depots

		S.creer_dossier_depots("Essai dossier quai")
		dossier = self._noeud("Essai dossier quai")
		self.assertTrue(dossier["dossier"])
		self.assertIsNone(dossier["parent"])
		depot = bureau_depots.create_depot({"depot": "Essai dépôt quai"})["name"]
		noeud = self._noeud("Essai dépôt quai")
		S.deplacer_depot(depot, noeud["modified"], dossier["name"])
		self.assertEqual(self._noeud("Essai dépôt quai")["parent"], dossier["name"])
		with self.assertRaises(frappe.ValidationError):
			S.supprimer_dossier_depots(dossier["name"])
		with self.assertRaises(frappe.ValidationError):
			S.deplacer_depot(dossier["name"], self._noeud("Essai dossier quai")["modified"], dossier["name"])

		article = _article("Essai seuil onyx")
		ligne = next(
			row for row in S.get_seuils(depot, "Essai seuil onyx")["lignes"] if row["article"] == article
		)
		S.set_seuil(depot, article, ligne["modified"], "5")
		reglages = S.supprimer_depot(depot)
		self.assertNotIn(depot, reglages["depots"])
		self.assertFalse(frappe.db.exists("Item Reorder", {"parent": article}))
		S.supprimer_dossier_depots(dossier["name"])
		self.assertIsNone(self._noeud("Essai dossier quai"))

	def test_depot_par_defaut_protege(self):
		defaut = frappe.db.get_single_value("Stock Settings", "default_warehouse")
		if not defaut or defaut not in depots():
			self.skipTest("Pas de dépôt de réception par défaut.")
		with self.assertRaises(frappe.ValidationError):
			S.supprimer_depot(defaut)
