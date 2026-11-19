# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_societe as S

LECTEUR = "lecteur.societe@example.com"


def _lecteur():
	if not frappe.db.exists("User", LECTEUR):
		user = frappe.get_doc(
			{"doctype": "User", "email": LECTEUR, "first_name": "Lecteur", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		user.add_roles("Opérateur Conditionnement")
	return LECTEUR


class TestSociete(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_lecture_et_mentions(self):
		societe = S.get_societe()
		self.assertTrue(societe["peut_modifier"])
		self.assertEqual(
			[m["cle"] for m in societe["mentions"]],
			["raison_sociale", "forme_juridique", "capital_social", "adresse", "rc", "nif", "nis", "ai"],
		)
		self.assertIn("raison_sociale", societe["valeurs"])

	def test_enregistrer(self):
		societe = S.get_societe()
		valeurs = dict(societe["valeurs"])
		valeurs.update(
			{
				"forme_juridique": " SARL ",
				"capital_social": "1 000 000",
				"nif": "0021 1612 3456 789",
				"ai": "123",
			}
		)
		apres = S.save_societe(societe["modified"], valeurs)
		self.assertEqual(apres["valeurs"]["forme_juridique"], "SARL")
		self.assertEqual(apres["valeurs"]["capital_social"], 1000000)
		self.assertTrue(next(m for m in apres["mentions"] if m["cle"] == "capital_social")["ok"])
		# l'AI de 3 chiffres passe, avec un avertissement ; le NIF de 15 chiffres, sans
		self.assertEqual(len(apres["avertissements"]), 1)
		self.assertIn("AI", apres["avertissements"][0])
		with self.assertRaises(frappe.TimestampMismatchError):
			S.save_societe(societe["modified"], valeurs)

	def test_refus(self):
		societe = S.get_societe()
		for champ, valeur in (
			("nif", "12AB"),
			("capital_social", "beaucoup"),
			("email", "pas-un-mail"),
			("raison_sociale", "  "),
		):
			valeurs = dict(societe["valeurs"], **{champ: valeur})
			with self.assertRaises(frappe.ValidationError, msg=champ):
				S.save_societe(societe["modified"], valeurs)

	def test_commune_d_une_autre_wilaya(self):
		communes = frappe.get_all(
			"Commune", fields=["name", "wilaya"], filters={"wilaya": ["is", "set"]}, limit=200
		)
		wilayas = list(dict.fromkeys(c.wilaya for c in communes))
		if len(wilayas) < 2:
			self.skipTest("il faut des communes dans deux wilayas")
		commune = next(c for c in communes if c.wilaya == wilayas[0])
		societe = S.get_societe()
		apres = S.save_societe(
			societe["modified"], dict(societe["valeurs"], wilaya=wilayas[1], commune=commune.name)
		)
		self.assertEqual(apres["valeurs"]["commune"], "")
		self.assertTrue(all(c["name"] for c in S.get_communes(wilayas[0])))

	def test_lecteur_ne_modifie_pas(self):
		frappe.set_user(_lecteur())
		with self.assertRaises(frappe.PermissionError):
			S.save_societe("x", {"raison_sociale": "Autre"})

	def test_facture_d_exemple(self):
		import io

		from pypdf import PdfReader

		if not frappe.get_all("Customer", limit=1) or not frappe.get_all(
			"Item", filters={"is_sales_item": 1}, limit=1
		):
			self.skipTest("il faut un client et un article")
		S.apercu_pdf()
		self.assertEqual(frappe.local.response.type, "pdf")
		texte = PdfReader(io.BytesIO(frappe.local.response.filecontent)).pages[0].extract_text()
		self.assertIn("FACTURE", texte)
		self.assertFalse(frappe.db.exists("Sales Invoice", "EXEMPLE"))

	def test_logo(self):
		import base64

		png = base64.b64decode(
			"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
		)
		apres = S.get_societe()
		S.enregistrer_logo(S._societe(), png, "image/png")
		apres = S.get_societe()
		self.assertTrue(apres["logo"].startswith("/files/logo-"))
		with self.assertRaises(frappe.ValidationError):
			S.enregistrer_logo(S._societe(), b"%PDF", "application/pdf")
		sans = S.supprimer_logo(apres["modified"])
		self.assertEqual(sans["logo"], "")
		self.assertFalse(frappe.db.exists("File", {"file_url": apres["logo"]}))
