# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import (
	bureau_articles,
	bureau_bulk,
	bureau_clients,
	bureau_commandes_achat,
	bureau_devis,
	bureau_factures_achat,
	bureau_fournisseurs,
	bureau_receptions,
	bureau_versions,
)
from unicare.tests.achats_outils import article, fournisseur

CA = bureau_commandes_achat


def _commande(fournisseur_name, article_name, quantite=5):
	name = CA.create_commande_achat(
		json.dumps(
			{
				"fournisseur": fournisseur_name,
				"reception": add_days(today(), 3),
				"lignes": [{"article": article_name, "quantite": quantite}],
			}
		)
	)["name"]
	return CA.validate_commande_achat(name, CA.get_commande_achat(name)["modified"])


class TestVersions(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.fournisseur = fournisseur("Fournisseur Essai Versions")
		self.article = article("Article essai versions", 40, stock=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_nouvelle_version_d_une_commande_annulee(self):
		fiche = _commande(self.fournisseur, self.article)
		self.assertNotIn("nouvelle_version", fiche["actions"])
		fiche = CA.cancel_commande_achat(fiche["name"], fiche["modified"])
		self.assertEqual(fiche["actions"], ["nouvelle_version", "supprimer"])
		result = CA.create_version(fiche["name"], fiche["modified"])
		self.assertEqual(result["name"], f"{fiche['name']}-1")
		version = CA.get_commande_achat(result["name"])
		self.assertEqual(version["docstatus"], 0)
		self.assertEqual(version["version_de"], fiche["name"])
		self.assertEqual(version["recu"], 0)
		self.assertEqual(version["versions"]["origine"]["name"], fiche["name"])
		origine = CA.get_commande_achat(fiche["name"])
		self.assertEqual([row["name"] for row in origine["versions"]["suivantes"]], [result["name"]])
		# Une seule version ouverte à la fois : l'action disparaît et le serveur refuse.
		self.assertNotIn("nouvelle_version", origine["actions"])
		with self.assertRaises(frappe.ValidationError):
			bureau_versions.amend(frappe.get_doc("Purchase Order", fiche["name"]))
		# L'original reste cité par sa nouvelle version : Frappe refuse de le supprimer.
		with self.assertRaises(frappe.LinkExistsError):
			CA.delete_commande_achat(fiche["name"], origine["modified"])
		# La version validée, annulée puis refaite donne -2.
		version = CA.validate_commande_achat(result["name"], version["modified"])
		version = CA.cancel_commande_achat(result["name"], version["modified"])
		self.assertEqual(CA.create_version(result["name"], version["modified"])["name"], f"{fiche['name']}-2")

	def test_suppression_d_une_piece_annulee_et_en_groupe(self):
		fiche = _commande(self.fournisseur, self.article)
		fiche = CA.cancel_commande_achat(fiche["name"], fiche["modified"])
		CA.delete_commande_achat(fiche["name"], fiche["modified"])
		self.assertFalse(frappe.db.exists("Purchase Order", fiche["name"]))
		autre = _commande(self.fournisseur, self.article)
		autre = CA.cancel_commande_achat(autre["name"], autre["modified"])
		valide = _commande(self.fournisseur, self.article)
		result = bureau_bulk.bulk_delete(
			"Purchase Order",
			json.dumps([{"name": autre["name"], "modified": autre["modified"]}, {"name": valide["name"], "modified": valide["modified"]}]),
		)
		self.assertEqual(result["done"], [autre["name"]])
		self.assertEqual([row["name"] for row in result["skipped"]], [valide["name"]])

	def test_reception_annulee_refaite(self):
		fiche = _commande(self.fournisseur, self.article)
		reception = CA.create_suivante(fiche["name"], fiche["modified"], "reception")["name"]
		prep = bureau_receptions.get_reception(reception)
		depot = frappe.db.get_value("Warehouse", {"company": CA._company(), "is_group": 0}, "name")
		prep = bureau_receptions.prepare_reception(
			reception, prep["modified"], json.dumps([{"name": prep["lignes"][0]["name"], "depot": depot}])
		)
		prep = bureau_receptions.validate_reception(reception, prep["modified"])
		prep = bureau_receptions.cancel_reception(reception, prep["modified"])
		version = bureau_receptions.create_version(reception, prep["modified"])
		doc = frappe.get_doc("Purchase Receipt", version["name"])
		self.assertEqual(doc.amended_from, reception)
		self.assertEqual(doc.items[0].purchase_order, fiche["name"])
		bureau_receptions.validate_reception(doc.name, str(doc.modified))
		self.assertEqual(frappe.db.get_value("Purchase Order", fiche["name"], "per_received"), 100)

	def test_facture_achat_annulee_refaite(self):
		fiche = _commande(self.fournisseur, article("Service essai versions", 300))
		facture = CA.create_suivante(fiche["name"], fiche["modified"], "facture")["name"]
		FA = bureau_factures_achat
		doc = FA.update_facture_achat(facture, FA.get_facture_achat(facture)["modified"], json.dumps({"numero_fournisseur": "V-1"}))
		doc = FA.validate_facture_achat(facture, doc["modified"])
		doc = FA.cancel_facture_achat(facture, doc["modified"])
		version = FA.get_facture_achat(FA.create_version(facture, doc["modified"])["name"])
		self.assertEqual(version["numero_fournisseur"], "V-1")
		self.assertEqual(version["status"], "Draft")
		self.assertEqual(version["paye"], 0)

	def test_devis_client_annule_refait(self):
		client = bureau_clients.create_client(
			json.dumps(
				{
					"customer_name": "Pharmacie Versions Essai",
					"forme_juridique": "SARL",
					"categorie": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
					"commune": frappe.db.get_value("Commune", {}, "name"),
				}
			)
		)["name"]
		item = frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1, "has_variants": 0}, "name")
		name = bureau_devis.create_devis(
			json.dumps(
				{"client": client, "valable": add_days(today(), 10), "lignes": [{"article": item, "quantite": 2, "prix": 10}]}
			)
		)["name"]
		fiche = bureau_devis.validate_devis(name, bureau_devis.get_devis(name)["modified"])
		fiche = bureau_devis.cancel_devis(name, fiche["modified"])
		version = bureau_devis.create_version(name, fiche["modified"])
		self.assertEqual(frappe.db.get_value("Quotation", version["name"], ["amended_from", "docstatus"]), (name, 0))


