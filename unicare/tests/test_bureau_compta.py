# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_compta as C


def _point(reponse, code):
	return next(row for row in reponse["bilan"] if row["code"] == code)


class TestCompta(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = C._societe()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_lecture(self):
		reponse = C.get_compta()
		self.assertEqual(reponse["societe"]["name"], self.company)
		codes = [row["code"] for row in reponse["bilan"]]
		self.assertEqual(
			codes, ["exercice", "plan", "comptes", "tva_vente", "tva_achat", "modes", "timbre", "tarifs"]
		)
		for row in reponse["bilan"]:
			self.assertIn(row["etat"], ("ok", "attention", "manque"))
		clients = reponse["comptes"]["options"]["default_receivable_account"]
		self.assertTrue(clients)
		for compte in clients:
			self.assertEqual(frappe.db.get_value("Account", compte, "account_type"), "Receivable")

	def test_comptes_par_defaut(self):
		reponse = C.get_compta()
		caisses = reponse["comptes"]["options"]["default_cash_account"]
		reponse = C.save_comptes(reponse["societe"]["modified"], {"default_cash_account": caisses[-1]})
		self.assertEqual(frappe.db.get_value("Company", self.company, "default_cash_account"), caisses[-1])
		with self.assertRaises(frappe.TimestampMismatchError):
			C.save_comptes("2000-01-01 00:00:00", {"default_cash_account": caisses[0]})
		modified = reponse["societe"]["modified"]
		with self.assertRaises(frappe.ValidationError):
			C.save_comptes(modified, {"default_receivable_account": ""})
		banque = reponse["comptes"]["options"]["default_bank_account"][0]
		with self.assertRaises(frappe.ValidationError):
			C.save_comptes(modified, {"default_receivable_account": banque})

	def test_tva(self):
		reponse = C.create_tva("vente", "13,5")
		taux = next(row for row in reponse["tva"]["vente"] if row["titre"] == "TVA 13,5%")
		self.assertEqual((taux["taux"], taux["defaut"], taux["actif"]), (13.5, False, True))
		self.assertTrue(taux["compte"].startswith("44571"))
		with self.assertRaises(frappe.ValidationError):
			C.create_tva("vente", "13,5")
		with self.assertRaises(frappe.ValidationError):
			C.create_tva("vente", "abc")

		ancien = next(row for row in reponse["tva"]["vente"] if row["defaut"])
		reponse = C.set_tva("vente", taux["name"], taux["modified"], "defaut")
		defauts = [row["name"] for row in reponse["tva"]["vente"] if row["defaut"]]
		self.assertEqual(defauts, [taux["name"]])
		self.assertEqual(_point(reponse, "tva_vente")["etat"], "ok")
		taux = next(row for row in reponse["tva"]["vente"] if row["name"] == taux["name"])
		with self.assertRaises(frappe.ValidationError):
			C.set_tva("vente", taux["name"], taux["modified"], "desactiver")
		ancien = next(row for row in reponse["tva"]["vente"] if row["name"] == ancien["name"])
		reponse = C.set_tva("vente", ancien["name"], ancien["modified"], "desactiver")
		self.assertFalse(
			next(row for row in reponse["tva"]["vente"] if row["name"] == ancien["name"])["actif"]
		)

		reponse = C.create_tva("achat", "13,5")
		self.assertTrue(any(row["titre"] == "TVA déductible 13,5%" for row in reponse["tva"]["achat"]))

	def test_modes_de_paiement(self):
		reponse = C.get_compta()
		banque = next(
			c
			for c in reponse["comptes_tresorerie"]
			if frappe.db.get_value("Account", c, "account_type") == "Bank"
		)
		reponse = C.save_mode(values={"nom": "Essai compta mode", "type": "Bank", "compte": banque})
		mode = next(row for row in reponse["modes"] if row["name"] == "Essai compta mode")
		self.assertEqual((mode["type"], mode["compte"], mode["actif"]), ("Bank", banque, True))
		reponse = C.save_mode(mode["name"], mode["modified"], {"type": "Bank", "compte": "", "actif": False})
		mode = next(row for row in reponse["modes"] if row["name"] == "Essai compta mode")
		self.assertEqual((mode["compte"], mode["actif"]), (None, False))
		with self.assertRaises(frappe.ValidationError):
			C.save_mode(
				mode["name"],
				mode["modified"],
				{"type": "Bank", "compte": reponse["comptes"]["options"]["default_receivable_account"][0]},
			)
		with self.assertRaises(frappe.ValidationError):
			C.save_mode(values={"nom": "Essai compta mode", "type": "Bank"})

	def test_bilan_modes_sans_compte(self):
		reponse = C.save_mode(values={"nom": "Essai compta repli", "type": "Bank"})
		point = _point(reponse, "modes")
		self.assertIn(point["etat"], ("attention", "manque"))
		self.assertIn("Essai compta repli", point["detail"])

	def test_exercice_suivant(self):
		exercices = C._exercices(self.company)
		suivant = C._suivant(exercices)
		if frappe.db.exists("Fiscal Year", suivant["name"]):
			self.skipTest("exercice suivant déjà créé")
		with patch.object(C, "today", return_value=exercices[0]["fin"]):
			self.assertEqual(_point(C.get_compta(), "exercice")["etat"], "attention")
			reponse = C.create_exercice()
			self.assertEqual(reponse["exercices"][0]["name"], suivant["name"])
			self.assertEqual(_point(reponse, "exercice")["etat"], "ok")
			self.assertEqual(C._suivant(reponse["exercices"])["debut"], f"{int(suivant['name']) + 1}-01-01")

	def test_sans_droit(self):
		def refus(*args, throw=False, **kwargs):
			if throw:
				frappe.throw("Refusé", frappe.PermissionError)
			return False

		with patch("frappe.has_permission", side_effect=refus):
			with self.assertRaises(frappe.PermissionError):
				C.get_compta()
			with self.assertRaises(frappe.PermissionError):
				C.create_exercice()


class TestSuppressionMode(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _mode(self, reponse, nom):
		return next((row for row in reponse["modes"] if row["name"] == nom), None)

	def test_supprimer_un_mode_jamais_utilise(self):
		reponse = C.save_mode(values={"nom": "Essai compta jetable", "type": "Cash"})
		mode = self._mode(reponse, "Essai compta jetable")
		self.assertEqual(mode["usages"], 0)
		with self.assertRaises(frappe.TimestampMismatchError):
			C.delete_mode(mode["name"], "2000-01-01 00:00:00")
		reponse = C.delete_mode(mode["name"], mode["modified"])
		self.assertIsNone(self._mode(reponse, "Essai compta jetable"))
		self.assertTrue(C.get_compta()["droits"]["modes_supprimer"])

	def test_un_mode_utilise_ne_se_supprime_pas(self):
		reponse = C.save_mode(values={"nom": "Essai compta servi", "type": "Cash"})
		mode = self._mode(reponse, "Essai compta servi")
		with patch.object(C, "_usages_modes", return_value={"Essai compta servi": 3}):
			self.assertEqual(self._mode(C.get_compta(), "Essai compta servi")["usages"], 3)
			with self.assertRaises(frappe.ValidationError):
				C.delete_mode(mode["name"], mode["modified"])
		self.assertTrue(frappe.db.exists("Mode of Payment", "Essai compta servi"))
