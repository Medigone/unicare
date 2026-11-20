# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_achats, bureau_bulk, bureau_devis, bureau_devis_fournisseur, bureau_fournisseurs
from unicare.setup.algeria import bareme_timbre, get_account
from unicare.tests.achats_outils import article, fournisseur

DF = bureau_devis_fournisseur


class TestVuesDevisFournisseur(FrappeTestCase):
	def test_vues(self):
		day = today()
		self.assertTrue(DF.in_view("brouillons", {"status": "Draft"}, day))
		self.assertTrue(DF.in_view("ouverts", {"status": "Submitted", "commande": False}, day))
		self.assertFalse(DF.in_view("ouverts", {"status": "Submitted", "commande": True}, day))
		self.assertTrue(DF.in_view("commandes", {"status": "Submitted", "commande": True}, day))
		self.assertTrue(
			DF.in_view("expirent", {"status": "Submitted", "commande": False, "valable": add_days(day, 3)}, day)
		)
		self.assertFalse(
			DF.in_view("expirent", {"status": "Submitted", "commande": False, "valable": add_days(day, 30)}, day)
		)
		self.assertTrue(DF.in_view("clos", {"status": "Expired"}, day))

	def test_ordre(self):
		rows = [{"name": "A", "date": "2026-01-02", "total": 5}, {"name": "B", "date": "2026-03-01", "total": 9}]
		self.assertEqual([row["name"] for row in DF.order_devis(rows)], ["B", "A"])
		self.assertEqual([row["name"] for row in DF.order_devis(rows, "total", "asc")], ["A", "B"])