class TestSuppressionFiches(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_fournisseur_libre_puis_lie(self):
		libre = fournisseur("Fournisseur Essai Suppression")
		self.assertTrue(bureau_fournisseurs.get_fournisseur(libre)["can_delete"])
		bureau_fournisseurs.delete_fournisseur(libre, str(frappe.db.get_value("Supplier", libre, "modified")))
		self.assertFalse(frappe.db.exists("Supplier", libre))
		lie = fournisseur("Fournisseur Essai Lié")
		_commande(lie, article("Article essai lié", 10))
		with self.assertRaises(frappe.LinkExistsError):
			bureau_fournisseurs.delete_fournisseur(lie, str(frappe.db.get_value("Supplier", lie, "modified")))

	def test_client_et_article_libres(self):
		client = bureau_clients.create_client(
			json.dumps(
				{
					"customer_name": "Client Essai Suppression",
					"forme_juridique": "SARL",
					"categorie": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
					"commune": frappe.db.get_value("Commune", {}, "name"),
					"contact": "Contact Essai",
				}
			)
		)["name"]
		bureau_clients.delete_client(client, str(frappe.db.get_value("Customer", client, "modified")))
		self.assertFalse(frappe.db.exists("Customer", client))
		item = article("Article essai suppression")
		bureau_articles.delete_article(item, str(frappe.db.get_value("Item", item, "modified")))
		self.assertFalse(frappe.db.exists("Item", item))
		with self.assertRaises(frappe.TimestampMismatchError):
			bureau_articles.delete_article(article("Article essai version"), "2000-01-01 00:00:00")
