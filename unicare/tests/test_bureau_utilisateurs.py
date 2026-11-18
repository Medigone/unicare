# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_utilisateurs as U

EMAIL = "essai.utilisateur@example.com"
MDP = "Zircon-Quartz-2026!"


def _compte(reponse, name=EMAIL):
	return next((row for row in reponse["utilisateurs"] if row["name"] == name), None)


class TestUtilisateurs(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _creer(self, roles=("Sales User",)):
		return U.save_utilisateur(
			values={"email": EMAIL, "prenom": "Essai", "nom_famille": "Compte", "mot_de_passe": MDP, "roles": list(roles)}
		)

	def test_creer_un_compte(self):
		compte = _compte(self._creer(["Sales User", "Opérateur Conditionnement"]))
		self.assertEqual(compte["nom"], "Essai Compte")
		self.assertEqual(compte["roles"], ["Opérateur Conditionnement", "Sales User"])
		self.assertTrue(compte["acces_bureau"])
		self.assertTrue(compte["actif"])
		with self.assertRaises(frappe.ValidationError):
			self._creer()
		with self.assertRaises(frappe.ValidationError):
			U.save_utilisateur(values={"email": "pas-une-adresse", "prenom": "X", "mot_de_passe": MDP})
		with self.assertRaises(frappe.ValidationError):
			U.save_utilisateur(values={"email": "autre.essai@example.com", "prenom": "X", "mot_de_passe": "court"})

	def test_roles_et_desactivation(self):
		compte = _compte(self._creer(["Sales User"]))
		self.assertFalse(compte["acces_bureau"])
		frappe.get_doc("User", EMAIL).add_roles("Blogger")
		compte = _compte(U.get_utilisateurs())
		reponse = U.save_utilisateur(
			EMAIL, compte["modified"], {"prenom": "Essai", "actif": False, "roles": ["Stock User", "Magasinier Conditionnement"]}
		)
		compte = _compte(reponse)
		self.assertEqual(compte["roles"], ["Magasinier Conditionnement", "Stock User"])
		self.assertFalse(compte["actif"])
		self.assertIn("Blogger", frappe.get_roles(EMAIL))
		with self.assertRaises(frappe.TimestampMismatchError):
			U.save_utilisateur(EMAIL, "2000-01-01 00:00:00", {"prenom": "Essai"})
		with self.assertRaises(frappe.ValidationError):
			U.save_utilisateur(EMAIL, compte["modified"], {"prenom": "Essai", "roles": ["Rôle imaginaire"]})

	def test_mot_de_passe(self):
		compte = _compte(self._creer())
		U.set_mot_de_passe(EMAIL, compte["modified"], "Autre-Quartz-2027!")
		from frappe.utils.password import check_password

		self.assertEqual(check_password(EMAIL, "Autre-Quartz-2027!"), EMAIL)
		with self.assertRaises(frappe.ValidationError):
			U.set_mot_de_passe(EMAIL, _compte(U.get_utilisateurs())["modified"], "court")

	def test_garde_fous_sur_soi(self):
		compte = _compte(self._creer(["System Manager", "Sales User"]))
		frappe.set_user(EMAIL)
		with self.assertRaises(frappe.ValidationError):
			U.save_utilisateur(EMAIL, compte["modified"], {"prenom": "Essai", "actif": False, "roles": compte["roles"]})
		with self.assertRaises(frappe.ValidationError):
			U.save_utilisateur(EMAIL, compte["modified"], {"prenom": "Essai", "roles": ["Sales User"]})
		with self.assertRaises(frappe.ValidationError):
			U.save_utilisateur("Administrator", None, {"prenom": "X"})

	def test_sans_droit(self):
		def refus(*args, throw=False, **kwargs):
			if throw:
				frappe.throw("Refusé", frappe.PermissionError)
			return False

		with patch("frappe.has_permission", side_effect=refus):
			with self.assertRaises(frappe.PermissionError):
				U.get_utilisateurs()
			with self.assertRaises(frappe.PermissionError):
				self._creer()
