# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Plan SCF, comptes par défaut, TVA, droit de timbre et migration d'une société existante."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from unicare.accounts.droit_timbre import appliquer_droit_timbre, calculer_timbre
from unicare.chart_of_accounts.chart_of_accounts import SCF_CHART, get_unicare_chart
from unicare.chart_of_accounts.patch import get_chart, get_charts_for_country
from unicare.setup.algeria import _iter_chart, _load, get_account, migrer_societe
from unicare.tests.test_bureau_commandes import _article
from unicare.tests.test_bureau_devis import _client


def _leaves_by_number(chart):
	out = {}
	for _name, child, _parent in _iter_chart(chart["tree"]):
		is_leaf = not any(isinstance(v, dict) for v in child.values())
		if child.get("account_number"):
			out[child["account_number"]] = (child, is_leaf)
	return out


def _societe(name, abbr, chart=SCF_CHART):
	if frappe.db.exists("Company", name):
		return frappe.get_doc("Company", name)
	return frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": name,
			"abbr": abbr,
			"country": "Algeria",
			"default_currency": "DZD",
			"create_chart_of_accounts_based_on": "Standard Template",
			"chart_of_accounts": chart,
		}
	).insert()


class TestPlanSCF(FrappeTestCase):
	"""Contrôles statiques du plan livré et des fichiers de taxes."""

	def setUp(self):
		self.chart = get_unicare_chart(SCF_CHART)
		self.accounts = _leaves_by_number(self.chart)

	def test_numeros_uniques_et_feuilles_utilisables(self):
		numbers = [c.get("account_number") for _n, c, _p in _iter_chart(self.chart["tree"]) if c.get("account_number")]
		self.assertEqual(len(numbers), len(set(numbers)))
		for number, (child, is_leaf) in self.accounts.items():
			if is_leaf:
				self.assertFalse(child.get("is_group"), number)

	def test_types_uniques(self):
		for account_type in ("Round Off", "Cash", "Temporary", "Stock Adjustment", "Cost of Goods Sold"):
			leaves = [n for n, (c, leaf) in self.accounts.items() if leaf and c.get("account_type") == account_type]
			self.assertEqual(len(leaves), 1, account_type)

	def test_defaults_et_taxes_pointent_vers_des_feuilles(self):
		numbers = list(self.chart["unicare_defaults"].values())
		taxes = _load("algeria_tax.json")["chart_of_accounts"][SCF_CHART]
		for templates in taxes.values():
			for template in templates:
				for row in template["taxes"]:
					numbers.append((row.get("account_head") or row.get("tax_type"))["account_number"])
		numbers.append(_load("algeria_fiscal.json")["compte"])
		for number in numbers:
			self.assertIn(number, self.accounts)
			self.assertTrue(self.accounts[number][1], number)

	def test_assistant_propose_le_scf_en_premier(self):
		charts = get_charts_for_country("Algeria", with_standard=True)
		self.assertEqual(charts[0], SCF_CHART)
		self.assertIn("Standard", charts)
		self.assertTrue(get_chart(SCF_CHART))
		self.assertNotIn(SCF_CHART, get_charts_for_country("France", with_standard=True))


class TestTimbre(FrappeTestCase):
	def test_bareme(self):
		self.assertEqual(calculer_timbre(10), 5)
		self.assertEqual(calculer_timbre(20000), 200)
		self.assertEqual(calculer_timbre(50000), 750)
		self.assertEqual(calculer_timbre(59500), 892.5)
		self.assertEqual(calculer_timbre(30500), 457.5)
		self.assertEqual(calculer_timbre(200000), 4000)
		self.assertEqual(calculer_timbre(0), 0)


