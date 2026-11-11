# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from unicare.api import bureau_accueil as A
from unicare.api import bureau_mouvements as M
from unicare.tests.achats_outils import article


class TestAccueil(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.local.lang = "fr"

	def tearDown(self):
		frappe.db.rollback()

	def test_journee(self):
		code = article("Vrac essai accueil", stock=True, lots=True)
		frappe.db.set_value("Item", code, "valuation_rate", 10)
		entree = M.create_mouvement(json.dumps({"nature": "entree", "cible": "Magasins - U", "lignes": [{"article": code, "quantite": 4, "lot": "LOT-ACCUEIL", "peremption": add_days(today(), 10)}]}))["name"]
		M.validate_mouvement(entree, M.get_mouvement(entree)["modified"])
		frappe.db.set_value("Batch", "LOT-ACCUEIL", "expiry_date", add_days(today(), -1))
		brouillon = M.create_mouvement(json.dumps({"nature": "transfert", "source": "Magasins - U", "cible": "Production - U", "lignes": [{"article": code, "quantite": 1, "lot": "LOT-ACCUEIL"}]}))["name"]
		frappe.get_doc({"doctype": "Notification Log", "for_user": "Administrator", "type": "Mention", "subject": "<b>Samia</b> vous a mentionné", "document_type": "Stock Entry", "document_name": brouillon}).insert(ignore_permissions=True)

		accueil = A.get_accueil()
		retard = [item for item in accueil["a_faire"]["retard"] if "LOT-ACCUEIL" in item["titre"]]
		# Le lot périmé est déjà dans un mouvement en brouillon : la ligne mène à ce mouvement, sans doublon plus bas.
		self.assertEqual((retard[0]["module"], retard[0]["action"], retard[0]["name"]), ("Stock", "Vérifier et valider", brouillon))
		self.assertNotIn(brouillon, [item["name"] for item in accueil["a_faire"]["a_valider"]])
		mention = next(item for item in accueil["pour_vous"] if item["document"] == brouillon)
		self.assertEqual((mention["type"], mention["texte"], mention["fiche"], mention["lu"]), ("mention", "Samia vous a mentionné", "MouvementFiche", False))
		self.assertGreaterEqual(accueil["non_lus"], 1)
		self.assertTrue(any(row["name"] == brouillon for row in accueil["recents"]))
		self.assertIn("Valeur du stock", [kpi["label"] for kpi in accueil["mois"]])

		A.marquer_lus()
		self.assertEqual(A.get_accueil()["non_lus"], 0)
