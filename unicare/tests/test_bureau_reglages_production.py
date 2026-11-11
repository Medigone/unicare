# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase

from unicare.api import bureau_reglages_production as R


class TestReglagesProduction(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_checklists(self):
		reglages = R.save_checklist(values=json.dumps({"titre": "Checklist essai réglages", "lignes": [{"controle": "Ligne propre"}, {"controle": "  "}, {"controle": "Gants", "obligatoire": False}]}))
		checklist = next(row for row in reglages["checklists"] if row["name"] == "Checklist essai réglages")
		self.assertEqual(checklist["lignes"], [{"controle": "Ligne propre", "obligatoire": True}, {"controle": "Gants", "obligatoire": False}])
		with self.assertRaises(frappe.ValidationError):
			R.save_checklist(values=json.dumps({"titre": "Checklist essai réglages", "lignes": [{"controle": "X"}]}))
		with self.assertRaises(frappe.ValidationError):
			R.save_checklist(checklist["name"], checklist["modified"], json.dumps({"lignes": []}))
		reglages = R.save_checklist(checklist["name"], checklist["modified"], json.dumps({"actif": False, "lignes": [{"controle": "Ligne propre"}]}))
		checklist = next(row for row in reglages["checklists"] if row["name"] == "Checklist essai réglages")
		self.assertFalse(checklist["actif"])
		reglages = R.delete_checklist(checklist["name"], checklist["modified"])
		self.assertNotIn("Checklist essai réglages", [row["name"] for row in reglages["checklists"]])

	def test_parametres(self):
		reglages = R.get_reglages()
		parametres = reglages["parametres"]
		values = {field: parametres[field] for field in R.DEPOTS}
		with self.assertRaises(frappe.ValidationError):
			R.save_parametres(parametres["modified"], json.dumps({**values, "warehouse_pf": "Dépôt imaginaire", "tolerance": 10}))
		reglages = R.save_parametres(parametres["modified"], json.dumps({**values, "tolerance": 7.5}))
		self.assertEqual(reglages["parametres"]["tolerance"], 7.5)
		with self.assertRaises(frappe.TimestampMismatchError):
			R.save_parametres(parametres["modified"], json.dumps({**values, "tolerance": 8}))
