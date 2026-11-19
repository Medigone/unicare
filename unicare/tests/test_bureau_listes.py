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
		self.assertEqual(
			[row["code"] for row in listes], ["raisons", "clients", "fournisseurs", "articles", "unites"]
		)
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


def _article_dans(groupe, nom):
	return (
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": nom,
				"item_name": nom,
				"item_group": groupe,
				"stock_uom": frappe.db.get_value("UOM", {"enabled": 1}, "name"),
				"custom_type_conditionnement": "Autre",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


class TestFusion(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_resume_par_module_avec_lien(self):
		listes = {row["code"]: row for row in L.get_listes()}
		self.assertEqual(listes["clients"]["module"], "ventes")
		self.assertEqual(listes["unites"]["module"], "stock")
		self.assertEqual(listes["clients"]["lien"]["page"], "Clients")
		self.assertTrue(listes["clients"]["fusion"])
		self.assertFalse(listes["unites"]["fusion"])
		self.assertIsInstance(listes["articles"]["inutilisees"], int)

	def test_cle_des_doublons(self):
		self.assertEqual(L._cle("Pharmacies"), L._cle("pharmacie"))
		self.assertEqual(L._cle("Hôpitaux"), L._cle("hopitau"))
		self.assertEqual(L._cle("Prix  trop élevé !"), L._cle("prix trop eleve"))
		self.assertNotEqual(L._cle("Clinique"), L._cle("Cliniques privées"))

	def test_doublons_et_fusion_d_un_groupe(self):
		L.create_valeur("articles", "Essai liste Flacons")
		L.create_valeur("articles", "Essai liste flacon")
		article = _article_dans("Essai liste Flacons", "Essai liste article fusion")
		paires = [row for row in L.get_doublons("articles") if row["cible"].startswith("Essai liste")]
		self.assertEqual(
			paires, [{"source": "Essai liste flacon", "cible": "Essai liste Flacons", "usages": 0}]
		)
		fiches = L.get_fiches("articles", "Essai liste Flacons")
		self.assertEqual((fiches["total"], fiches["fiches"][0]["name"]), (1, article))
		row = _valeur(L.get_valeurs("articles"), "Essai liste Flacons")
		self.assertEqual(row["detail"], {"articles": 1})
		valeurs = L.fusionner("articles", row["name"], row["modified"], "Essai liste flacon")
		self.assertIsNone(_valeur(valeurs, "Essai liste Flacons"))
		self.assertEqual(_valeur(valeurs, "Essai liste flacon")["usages"], 1)
		self.assertEqual(frappe.db.get_value("Item", article, "item_group"), "Essai liste flacon")

	def test_fusion_d_une_raison_de_perte(self):
		L.create_valeur("raisons", "Essai liste trop cher")
		L.create_valeur("raisons", "Essai liste prix")
		row = _valeur(L.get_valeurs("raisons"), "Essai liste trop cher")
		valeurs = L.fusionner("raisons", row["name"], row["modified"], "Essai liste prix")
		self.assertIsNone(_valeur(valeurs, "Essai liste trop cher"))
		self.assertIsNotNone(_valeur(valeurs, "Essai liste prix"))

	def test_fusions_refusees(self):
		row = _valeur(L.create_valeur("articles", "Essai liste seul"), "Essai liste seul")
		with self.assertRaises(frappe.ValidationError):
			L.fusionner("articles", row["name"], row["modified"], row["name"])
		with self.assertRaises(frappe.ValidationError):
			L.fusionner("articles", row["name"], row["modified"], L._racine("articles"))
		with self.assertRaises(frappe.ValidationError):
			L.fusionner("articles", row["name"], row["modified"], "Essai liste inexistant")
		unite = _valeur(L.create_valeur("unites", "Essai liste bidon"), "Essai liste bidon")
		with self.assertRaises(frappe.ValidationError):
			L.fusionner("unites", unite["name"], unite["modified"], "Nos")
		self.assertEqual(L.get_doublons("unites"), [])


class TestArbre(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_dossiers_et_rangement(self):
		listes = {row["code"]: row for row in L.get_listes()}
		self.assertTrue(listes["articles"]["arbre"])
		self.assertFalse(listes["unites"]["arbre"])
		L.create_valeur("articles", "Essai arbre Emballages", est_dossier=1)
		L.create_valeur("articles", "Essai arbre Matières", est_dossier=1)
		valeurs = L.create_valeur("articles", "Essai arbre Flacons", dossier="Essai arbre Emballages")
		flacons = _valeur(valeurs, "Essai arbre Flacons")
		self.assertEqual((flacons["dossier"], flacons["parent"]), (False, "Essai arbre Emballages"))
		self.assertTrue(_valeur(valeurs, "Essai arbre Emballages")["dossier"])
		self.assertIsNone(_valeur(valeurs, "Essai arbre Emballages")["parent"])
		self.assertIsNone(_valeur(valeurs, L._racine("articles")))
		with self.assertRaises(frappe.ValidationError):
			L.create_valeur("articles", "Essai arbre refus", dossier="Essai arbre Flacons")

		valeurs = L.deplacer("articles", flacons["name"], flacons["modified"], "Essai arbre Matières")
		flacons = _valeur(valeurs, "Essai arbre Flacons")
		self.assertEqual(flacons["parent"], "Essai arbre Matières")
		valeurs = L.deplacer("articles", flacons["name"], flacons["modified"], None)
		self.assertIsNone(_valeur(valeurs, "Essai arbre Flacons")["parent"])

	def test_dossier_dans_son_sous_dossier_refuse(self):
		L.create_valeur("articles", "Essai arbre A", est_dossier=1)
		valeurs = L.create_valeur("articles", "Essai arbre B", dossier="Essai arbre A", est_dossier=1)
		a = _valeur(valeurs, "Essai arbre A")
		with self.assertRaises(frappe.ValidationError):
			L.deplacer("articles", a["name"], a["modified"], "Essai arbre B")
		with self.assertRaises(frappe.ValidationError):
			L.deplacer("articles", a["name"], a["modified"], "Essai arbre A")

	def test_supprimer_et_fusionner_un_dossier(self):
		L.create_valeur("articles", "Essai arbre plein", est_dossier=1)
		valeurs = L.create_valeur("articles", "Essai arbre dedans", dossier="Essai arbre plein")
		plein = _valeur(valeurs, "Essai arbre plein")
		with self.assertRaises(frappe.ValidationError):
			L.delete_valeur("articles", plein["name"], plein["modified"])
		with self.assertRaises(frappe.ValidationError):
			L.fusionner("articles", plein["name"], plein["modified"], "Essai arbre dedans")
		dedans = _valeur(valeurs, "Essai arbre dedans")
		with self.assertRaises(frappe.ValidationError):
			L.fusionner("articles", dedans["name"], dedans["modified"], "Essai arbre plein")
		valeurs = L.delete_valeur("articles", dedans["name"], dedans["modified"])
		plein = _valeur(valeurs, "Essai arbre plein")
		valeurs = L.rename_valeur("articles", plein["name"], plein["modified"], "Essai arbre vide")
		vide = _valeur(valeurs, "Essai arbre vide")
		self.assertTrue(vide["dossier"])
		valeurs = L.delete_valeur("articles", vide["name"], vide["modified"])
		self.assertIsNone(_valeur(valeurs, "Essai arbre vide"))