class TestDevisFournisseur(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.fournisseur = fournisseur()
		self.avec_prix = article("Flacon essai achat", 120)
		self.sans_prix = article("Bouchon essai achat")

	def tearDown(self):
		frappe.db.rollback()

	def _devis(self, **extra):
		values = {
			"fournisseur": self.fournisseur,
			"valable": add_days(today(), 15),
			"reference": "DEV-F-42",
			"taxes": bureau_achats.taxes_options(DF._company())["taxes_defaut"],
			"lignes": [{"article": self.avec_prix, "quantite": 10, "prix": None}],
			**extra,
		}
		return DF.create_devis_fournisseur(json.dumps(values))["name"]

	def test_prix_d_achat_et_tva(self):
		fiche = DF.get_devis_fournisseur(self._devis())
		self.assertEqual(fiche["lignes"][0]["prix"], 120)
		self.assertEqual(fiche["reference"], "DEV-F-42")
		self.assertTrue(fiche["taxes"])
		self.assertGreater(fiche["total_ttc"], fiche["total"])
		self.assertEqual(fiche["actions"], ["modifier", "valider", "supprimer"])

	def test_ligne_sans_prix_bloque_la_validation(self):
		name = self._devis(lignes=[{"article": self.sans_prix, "quantite": 2}])
		fiche = DF.get_devis_fournisseur(name)
		self.assertTrue(fiche["blocked"])
		with self.assertRaises(frappe.ValidationError):
			DF.validate_devis_fournisseur(name, fiche["modified"])

	def test_refus(self):
		with self.assertRaises(frappe.ValidationError):
			self._devis(lignes=[])
		with self.assertRaises(frappe.ValidationError):
			self._devis(valable="2000-01-01")
		doc = frappe.get_doc("Supplier", self.fournisseur)
		bureau_fournisseurs.update_fournisseur(doc.name, str(doc.modified), json.dumps({"status": "Exclu"}))
		with self.assertRaises(frappe.ValidationError):
			self._devis()

	def test_cycle_jusqu_a_la_commande(self):
		name = self._devis()
		fiche = DF.get_devis_fournisseur(name)
		fiche = DF.update_devis_fournisseur(
			name, fiche["modified"], json.dumps({"lignes": [{"article": self.avec_prix, "quantite": 4, "prix": 100}]})
		)
		self.assertEqual(fiche["total"], 400)
		with self.assertRaises(frappe.TimestampMismatchError):
			DF.validate_devis_fournisseur(name, "2000-01-01 00:00:00")
		fiche = DF.validate_devis_fournisseur(name, fiche["modified"])
		self.assertEqual(fiche["status"], "Submitted")
		self.assertIn("commande", fiche["actions"])
		result = DF.create_commande_achat(name, fiche["modified"], add_days(today(), 7))
		commande = frappe.get_doc("Purchase Order", result["commande"])
		self.assertEqual(commande.supplier, self.fournisseur)
		self.assertEqual(commande.items[0].supplier_quotation, name)
		self.assertEqual(str(commande.schedule_date), add_days(today(), 7))
		self.assertEqual([row["name"] for row in result["devis"]["commandes"]], [commande.name])
		liste = DF.get_devis_fournisseurs(view="commandes", page_length=500)
		self.assertIn(name, liste["names"])

	def test_actions_groupees_et_bulk(self):
		name = self._devis()
		fiche = DF.validate_devis_fournisseur(name, DF.get_devis_fournisseur(name)["modified"])
		result = bureau_bulk.bulk_delete("Supplier Quotation", json.dumps([{"name": name, "modified": fiche["modified"]}]))
		self.assertEqual(result["done"], [])
		self.assertEqual(len(result["skipped"]), 1)


class TestAffichageLignesEtTva(FrappeTestCase):
	def test_description_html_masquee_si_egale_a_la_designation(self):
		ligne = frappe._dict(item_name="Shampoing Vrac", description="<div><p>Shampoing Vrac</p></div>")
		self.assertIsNone(bureau_devis.line_description(ligne))
		ligne.description = "<div><p>Parfum <b>lavande</b></p></div>"
		self.assertEqual(bureau_devis.line_description(ligne), "Parfum lavande")

	def test_une_seule_ligne_tva_et_le_timbre_a_part(self):
		company = DF._company()
		timbre = get_account(company, bareme_timbre()["compte"])
		taxes = [
			frappe._dict(account_head="44566 - TVA", description="TVA déductible 19%", tax_amount=1900),
			frappe._dict(account_head="44566 - TVA", description="TVA 9%", tax_amount=90),
		]
		if timbre:
			taxes.append(frappe._dict(account_head=timbre, description="Droit de timbre", tax_amount=10))
		lines = bureau_devis.tax_lines(frappe._dict(company=company, taxes=taxes))
		self.assertEqual(lines[0], {"description": "TVA", "montant": 1990})
		if timbre:
			self.assertEqual(lines[1], {"description": "Droit de timbre", "montant": 10})
		self.assertEqual(bureau_devis.tax_lines(frappe._dict(company=company, taxes=[])), [])


class TestListeDePrixAchat(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.fournisseur = fournisseur("Fournisseur Essai Liste")
		self.article = article("Flacon essai liste", 120)
		devise = frappe.db.get_value("Price List", bureau_achats.buying_price_list(), "currency")
		self.liste = (
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": "Achat négocié essai",
					"enabled": 1,
					"buying": 1,
					"currency": devise,
				}
			)
			.insert()
			.name
		)
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": self.article,
				"price_list": self.liste,
				"price_list_rate": 100,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def _values(self, **extra):
		return {
			"fournisseur": self.fournisseur,
			"lignes": [{"article": self.article, "quantite": 5}],
			**extra,
		}

	def test_liste_choisie_fixe_le_prix_et_se_change(self):
		self.assertIn(self.liste, DF.get_devis_fournisseur_options()["listes_prix"])
		values = self._values(valable=add_days(today(), 15), liste_prix=self.liste)
		fiche = DF.get_devis_fournisseur(DF.create_devis_fournisseur(json.dumps(values))["name"])
		self.assertEqual(fiche["liste_prix"], self.liste)
		self.assertEqual(fiche["lignes"][0]["prix"], 100)
		defaut = bureau_achats.buying_price_list()
		fiche = DF.update_devis_fournisseur(
			fiche["name"],
			fiche["modified"],
			json.dumps({"liste_prix": defaut, "lignes": [{"article": self.article, "quantite": 5}]}),
		)
		self.assertEqual(fiche["liste_prix"], defaut)
		self.assertEqual(fiche["lignes"][0]["prix"], 120)

	def test_liste_du_fournisseur_par_defaut(self):
		from unicare.api import bureau_commandes_achat

		frappe.db.set_value("Supplier", self.fournisseur, "default_price_list", self.liste)
		trouve = next(
			row
			for row in bureau_fournisseurs.search_fournisseurs("Fournisseur Essai Liste", 1)
			if row["name"] == self.fournisseur
		)
		self.assertEqual(trouve["liste_prix"], self.liste)
		commande = bureau_commandes_achat.create_commande_achat(
			json.dumps(self._values(reception=add_days(today(), 7)))
		)["name"]
		fiche = bureau_commandes_achat.get_commande_achat(commande)
		self.assertEqual(fiche["liste_prix"], self.liste)
		self.assertEqual(fiche["lignes"][0]["prix"], 100)

	def test_prix_et_recherche_dans_la_liste(self):
		prix = bureau_achats.get_prix_achat(json.dumps([self.article]), self.liste)
		self.assertEqual(prix, {"prix": {self.article: 100}, "liste": {self.article: 100}})
		trouves = bureau_achats.search_achat_articles("Flacon essai liste", self.liste)
		self.assertEqual(trouves[0]["prix"], 100)
		self.assertEqual(trouves[0]["prix_liste"], 100)
		self.assertRaises(
			frappe.ValidationError,
			bureau_achats.get_prix_achat,
			json.dumps([self.article]),
			bureau_devis._price_list(),
		)