class TestSocieteSCF(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.company = _societe("Essai SCF Unicare", "ESCF").name

	def test_comptes_par_defaut(self):
		company = frappe.get_doc("Company", self.company)
		attendus = {
			"default_receivable_account": "411",
			"default_payable_account": "401",
			"default_income_account": "700",
			"default_expense_account": "600",
			"round_off_account": "6581",
			"default_cash_account": "531",
			"stock_received_but_not_billed": "4081",
		}
		for fieldname, number in attendus.items():
			self.assertEqual(company.get(fieldname), get_account(self.company, number), fieldname)

	def test_modeles_tva_sur_les_comptes_du_plan(self):
		collectee = get_account(self.company, "44571")
		deductible = get_account(self.company, "44566")
		vente = frappe.get_doc("Sales Taxes and Charges Template", {"company": self.company, "title": "TVA 19%"})
		self.assertTrue(vente.is_default)
		self.assertEqual([(t.account_head, flt(t.rate)) for t in vente.taxes], [(collectee, 19)])
		achat = frappe.get_doc(
			"Purchase Taxes and Charges Template", {"company": self.company, "title": "TVA déductible 9%"}
		)
		self.assertEqual([(t.account_head, flt(t.rate)) for t in achat.taxes], [(deductible, 9)])
		article = frappe.get_doc("Item Tax Template", {"company": self.company, "title": "TVA 19%"})
		self.assertEqual({t.tax_type for t in article.taxes}, {collectee, deductible})
		# Aucun compte « TVA 19% » créé à côté du plan.
		self.assertFalse(frappe.db.exists("Account", {"company": self.company, "account_name": "TVA 19%"}))

	def _facture(self, montant, especes):
		item = frappe.db.get_value("Item", {"is_stock_item": 0, "disabled": 0, "has_variants": 0}) or _article(
			"Prestation essai timbre", 1000, stock=False
		)
		customer = frappe.db.get_value("Customer", {"disabled": 0}) or _client()
		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": self.company,
				"customer": customer,
				"currency": "DZD",
				"conversion_rate": 1,
				"debit_to": get_account(self.company, "411"),
				"items": [
					{
						"item_code": item,
						"qty": 1,
						"rate": montant,
						"income_account": get_account(self.company, "700"),
						"cost_center": frappe.get_cached_value("Company", self.company, "cost_center"),
					}
				],
			}
		)
		invoice.unicare_paiement_especes = especes
		invoice.set_missing_values()
		# Hors TVA : seul le timbre doit apparaître.
		invoice.taxes_and_charges = None
		invoice.set("taxes", [])
		invoice.calculate_taxes_and_totals()
		appliquer_droit_timbre(invoice)
		return invoice

	def test_timbre_sur_facture_especes(self):
		timbre = get_account(self.company, "44575")
		invoice = self._facture(50000, 1)
		lignes = [t for t in invoice.taxes if t.account_head == timbre]
		self.assertEqual(len(lignes), 1)
		self.assertEqual(flt(lignes[0].tax_amount), 750)
		self.assertEqual(flt(invoice.grand_total), 50750)

		# Recalcul : toujours une seule ligne, même montant.
		appliquer_droit_timbre(invoice)
		self.assertEqual(len([t for t in invoice.taxes if t.account_head == timbre]), 1)
		self.assertEqual(flt(invoice.grand_total), 50750)

		invoice.unicare_paiement_especes = 0
		appliquer_droit_timbre(invoice)
		self.assertFalse([t for t in invoice.taxes if t.account_head == timbre])
		self.assertEqual(flt(invoice.grand_total), 50000)

	def test_pas_de_timbre_sans_especes(self):
		invoice = self._facture(10, 0)
		self.assertFalse(invoice.taxes)
		invoice = self._facture(10, 1)
		self.assertEqual(flt(invoice.grand_total), 15)


class TestMigration(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.company = _societe("Essai Migration Standard", "EMIG", chart="Standard with Numbers").name

	def test_migration_sans_ecritures(self):
		# Simulation d'abord : rien n'est écrit.
		avant = frappe.db.count("Account", {"company": self.company})
		report = migrer_societe(self.company)
		self.assertEqual(frappe.db.count("Account", {"company": self.company}), avant)
		self.assertGreater(report["comptes_crees"], 200)
		self.assertTrue(report["anciens_comptes"]["supprimes"])

		report = migrer_societe(self.company, dry_run=0, commit=0)
		company = frappe.get_doc("Company", self.company)
		self.assertEqual(company.chart_of_accounts, SCF_CHART)
		self.assertEqual(company.default_receivable_account, get_account(self.company, "411"))
		self.assertEqual(company.round_off_account, get_account(self.company, "6581"))
		self.assertFalse(report["anciens_comptes"]["a_virer_par_ecriture"])
		# Plus aucun compte actif de l'ancien plan.
		actifs = frappe.get_all(
			"Account",
			filters={"company": self.company, "disabled": 0},
			fields=["account_number", "parent_account"],
		)
		self.assertTrue(all(a.account_number or not a.parent_account for a in actifs))
		self.assertTrue(
			frappe.db.exists("Sales Taxes and Charges Template", {"company": self.company, "title": "TVA 19%"})
		)
		# Relance : idempotente.
		report = migrer_societe(self.company, dry_run=0, commit=0)
		self.assertEqual(report["comptes_crees"], 0)
