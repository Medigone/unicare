# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_bulk, bureau_fournisseurs, bureau_list


def _row(fournisseur, **values):
	return {
		"name": fournisseur,
		"fournisseur": fournisseur,
		"status": None,
		"categorie": None,
		"wilaya": None,
		"contact": None,
		"telephone": None,
		"solde": None,
		**values,
	}


def _values(**extra):
	return {
		"supplier_name": "Emballages Essai Bureau",
		"categorie": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
		"commune": frappe.db.get_value("Commune", {}, "name"),
		**extra,
	}


class TestListeFournisseurs(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_ordre_par_nom_et_valeur_vide_a_la_fin(self):
		rows = [_row("b", wilaya="Sétif"), _row("A", wilaya=None), _row("c", wilaya="Alger")]
		order = bureau_fournisseurs.order_fournisseurs
		self.assertEqual([row["fournisseur"] for row in order(rows)], ["A", "b", "c"])
		self.assertEqual([row["fournisseur"] for row in order(rows, "wilaya", "desc")], ["b", "c", "A"])

	def test_vues(self):
		self.assertTrue(bureau_fournisseurs.VIEWS["exclu"]({"status": "Exclu"}))
		self.assertFalse(bureau_fournisseurs.VIEWS["actif"]({"status": "Exclu"}))
		self.assertTrue(bureau_fournisseurs.VIEWS["solde"]({"solde": 10}))
		self.assertFalse(bureau_fournisseurs.VIEWS["solde"]({"solde": None}))

	def test_liste_et_compteurs(self):
		response = bureau_fournisseurs.get_fournisseurs(page_length=500)
		self.assertEqual(response["counts"]["all"], response["total"])
		self.assertEqual(len(response["names"]), response["total"])
		with self.assertRaises(frappe.ValidationError):
			bureau_fournisseurs.get_fournisseurs(view="inconnue")

	def test_sans_droit_comptable_pas_de_solde(self):
		with patch.object(bureau_fournisseurs, "_readable", return_value=False):
			self.assertEqual(bureau_fournisseurs._soldes(), {})
			response = bureau_fournisseurs.get_fournisseurs()
		self.assertTrue(all(row["solde"] is None for row in response["fournisseurs"]))

	def test_options_filtres_et_actions_groupees(self):
		options = bureau_fournisseurs.get_fournisseur_options()
		fields = {entry["field"] for entry in options["filter_fields"]}
		self.assertTrue({"custom_statut", "supplier_group", "custom_wilaya", bureau_list.BELL_FILTER} <= fields)
		self.assertEqual(options["statuses"], ["Actif", "Exclu"])
		bulk = {field["fieldname"] for field in bureau_bulk.get_bulk_options("Supplier")["fields"]}
		self.assertNotIn("supplier_name", bulk)


class TestFicheFournisseur(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_creation_avec_contact_principal(self):
		name = bureau_fournisseurs.create_fournisseur(
			json.dumps(_values(contact="Samir Test", fonction="Commercial", contact_telephone="0550000000"))
		)["name"]
		doc = frappe.get_doc("Supplier", name)
		self.assertEqual(doc.custom_statut, bureau_fournisseurs.ACTIF)
		self.assertTrue(doc.supplier_primary_contact)
		contact = frappe.get_doc("Contact", doc.supplier_primary_contact)
		self.assertEqual(contact.links[0].link_name, name)
		fiche = bureau_fournisseurs.get_fournisseur(name, full=1)
		self.assertEqual(fiche["contacts"][0]["nom"], "Samir Test")
		self.assertEqual(set(fiche["achats"]), set(bureau_fournisseurs.ACHATS))

	def test_creation_refusee(self):
		with self.assertRaises(frappe.ValidationError):
			bureau_fournisseurs.create_fournisseur(json.dumps(_values(categorie="")))
		with self.assertRaises(frappe.ValidationError):
			bureau_fournisseurs.create_fournisseur(json.dumps(_values(fonction="Commercial")))
		bureau_fournisseurs.create_fournisseur(json.dumps(_values()))
		with self.assertRaises(frappe.ValidationError):
			bureau_fournisseurs.create_fournisseur(json.dumps(_values(supplier_name="emballages essai bureau")))

	def test_modification_et_version(self):
		name = bureau_fournisseurs.create_fournisseur(json.dumps(_values()))["name"]
		doc = frappe.get_doc("Supplier", name)
		updated = bureau_fournisseurs.update_fournisseur(
			name, str(doc.modified), json.dumps({"status": "Exclu", "nif": "0001", "inconnu": "x"})
		)
		self.assertEqual(updated["status"], "Exclu")
		self.assertEqual(updated["pieces"][1]["numero"], "0001")
		with self.assertRaises(frappe.TimestampMismatchError):
			bureau_fournisseurs.update_fournisseur(name, str(doc.modified), json.dumps({"status": "Actif"}))
		self.assertNotIn(name, [row["name"] for row in bureau_fournisseurs.search_fournisseurs("", actifs=1)])
