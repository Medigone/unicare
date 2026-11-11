# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_bulk, bureau_ordres, bureau_recettes
from unicare.tests.achats_outils import article

R = bureau_recettes


def _type(item, kind):
	frappe.db.set_value("Item", item, {"custom_type_conditionnement": kind, "has_batch_no": 1 if kind in ("Fût", "Produit fini") else 0})


class TestRecettes(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.fut = article("Vrac essai recettes", stock=True)
		_type(self.fut, "Fût")
		self.flacon = article("Flacon essai recettes", stock=True)
		_type(self.flacon, "Conditionnement")
		self.pf = article("Produit essai recettes", stock=True)
		_type(self.pf, "Produit fini")
		self.checklist = frappe.get_doc({"doctype": "Checklist Ordre Conditionnement", "titre": "Checklist essai recettes", "actif": 1, "lignes": [{"controle": "Ligne propre", "obligatoire": 1}]}).insert().name

	def tearDown(self):
		frappe.db.rollback()

	def _values(self, **extra):
		return {
			"produit": self.pf,
			"quantite_base": 1,
			"rendement": 98,
			"ingredients": [{"article": self.fut, "quantite": 0.25}, {"article": self.flacon, "quantite": 1}],
			**extra,
		}

	def test_cycle(self):
		name = R.create_recette(json.dumps(self._values()))["name"]
		fiche = R.get_recette(name)
		self.assertEqual((fiche["produit"], fiche["actif"], fiche["rendement"]), (self.pf, True, 98.0))
		self.assertEqual([row["type"] for row in fiche["ingredients"]], ["Fût", "Conditionnement"])
		self.assertIn("supprimer", fiche["actions"])
		self.assertIn(name, R.get_recettes()["names"])

		# Une recette sans fût est refusée par le doctype.
		with self.assertRaises(frappe.ValidationError):
			R.update_recette(name, fiche["modified"], json.dumps(self._values(ingredients=[{"article": self.flacon, "quantite": 1}])))
		with self.assertRaises(frappe.ValidationError):
			R.create_recette(json.dumps(self._values(ingredients=[{"article": self.pf, "quantite": 1}])))

		fiche = R.update_recette(name, fiche["modified"], json.dumps(self._values(quantite_base=10)))
		self.assertEqual(fiche["quantite_base"], 10)

		# Utilisée par un ordre : plus de suppression, mais on peut la désactiver.
		bureau_ordres.create_ordre(json.dumps({"recette": name, "quantite": 20, "checklist": self.checklist}))
		fiche = R.get_recette(name)
		self.assertNotIn("supprimer", fiche["actions"])
		self.assertEqual(fiche["nb_ordres"], 1)
		fiche = R.set_actif(name, fiche["modified"], 0)
		self.assertFalse(fiche["actif"])
		self.assertIn(name, R.get_recettes(view="inactives")["names"])
		result = bureau_bulk.bulk_delete(R.RECETTE, json.dumps([{"name": name, "modified": fiche["modified"]}]))
		self.assertTrue(frappe.db.exists(R.RECETTE, name), result)

		copie = R.dupliquer(name)["name"]
		self.assertTrue(R.get_recette(copie)["actif"])
		copie_fiche = R.get_recette(copie)
		R.delete_recette(copie, copie_fiche["modified"])
		self.assertFalse(frappe.db.exists(R.RECETTE, copie))

	def test_options(self):
		options = R.get_recette_options()
		self.assertIn(self.pf, [item["value"] for item in options["produits"]])
		self.assertIn(self.fut, [item["value"] for item in options["matieres"]])
		self.assertNotIn(self.pf, [item["value"] for item in options["matieres"]])
