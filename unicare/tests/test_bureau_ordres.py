# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from unicare.api import bureau_bulk, bureau_mouvements, bureau_ordres
from unicare.conditionnement.stock import get_parametres
from unicare.tests.achats_outils import article

O = bureau_ordres


def _stock(item, depot):
	return flt(frappe.db.get_value("Bin", {"item_code": item, "warehouse": depot}, "actual_qty"))


def _type(item, kind, lots=False):
	frappe.db.set_value("Item", item, {"custom_type_conditionnement": kind, "has_batch_no": 1 if lots else 0, "valuation_rate": 20})


class TestVuesOrdres(FrappeTestCase):
	def test_vues_et_etapes(self):
		row = {"state": "Préparé", "retard": False}
		self.assertTrue(O.in_view("en_cours", row))
		self.assertTrue(O.in_view("prets", row))
		self.assertFalse(O.in_view("termines", row))
		self.assertTrue(O.in_view("en_retard", {**row, "retard": True}))
		self.assertTrue(O._retard("Brouillon", add_days(today(), -1)))
		self.assertFalse(O._retard("Terminé", add_days(today(), -1)))
		self.assertEqual(O.ETAPES["Brouillon"], "À planifier")


class TestOrdres(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.local.lang = "fr"
		p = get_parametres()
		self.magasin, self.atelier, self.pf_depot, self.rebus = p.warehouse_mp, p.warehouse_atelier, p.warehouse_pf, p.warehouse_rebuts
		self.fut = article("Vrac essai ordres", stock=True, lots=True)
		_type(self.fut, "Fût", lots=True)
		self.bouteille = article("Flacon essai ordres", stock=True)
		_type(self.bouteille, "Conditionnement")
		self.pf = article("Flacon rempli essai ordres", stock=True, lots=True)
		_type(self.pf, "Produit fini", lots=True)
		uom = frappe.db.get_value("Item", self.fut, "stock_uom")
		entree = bureau_mouvements.create_mouvement(
			json.dumps(
				{
					"nature": "entree",
					"cible": self.magasin,
					"lignes": [
						{"article": self.fut, "quantite": 100, "lot": "LOT-ESSAI-ORDRE", "peremption": add_days(today(), 200)},
						{"article": self.bouteille, "quantite": 500},
					],
				}
			)
		)["name"]
		fiche = bureau_mouvements.get_mouvement(entree)
		bureau_mouvements.validate_mouvement(entree, fiche["modified"])
		self.recette = frappe.get_doc(
			{
				"doctype": "Recette de Conditionnement",
				"produit_fini": self.pf,
				"quantite_base": 1,
				"uom": uom,
				"rendement_theorique": 100,
				"actif": 1,
				"ingredients": [
					{"item_code": self.fut, "type_ingredient": "Fût", "qty": 0.1, "uom": uom},
					{"item_code": self.bouteille, "type_ingredient": "Conditionnement", "qty": 1, "uom": uom},
				],
			}
		).insert().name
		self.checklist = frappe.get_doc(
			{"doctype": "Checklist Ordre Conditionnement", "titre": "Checklist essai ordres", "actif": 1, "lignes": [{"controle": "Ligne propre", "obligatoire": 1}, {"controle": "Balance tarée", "obligatoire": 1}]}
		).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _ordre(self, quantite=100):
		name = O.create_ordre(json.dumps({"recette": self.recette, "quantite": quantite, "date_prevue": today(), "checklist": self.checklist}))["name"]
		return O.get_ordre(name)

	def _cocher(self, fiche):
		for ligne in fiche["checklist"]:
			fiche = O.set_controle(fiche["name"], fiche["modified"], ligne["name"], conforme=1)
		return fiche

	def test_cycle_complet(self):
		fiche = self._ordre()
		self.assertEqual((fiche["state"], fiche["etape"]), ("Brouillon", "À planifier"))
		self.assertEqual([etape["statut"] for etape in fiche["etapes"]], ["en_cours", "a_venir", "a_venir", "a_venir"])
		vrac = next(line for line in fiche["matieres"] if line["article"] == self.fut)
		# Lot proposé tout seul : le seul en stock, qui couvre les 10 kg.
		self.assertEqual((vrac["prevu"], vrac["lot"], vrac["disponible"]), (10.0, "LOT-ESSAI-ORDRE", 100.0))
		self.assertTrue(any("contrôle" in manque["texte"] for manque in fiche["manques"]))
		self.assertIn("preparer", fiche["actions"])
		with self.assertRaises(frappe.ValidationError):
			O.preparer(fiche["name"], fiche["modified"])

		# Plus de bouteilles que le stock : le manque le dit en clair.
		fiche = O.update_ordre(fiche["name"], fiche["modified"], json.dumps({"quantite": 600}))
		self.assertTrue(any("500 en stock pour 600" in manque["texte"] for manque in fiche["manques"]))
		fiche = O.update_ordre(fiche["name"], fiche["modified"], json.dumps({"quantite": 100}))
		fiche = self._cocher(fiche)
		self.assertEqual(fiche["checklist"][0]["par"], frappe.utils.get_fullname("Administrator"))
		self.assertEqual(fiche["manques"], [])

		atelier_avant = _stock(self.bouteille, self.atelier)
		fiche = O.preparer(fiche["name"], fiche["modified"])
		self.assertEqual((fiche["state"], fiche["etape"]), ("Préparé", "Prêt à démarrer"))
		self.assertEqual(_stock(self.bouteille, self.atelier) - atelier_avant, 100)
		self.assertEqual([etape["statut"] for etape in fiche["etapes"]], ["fait", "fait", "en_cours", "a_venir"])
		self.assertEqual(fiche["mouvements"][0]["role"], "preparation")
		self.assertNotIn("modifier", fiche["actions"])

		fiche = O.demarrer(fiche["name"], fiche["modified"])
		self.assertEqual(fiche["state"], "En production")
		self.assertIn("saisir", fiche["actions"])
		fiche = O.complement(fiche["name"], fiche["modified"], self.bouteille, 5, self.magasin)
		self.assertEqual(fiche["complements"][0]["quantite"], 5)
		self.assertEqual(next(line for line in fiche["matieres"] if line["article"] == self.bouteille)["complement"], 5)
		fiche = O.add_rebut(fiche["name"], fiche["modified"], self.bouteille, 3)
		with self.assertRaises(frappe.ValidationError):
			O.add_rebut(fiche["name"], fiche["modified"], self.pf, 1)

		lignes = [{"name": line["name"], "utilise": 97 if line["article"] == self.bouteille else 9.7} for line in fiche["matieres"]]
		# Rendement de 50 % : hors tolérance, une remarque est exigée.
		with self.assertRaises(frappe.ValidationError):
			O.cloturer(fiche["name"], fiche["modified"], 50, json.dumps(lignes))
		pf_avant = _stock(self.pf, self.pf_depot)
		rebus_avant = _stock(self.bouteille, self.rebus)
		fiche = O.cloturer(fiche["name"], fiche["modified"], 97, json.dumps(lignes))
		self.assertEqual((fiche["state"], fiche["etape"], fiche["rendement"]), ("Terminé", "Terminé", 97.0))
		self.assertTrue(fiche["lot_pf"])
		self.assertEqual(_stock(self.pf, self.pf_depot) - pf_avant, 97)
		self.assertEqual(_stock(self.bouteille, self.rebus) - rebus_avant, 3)
		self.assertEqual({entry["role"] for entry in fiche["mouvements"]}, {"preparation", "complement", "production", "rebuts"})
		self.assertEqual(fiche["tracabilite"][0]["lot"], "LOT-ESSAI-ORDRE")
		self.assertEqual([etape["statut"] for etape in fiche["etapes"]], ["fait"] * 4)
		self.assertNotIn("annuler", fiche["actions"])

		liste = O.get_ordres(view="termines", page_length=500)
		self.assertIn(fiche["name"], liste["names"])

		# « Refaire cet ordre » : un nouvel ordre à planifier, mêmes réglages.
		copie = O.get_ordre(O.dupliquer(fiche["name"])["name"])
		self.assertEqual((copie["state"], copie["qty_prevue"], copie["recette"]), ("Brouillon", 100.0, self.recette))

	def test_cloture_hors_tolerance_avec_remarque(self):
		fiche = self._cocher(self._ordre(10))
		fiche = O.preparer(fiche["name"], fiche["modified"])
		fiche = O.demarrer(fiche["name"], fiche["modified"])
		lignes = [{"name": line["name"], "utilise": line["prevu"]} for line in fiche["matieres"]]
		fiche = O.cloturer(fiche["name"], fiche["modified"], 5, json.dumps(lignes), "Bourrage de la remplisseuse")
		self.assertEqual(fiche["state"], "Terminé")
		self.assertTrue(frappe.db.exists("Comment", {"reference_name": fiche["name"], "content": ["like", "%Bourrage%"]}))

	def test_annulation_rend_le_stock(self):
		avant = _stock(self.bouteille, self.magasin)
		fiche = self._cocher(self._ordre(50))
		fiche = O.preparer(fiche["name"], fiche["modified"])
		self.assertEqual(_stock(self.bouteille, self.magasin), avant - 50)
		fiche = O.annuler(fiche["name"], fiche["modified"])
		self.assertEqual(fiche["state"], "Annulé")
		self.assertEqual(_stock(self.bouteille, self.magasin), avant)
		self.assertEqual(fiche["mouvements"], [])
		self.assertEqual([etape["statut"] for etape in fiche["etapes"]][-1], "annule")

	def test_droits_et_suppression(self):
		fiche = self._ordre()
		user = "operateur.essai.ordres@example.com"
		frappe.get_doc({"doctype": "User", "email": user, "first_name": "Opérateur", "send_welcome_email": 0, "roles": [{"role": "Opérateur Conditionnement"}]}).insert(ignore_permissions=True)
		frappe.set_user(user)
		vue = O.get_ordre(fiche["name"])
		self.assertIn("preparer", vue["actions"])
		self.assertNotIn("annuler", vue["actions"])
		self.assertNotIn("supprimer", vue["actions"])
		frappe.set_user("Administrator")
		self.assertIn("en_cours", O.get_ordres()["counts"])
		result = bureau_bulk.bulk_delete("Ordre de Conditionnement", json.dumps([{"name": fiche["name"], "modified": fiche["modified"]}]))
		self.assertFalse(frappe.db.exists("Ordre de Conditionnement", fiche["name"]), result)

	def test_besoins_de_la_fenetre(self):
		lignes = O.get_besoins(self.recette, 600)["lignes"]
		bouteilles = next(line for line in lignes if line["article"] == self.bouteille)
		self.assertEqual((bouteilles["quantite"], bouteilles["disponible"]), (600.0, 500.0))
		options = O.get_ordre_options()
		self.assertIn(self.pf, [item["value"] for item in options["produits"]])
		self.assertIn(self.checklist, options["checklists"])
