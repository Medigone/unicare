# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_mouvements as M
from unicare.api import bureau_perimes as P
from unicare.conditionnement.stock import get_parametres
from unicare.tests.achats_outils import article


class TestMiseAuRebut(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		p = get_parametres()
		self.magasin, self.atelier, self.rebus = "Magasins - U", p.warehouse_atelier, p.warehouse_rebuts
		self.code = article("Vrac essai mise au rebut", stock=True, lots=True)
		frappe.db.set_value("Item", self.code, "valuation_rate", 10)
		lignes = [
			{"article": self.code, "quantite": 8, "lot": "LOT-REBUT-VIEUX", "peremption": add_days(today(), 30)},
			{"article": self.code, "quantite": 5, "lot": "LOT-REBUT-BON", "peremption": add_days(today(), 300)},
		]
		for cible in (self.magasin, self.atelier):
			name = M.create_mouvement(json.dumps({"nature": "entree", "cible": cible, "lignes": lignes}))["name"]
			M.validate_mouvement(name, M.get_mouvement(name)["modified"])
		frappe.db.set_value("Batch", "LOT-REBUT-VIEUX", "expiry_date", add_days(today(), -3))

	def tearDown(self):
		frappe.db.rollback()

	def test_brouillon_prepare_une_fois(self):
		perimes = [row for row in P.lots_perimes() if row[0] == "LOT-REBUT-VIEUX"]
		# L'atelier est laissé à la production ; le bon lot n'est pas concerné.
		self.assertEqual(perimes, [("LOT-REBUT-VIEUX", self.code, self.magasin, 8.0)])
		self.assertEqual(P.etat_lot("LOT-REBUT-VIEUX")["a_mettre_au_rebut"], True)
		self.assertEqual(P.etat_lot("LOT-REBUT-BON")["a_mettre_au_rebut"], False)

		name = P.preparer_mise_au_rebut("LOT-REBUT-VIEUX")["name"]
		doc = frappe.get_doc("Stock Entry", name)
		self.assertEqual((doc.docstatus, doc.purpose, doc.from_warehouse, doc.to_warehouse), (0, "Material Transfer", self.magasin, self.rebus))
		self.assertEqual([(row.batch_no, row.qty) for row in doc.items], [("LOT-REBUT-VIEUX", 8)])
		self.assertEqual(P.etat_lot("LOT-REBUT-VIEUX")["mise_au_rebut"], name)

		# Déjà prévu : ni la tâche du jour ni un second clic n'en créent un autre.
		self.assertNotIn(name, P.preparer())
		self.assertFalse([n for n in P.preparer() if "LOT-REBUT-VIEUX" in str(frappe.get_doc("Stock Entry", n).items[0].batch_no)])
		self.assertEqual(P.preparer_mise_au_rebut("LOT-REBUT-VIEUX")["name"], name)

		fiche = M.get_mouvement(name)
		self.assertEqual(fiche["blocked"], [])
		M.validate_mouvement(name, fiche["modified"])
		self.assertEqual(P.etat_lot("LOT-REBUT-VIEUX")["a_mettre_au_rebut"], False)
