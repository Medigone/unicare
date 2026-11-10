# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_postes
from unicare.www import bureau


class TestPostes(FrappeTestCase):
	def _keys(self, *roles):
		with patch("frappe.get_roles", return_value=list(roles)):
			return [poste["key"] for poste in bureau_postes.get_postes("x@example.com")]

	def _access(self, *roles):
		with patch("frappe.get_roles", return_value=list(roles)):
			return bureau_postes.can_access_bureau("x@example.com")

	def test_invite_sans_poste_ni_acces(self):
		self.assertEqual(bureau_postes.get_postes("Guest"), [])
		self.assertEqual(bureau_postes.get_droits("Guest"), {})
		self.assertFalse(bureau_postes.can_access_bureau("Guest"))

	def test_roles_conditionnement(self):
		for role in (
			"Magasinier Conditionnement",
			"Opérateur Conditionnement",
			"Responsable Conditionnement",
		):
			self.assertEqual(self._keys(role), ["conditionnement"])
			self.assertTrue(self._access(role))

	def test_acces_complet_voit_les_postes_ouverts(self):
		self.assertEqual(self._keys("System Manager"), ["conditionnement"])
		self.assertTrue(self._access("System Manager"))
		self.assertTrue(self._access("Administrator"))

	def test_autre_role_refuse(self):
		self.assertEqual(self._keys("Sales User"), [])
		self.assertFalse(self._access("Sales User"))

	def test_poste_ferme_ne_compte_pas(self):
		ferme = {**bureau_postes.POSTES["conditionnement"], "ouvert": False}
		with patch.dict(bureau_postes.POSTES, {"conditionnement": ferme}):
			self.assertEqual(self._keys("Opérateur Conditionnement"), [])

	def test_droits_de_l_administrateur(self):
		droits = bureau_postes.get_droits("Administrator")
		self.assertEqual(set(droits), set(bureau_postes.DOCTYPES_INTERFACE))
		self.assertTrue(all(droit["read"] for droit in droits.values()))

	def test_documents_de_l_interface_existent(self):
		for doctype in bureau_postes.DOCTYPES_INTERFACE:
			self.assertTrue(frappe.db.exists("DocType", doctype), doctype)


class TestPageBureau(FrappeTestCase):
	def test_retour_apres_connexion_reste_dans_le_poste(self):
		self.assertEqual(bureau.safe_redirect("/bureau/ordres?page=2"), "/bureau/ordres?page=2")
		self.assertEqual(bureau.safe_redirect("/bureau"), "/bureau")
		for target in (
			"",
			None,
			"https://exemple.com/bureau",
			"//exemple.com",
			"/app",
			"/bureaux",
			"/bureau/connexion",
		):
			self.assertEqual(bureau.safe_redirect(target), "/bureau", target)

	def test_boot_de_l_administrateur(self):
		frappe.set_user("Administrator")
		# Hors requête HTTP, Frappe n'a pas de session où ranger le jeton CSRF.
		with patch("frappe.sessions.get_csrf_token", return_value="jeton"):
			boot = bureau.get_boot()
		self.assertEqual(boot.csrf_token, "jeton")
		self.assertTrue(boot.can_access)
		self.assertEqual([poste["key"] for poste in boot.postes], ["conditionnement"])
		self.assertEqual(boot.default_route, "/bureau")
