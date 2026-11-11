# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from unicare.api import bureau_inventaires, bureau_mouvements
from unicare.tests.achats_outils import article

I = bureau_inventaires
M = bureau_mouvements


class TestInventaires(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.depot = "Travaux en cours - U"
		self.groupe = "Groupe essai inventaire"
		if not frappe.db.exists("Item Group", self.groupe):
			frappe.get_doc({"doctype": "Item Group", "item_group_name": self.groupe, "parent_item_group": frappe.db.get_value("Item Group", {"is_group": 1}, "name")}).insert()
		self.simple = article("Flacon essai inventaire", stock=True)
		self.lot_item = article("Vrac essai inventaire", stock=True, lots=True)
		frappe.db.set_value("Item", [self.simple, self.lot_item], {"item_group": self.groupe, "valuation_rate": 10})
		entree = M.create_mouvement(
			json.dumps(
				{
					"nature": "entree",
					"cible": self.depot,
					"lignes": [{"article": self.simple, "quantite": 40}, {"article": self.lot_item, "quantite": 12, "lot": "LOT-INV-ESSAI"}],
				}
			)
		)["name"]
		fiche = M.get_mouvement(entree)
		M.validate_mouvement(entree, fiche["modified"])

	def tearDown(self):
		frappe.db.rollback()

	def test_feuille_comptage_ecarts_validation(self):
		name = I.create_inventaire(json.dumps({"depot": self.depot, "groupe": self.groupe}))["name"]
		fiche = I.get_inventaire(name)
		# La feuille garde toutes les lignes, au théorique, et sans écart elle ne se valide pas.
		by_key = {(line["article"], line["lot"]): line for line in fiche["lignes"]}
		self.assertEqual(by_key[(self.simple, None)]["theorique"], 40)
		self.assertEqual(by_key[(self.lot_item, "LOT-INV-ESSAI")]["theorique"], 12)
		self.assertTrue(fiche["blocked"])
		with self.assertRaises(frappe.ValidationError):
			I.validate_inventaire(name, fiche["modified"])
		fiche = I.compter(
			name,
			fiche["modified"],
			json.dumps([{"name": by_key[(self.simple, None)]["name"], "quantite": 37}]),
		)
		self.assertEqual(fiche["resume"]["ecarts"], 1)
		self.assertEqual(fiche["resume"]["moins"], -3)
		self.assertEqual(fiche["resume"]["valeur"], -30)
		self.assertEqual(len(fiche["lignes"]), 2)
		fiche = I.validate_inventaire(name, fiche["modified"])
		self.assertEqual(fiche["status"], "Submitted")
		self.assertEqual(flt(frappe.db.get_value("Bin", {"item_code": self.simple, "warehouse": self.depot}, "actual_qty")), 37)
		# ERPNext n'a gardé que la ligne avec écart.
		self.assertEqual(len(fiche["lignes"]), 1)
		fiche = I.cancel_inventaire(name, fiche["modified"])
		self.assertEqual(flt(frappe.db.get_value("Bin", {"item_code": self.simple, "warehouse": self.depot}, "actual_qty")), 40)
		self.assertEqual(fiche["actions"], ["nouvelle_version"])
		version = I.create_version(name, fiche["modified"])
		self.assertEqual(I.get_inventaire(version["name"])["lignes"][0]["compte"], 37)

	def test_ajout_et_retrait_de_lignes(self):
		name = I.create_inventaire(json.dumps({"depot": self.depot, "groupe": self.groupe}))["name"]
		fiche = I.get_inventaire(name)
		lot_line = next(line for line in fiche["lignes"] if line["lot"])
		fiche = I.compter(
			name,
			fiche["modified"],
			ajouts=json.dumps([{"article": self.lot_item, "lot": "LOT-INV-TROUVE", "quantite": 2}]),
			retirer=json.dumps([lot_line["name"]]),
		)
		self.assertEqual({line["lot"] for line in fiche["lignes"]}, {None, "LOT-INV-TROUVE"})
		trouve = next(line for line in fiche["lignes"] if line["lot"] == "LOT-INV-TROUVE")
		self.assertEqual((trouve["theorique"], trouve["ecart"]), (0, 2))
		with self.assertRaises(frappe.ValidationError):
			I.compter(name, fiche["modified"], ajouts=json.dumps([{"article": self.lot_item, "quantite": 1}]))
		with self.assertRaises(frappe.ValidationError):
			I.compter(name, fiche["modified"], json.dumps([{"name": trouve["name"], "quantite": -1}]))
		I.delete_inventaire(name, fiche["modified"])
		self.assertFalse(frappe.db.exists("Stock Reconciliation", name))

	def test_refus(self):
		with self.assertRaises(frappe.ValidationError):
			I.create_inventaire(json.dumps({"depot": "Dépôt inconnu"}))
		with self.assertRaises(frappe.ValidationError):
			I.get_inventaires(view="inconnue")