class TestPrixAchatSaisisReportes(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.fournisseur = fournisseur("Fournisseur Essai Report")
		self.avec_prix = article("Flacon essai report", 120)
		self.sans_prix = article("Bouchon essai report")
		self.liste = bureau_achats.buying_price_list()

	def tearDown(self):
		frappe.db.rollback()

	def _prix(self, article):
		return frappe.db.get_value(
			"Item Price", {"price_list": self.liste, "item_code": article}, "price_list_rate"
		)

	def test_devis_fournisseur(self):
		lignes = [
			{"article": self.avec_prix, "quantite": 1, "prix": 110},
			{"article": self.sans_prix, "quantite": 1, "prix": 15},
		]
		values = {"fournisseur": self.fournisseur, "valable": add_days(today(), 15), "lignes": lignes}
		DF.create_devis_fournisseur(json.dumps({**values, "tarifs": [self.sans_prix]}))
		self.assertEqual(self._prix(self.sans_prix), 15)
		self.assertEqual(self._prix(self.avec_prix), 120)
		DF.create_devis_fournisseur(json.dumps({**values, "tarifs": [self.avec_prix]}))
		self.assertEqual(self._prix(self.avec_prix), 110)

	def test_commande_d_achat_modifiee(self):
		from unicare.api import bureau_commandes_achat as CA

		values = {
			"fournisseur": self.fournisseur,
			"reception": add_days(today(), 7),
			"lignes": [{"article": self.sans_prix, "quantite": 2, "prix": 8}],
		}
		commande = CA.get_commande_achat(CA.create_commande_achat(json.dumps(values))["name"])
		self.assertIsNone(self._prix(self.sans_prix))
		lignes = [{"article": self.sans_prix, "quantite": 2, "prix": 9}]
		CA.update_commande_achat(
			commande["name"], commande["modified"], json.dumps({"lignes": lignes, "tarifs": [self.sans_prix]})
		)
		self.assertEqual(self._prix(self.sans_prix), 9)
