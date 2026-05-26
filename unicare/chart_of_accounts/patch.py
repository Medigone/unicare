import json
from pathlib import Path

import frappe
from frappe import _

from unicare.chart_of_accounts.chart_of_accounts import (
	get_unicare_chart_names,
	get_unicare_chart_tree,
)

import erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts as coa_module
import erpnext.setup.setup_wizard.operations.taxes_setup as taxes_setup_module

_original_get_charts_for_country = coa_module.get_charts_for_country
_original_get_chart = coa_module.get_chart
_original_setup_taxes_and_charges = taxes_setup_module.setup_taxes_and_charges

_patches_applied = False


@frappe.whitelist()
def get_charts_for_country(country, with_standard=False):
	charts = list(_original_get_charts_for_country(country, with_standard=False))

	for chart_name in get_unicare_chart_names(country, with_standard=False):
		if chart_name not in charts:
			charts.append(chart_name)

	if len(charts) != 1 or with_standard:
		for standard_chart in ("Standard", "Standard with Numbers"):
			if standard_chart not in charts:
				charts.append(standard_chart)

	return charts


@frappe.whitelist()
def get_chart(chart_template, existing_company=None):
	chart = _original_get_chart(chart_template, existing_company)
	if chart:
		return chart

	return get_unicare_chart_tree(chart_template)


def setup_taxes_and_charges(company_name, country):
	if country == "Algeria":
		return _setup_algeria_taxes_and_charges(company_name, country)

	return _original_setup_taxes_and_charges(company_name, country)


def apply_patches():
	global _patches_applied
	if _patches_applied:
		return

	coa_module.get_charts_for_country = get_charts_for_country
	coa_module.get_chart = get_chart
	taxes_setup_module.setup_taxes_and_charges = setup_taxes_and_charges

	_patches_applied = True


def _setup_algeria_taxes_and_charges(company_name, country):
	from erpnext.setup.setup_wizard.operations.taxes_setup import (
		from_detailed_data,
		simple_to_detailed,
		update_regional_tax_settings,
	)

	if not frappe.db.exists("Company", company_name):
		frappe.throw(_("Company {} does not exist yet. Taxes setup aborted.").format(company_name))

	tax_file = Path(__file__).resolve().parent.parent / "setup" / "data" / "algeria_tax.json"
	with open(tax_file) as json_file:
		country_wise_tax = json.load(json_file)

	from_detailed_data(company_name, simple_to_detailed(country_wise_tax))
	update_regional_tax_settings(country, company_name)
