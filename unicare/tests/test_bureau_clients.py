# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_bulk, bureau_clients, bureau_list


def _row(client, **values):
	return {
		"name": client,
		"client": client,
		"status": None,
		"categorie": None,
		"wilaya": None,
		"contact": None,
		"telephone": None,
		"solde": None,
		**values,
	}


class TestListeClients(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_ordre_par_nom_et_valeur_vide_a_la_fin(self):
		rows = [_row("b", wilaya="Sétif"), _row("A", wilaya=None), _row("c", wilaya="Alger")]
		self.assertEqual([row["client"] for row in bureau_clients.order_clients(rows)], ["A", "b", "c"])
		self.assertEqual(
			[row["client"] for row in bureau_clients.order_clients(rows, "wilaya", "desc")], ["b", "c", "A"]
		)

	def test_tri_numerique_du_solde(self):
		rows = [_row("A", solde=9), _row("B", solde=100), _row("C", solde=None)]
		self.assertEqual(
			[row["client"] for row in bureau_clients.order_clients(rows, "solde", "desc")], ["B", "A", "C"]
		)

	def test_vues(self):
		self.assertTrue(bureau_clients.VIEWS["perdu"]({"status": "Exclu"}))
		self.assertFalse(bureau_clients.VIEWS["actif"]({"status": "Dormant"}))
		self.assertTrue(bureau_clients.VIEWS["solde"]({"solde": 10}))
		self.assertFalse(bureau_clients.VIEWS["solde"]({"solde": None}))

	def test_liste_et_compteurs(self):
		response = bureau_clients.get_clients(page_length=500)
		self.assertEqual(response["counts"]["all"], response["total"])
		self.assertEqual(len(response["names"]), response["total"])
		with self.assertRaises(frappe.ValidationError):
			bureau_clients.get_clients(view="inconnue")

	def test_filtre_inconnu_refuse(self):
		with self.assertRaises(frappe.ValidationError):
			bureau_clients.get_clients(
				conditions=json.dumps(
					[{"doctype": "Customer", "field": "champ_absent", "op": "=", "value": "x"}]
				)
			)

	def test_sans_droit_comptable_pas_de_solde(self):
		with patch.object(bureau_clients, "_readable", return_value=False):
			self.assertEqual(bureau_clients._soldes(), {})
			response = bureau_clients.get_clients()
		self.assertTrue(all(row["solde"] is None for row in response["clients"]))

	def test_gps(self):
		self.assertEqual(bureau_clients.parse_gps("36.75, 3.06"), (36.75, 3.06))
		self.assertEqual(bureau_clients.parse_gps("hors carte"), (None, None))
		self.assertEqual(bureau_clients.parse_gps("120, 3"), (None, None))

	def test_options_et_filtres(self):
		options = bureau_clients.get_client_options()
		fields = {entry["field"] for entry in options["filter_fields"]}
		self.assertTrue(
			{"custom_status", "customer_group", "custom_wilaya", bureau_list.BELL_FILTER} <= fields
		)


def _values(**extra):
	return {
		"customer_name": "Pharmacie Essai Bureau",
		"forme_juridique": "SARL",
		"categorie": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
		"commune": frappe.db.get_value("Commune", {}, "name"),
		**extra,
	}


class TestFicheClient(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_creation_avec_contact_principal(self):
		name = bureau_clients.create_client(
			json.dumps(_values(contact="Karim Test", fonction="Gérant", contact_telephone="0550000000"))
		)["name"]
		doc = frappe.get_doc("Customer", name)
		self.assertEqual(doc.customer_name, "PHARMACIE ESSAI BUREAU")
		self.assertEqual(doc.custom_status, bureau_clients.NEW_STATUS)
		self.assertTrue(doc.custom_wilaya)
		self.assertEqual(doc.custom_nom_contact_principal, "Karim Test")
		contact = frappe.get_doc("Contact", doc.customer_primary_contact)
		self.assertEqual(contact.links[0].link_name, name)
		self.assertEqual(contact.designation, "Gérant")

	def test_creation_refusee(self):
		with self.assertRaises(frappe.ValidationError):
			bureau_clients.create_client(json.dumps(_values(commune="")))
		with self.assertRaises(frappe.ValidationError):
			bureau_clients.create_client(json.dumps(_values(fonction="Gérant")))
		with self.assertRaises(frappe.ValidationError):
			bureau_clients.create_client(json.dumps(_values(forme_juridique="SPA inventée")))
		bureau_clients.create_client(json.dumps(_values()))
		with self.assertRaises(frappe.ValidationError):
			bureau_clients.create_client(json.dumps(_values(customer_name="pharmacie essai bureau")))

	def test_modification_et_version(self):
		name = bureau_clients.create_client(json.dumps(_values()))["name"]
		doc = frappe.get_doc("Customer", name)
		updated = bureau_clients.update_client(
			name, str(doc.modified), json.dumps({"status": "Dormant", "rc": "16/00-123", "inconnu": "x"})
		)
		self.assertEqual(updated["status"], "Dormant")
		self.assertEqual(updated["pieces"][0]["numero"], "16/00-123")
		self.assertIn("ventes", updated)
		with self.assertRaises(frappe.TimestampMismatchError):
			bureau_clients.update_client(name, str(doc.modified), json.dumps({"status": "Actif"}))

	def test_fiche_complete(self):
		name = bureau_clients.create_client(json.dumps(_values()))["name"]
		self.assertNotIn("ventes", bureau_clients.get_client(name))
		fiche = bureau_clients.get_client(name, full=1)
		self.assertEqual(set(fiche["ventes"]), set(bureau_clients.VENTES))
		self.assertEqual(fiche["comments"]["count"], 0)
		feed = bureau_clients.add_client_comment(name, "Premier échange")
		self.assertEqual(feed["comment_count"], 1)
		with patch.object(bureau_clients, "_readable", return_value=False):
			self.assertIsNone(bureau_clients.get_client(name, full=1)["comptabilite"])

	def test_recherche_communes_et_doublons(self):
		commune = frappe.get_doc("Commune", frappe.db.get_value("Commune", {}, "name"))
		found = bureau_clients.search_communes(commune.nom)
		self.assertIn(commune.name, [row.name for row in found])
		self.assertEqual(bureau_clients.search_clients(""), [])


class TestSocleListes(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_liste_inconnue_refusee(self):
		with self.assertRaises(frappe.ValidationError):
			bureau_list.get_saved_filters("Journal Entry")

	def test_page_vide_ramene_a_la_derniere(self):
		self.assertEqual(bureau_list.page_bounds(45, 60, 20), (40, 20))
		self.assertEqual(bureau_list.page_bounds(0, 20, 20), (0, 20))

	def test_cloche_toujours_la_personne_connectee(self):
		filters = bureau_list.condition_filters(
			[{"doctype": "Customer", "field": bureau_list.BELL_FILTER, "op": "=", "value": "1"}], "Customer"
		)
		self.assertEqual(filters, [["Customer", bureau_list.BELL_FIELD, "like", '%"Administrator"%']])

	def test_actions_groupees_seulement_sur_les_listes_declarees(self):
		self.assertNotIn(
			"customer_name",
			{field["fieldname"] for field in bureau_bulk.get_bulk_options("Customer")["fields"]},
		)
		with self.assertRaises(frappe.PermissionError):
			bureau_bulk.get_bulk_options("Journal Entry")
