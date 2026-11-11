# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from unicare.api import bureau_bulk, bureau_mouvements, bureau_stock
from unicare.tests.achats_outils import article

M = bureau_mouvements


def _stock(item, depot):
	return flt(frappe.db.get_value("Bin", {"item_code": item, "warehouse": depot}, "actual_qty"))


class TestVuesMouvements(FrappeTestCase):
	def test_natures_et_vues(self):
		self.assertEqual(M.nature_of("Material Transfer"), "transfert")
		self.assertEqual(M.nature_of("Repack"), "production")
		row = {"status": "Submitted", "nature": "sortie", "ordre": None}
		self.assertTrue(M.in_view("sorties", row))
		self.assertFalse(M.in_view("sorties", {**row, "status": "Cancelled"}))
		self.assertTrue(M.in_view("ordres", {**row, "ordre": "OC-1"}))


class TestMouvements(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.magasin, self.production = "Magasins - U", "Production - U"
		self.item = article("Matière essai mouvements", stock=True, lots=True)
		self.simple = article("Carton essai mouvements", stock=True)
		frappe.db.set_value("Item", [self.item, self.simple], "valuation_rate", 50)

	def tearDown(self):
		frappe.db.rollback()

	def _create(self, nature, lignes, **extra):
		values = {"nature": nature, "lignes": lignes, **extra}
		name = M.create_mouvement(json.dumps(values))["name"]
		return M.get_mouvement(name)

	def test_entree_transfert_sortie(self):
		entree = self._create(
			"entree",
			[
				{"article": self.item, "quantite": 20, "lot": "LOT-MVT-ESSAI", "peremption": add_days(today(), 200)},
				{"article": self.simple, "quantite": 30},
			],
			cible=self.magasin,
			remarque="Stock initial",
		)
		self.assertEqual(entree["nature"], "entree")
		self.assertEqual(entree["blocked"], [])
		self.assertEqual(str(frappe.db.get_value("Batch", "LOT-MVT-ESSAI", "expiry_date")), add_days(today(), 200))
		entree = M.validate_mouvement(entree["name"], entree["modified"])
		self.assertEqual(_stock(self.item, self.magasin), 20)
		self.assertIn({"lot": "LOT-MVT-ESSAI", "qty": 20.0, "peremption": add_days(today(), 200), "perime": False}, bureau_stock.lots_disponibles(self.item, self.magasin)[self.magasin])

		# Transfert : au-delà du disponible, il est bloqué ; à 15, il passe.
		transfert = self._create("transfert", [{"article": self.item, "quantite": 25, "lot": "LOT-MVT-ESSAI"}], source=self.magasin, cible=self.production)
		self.assertTrue(any("disponible" in reason for reason in transfert["blocked"]))
		with self.assertRaises(frappe.ValidationError):
			M.validate_mouvement(transfert["name"], transfert["modified"])
		transfert = M.update_mouvement(
			transfert["name"], transfert["modified"], json.dumps({"source": self.magasin, "cible": self.production, "lignes": [{"article": self.item, "quantite": 15, "lot": "LOT-MVT-ESSAI"}]})
		)
		M.validate_mouvement(transfert["name"], transfert["modified"])
		self.assertEqual(_stock(self.item, self.magasin), 5)
		self.assertEqual(_stock(self.item, self.production), 15)

		sortie = self._create("sortie", [{"article": self.simple, "quantite": 4}], source=self.magasin, remarque="Casse")
		sortie = M.validate_mouvement(sortie["name"], sortie["modified"])
		self.assertEqual(_stock(self.simple, self.magasin), 26)
		self.assertEqual(sortie["lignes"][0]["source"], self.magasin)

	def test_refus_de_saisie(self):
		with self.assertRaises(frappe.ValidationError):
			self._create("transfert", [{"article": self.simple, "quantite": 1}], source=self.magasin, cible=self.magasin)
		with self.assertRaises(frappe.ValidationError):
			self._create("sortie", [{"article": self.simple, "quantite": 1}], source="Dépôt inconnu")
		with self.assertRaises(frappe.ValidationError):
			self._create("inventaire", [{"article": self.simple, "quantite": 1}])
		sans_lot = self._create("sortie", [{"article": self.item, "quantite": 1}], source=self.magasin)
		self.assertTrue(any("lot" in reason for reason in sans_lot["blocked"]))

	def test_annuler_refaire_supprimer(self):
		entree = self._create("entree", [{"article": self.simple, "quantite": 10}], cible=self.magasin)
		entree = M.validate_mouvement(entree["name"], entree["modified"])
		entree = M.cancel_mouvement(entree["name"], entree["modified"])
		self.assertEqual(_stock(self.simple, self.magasin), 0)
		# Les écritures de stock annulées restent (piste d'audit) : ERPNext ne laisse pas supprimer, le bureau ne le propose pas.
		self.assertEqual(entree["actions"], ["nouvelle_version"])
		version = M.create_version(entree["name"], entree["modified"])
		self.assertEqual(version["name"], f"{entree['name']}-1")
		self.assertEqual(M.get_mouvement(version["name"])["lignes"][0]["cible"], self.magasin)
		M.delete_mouvement(version["name"], M.get_mouvement(version["name"])["modified"])
		self.assertFalse(frappe.db.exists("Stock Entry", version["name"]))
		with self.assertRaises(frappe.PermissionError):
			M.delete_mouvement(entree["name"], M.get_mouvement(entree["name"])["modified"])

	def test_mouvement_d_ordre_en_lecture_seule(self):
		name = frappe.db.get_value("Stock Entry", {"custom_ordre_conditionnement": ["is", "set"], "docstatus": 1}, "name")
		if not name:
			return
		fiche = M.get_mouvement(name)
		self.assertTrue(fiche["depuis_ordre"])
		self.assertEqual(fiche["actions"], [])
		with self.assertRaises(frappe.PermissionError):
			M.cancel_mouvement(name, fiche["modified"])
		result = bureau_bulk.bulk_delete("Stock Entry", json.dumps([{"name": name, "modified": fiche["modified"]}]))
		self.assertEqual(result["done"], [])


class TestRechercheArticlesStock(FrappeTestCase):
	def test_mots_dans_le_desordre_et_stock_du_depot(self):
		frappe.set_user("Administrator")
		try:
			code = article("Bidon essai recherche stock 20 L", stock=True)
			found = M.search_stock_articles("20 bidon", "Magasins - U")
			self.assertEqual([row["name"] for row in found], [code])
			self.assertEqual(found[0]["stock"], 0)
			self.assertIsNone(M.search_stock_articles("20 bidon")[0]["stock"])
		finally:
			frappe.db.rollback()


class TestLotPerime(FrappeTestCase):
	def test_un_lot_perime_se_met_au_rebut(self):
		frappe.set_user("Administrator")
		try:
			code = article("Vrac essai lot périmé", stock=True, lots=True)
			frappe.db.set_value("Item", code, "valuation_rate", 10)
			entree = M.create_mouvement(json.dumps({"nature": "entree", "cible": "Magasins - U", "lignes": [{"article": code, "quantite": 12, "lot": "LOT-ESSAI-PERIME", "peremption": add_days(today(), 30)}]}))["name"]
			M.validate_mouvement(entree, M.get_mouvement(entree)["modified"])
			frappe.db.set_value("Batch", "LOT-ESSAI-PERIME", "expiry_date", add_days(today(), -5))
			# Ailleurs (ventes, production), le lot périmé n'est plus proposé ; ici, il l'est, marqué.
			self.assertEqual(bureau_stock.lots_disponibles(code, "Magasins - U"), {})
			lots = M.get_lots_article(code, "Magasins - U")
			self.assertEqual([(lot["lot"], lot["qty"], lot["perime"]) for lot in lots], [("LOT-ESSAI-PERIME", 12.0, True)])
			transfert = M.create_mouvement(json.dumps({"nature": "transfert", "source": "Magasins - U", "cible": "Rebus - U", "lignes": [{"article": code, "quantite": 12, "lot": "LOT-ESSAI-PERIME"}]}))["name"]
			fiche = M.get_mouvement(transfert)
			self.assertEqual(fiche["blocked"], [])
			M.validate_mouvement(transfert, fiche["modified"])
			self.assertEqual(_stock(code, "Rebus - U"), 12)
		finally:
			frappe.db.rollback()
