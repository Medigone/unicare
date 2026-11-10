"""Branche les plans et les taxes Unicare dans ERPNext.

ERPNext ne lit les plans comptables que dans son propre dossier : on remplace ses fonctions dans les modules qui
les appellent. Les appels du navigateur passent par override_whitelisted_methods (hooks.py) ; les appels Python
(création de la société, y compris dans l'assistant exécuté en tâche de fond) passent par apply_patches(), appelé
au before_validate de Company (unicare.chart_of_accounts.company_hooks).
"""

import frappe

from unicare.chart_of_accounts.chart_of_accounts import get_unicare_chart_names, get_unicare_chart_tree

STANDARD_CHARTS = ("Standard", "Standard with Numbers")


def _coa_module():
	import erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts as coa_module

	return coa_module


def _taxes_module():
	import erpnext.setup.setup_wizard.operations.taxes_setup as taxes_module

	return taxes_module


def _original(module, name):
	"""La fonction ERPNext d'origine, même après le remplacement."""
	fn = getattr(module, name)
	return getattr(fn, "_unicare_original", fn)


@frappe.whitelist()
def get_charts_for_country(country, with_standard=False):
	"""Plans Unicare en premier : l'assistant présélectionne la première option."""
	charts = get_unicare_chart_names(country)
	for chart in _original(_coa_module(), "get_charts_for_country")(country, with_standard=False):
		if chart not in charts and chart not in STANDARD_CHARTS:
			charts.append(chart)

	if len(charts) != 1 or frappe.utils.cint(with_standard):
		charts += [chart for chart in STANDARD_CHARTS if chart not in charts]

	return charts


@frappe.whitelist()
def get_chart(chart_template, existing_company=None):
	return _original(_coa_module(), "get_chart")(chart_template, existing_company) or get_unicare_chart_tree(
		chart_template
	)


def setup_taxes_and_charges(company_name: str, country: str):
	if country == "Algeria":
		from unicare.setup.algeria import creer_taxes

		return creer_taxes(company_name)

	return _original(_taxes_module(), "setup_taxes_and_charges")(company_name, country)


def _replace(module, name, fn):
	current = getattr(module, name)
	if getattr(current, "_unicare_original", None):
		return
	fn._unicare_original = current
	setattr(module, name, fn)


def apply_patches():
	"""Idempotent : remplace les fonctions ERPNext là où elles sont appelées."""
	import erpnext.setup.doctype.company.company as company_module

	coa_module = _coa_module()
	_replace(coa_module, "get_charts_for_country", get_charts_for_country)
	_replace(coa_module, "get_chart", get_chart)
	_replace(_taxes_module(), "setup_taxes_and_charges", setup_taxes_and_charges)
	# company.py importe la fonction par son nom : il faut aussi la remplacer dans ce module.
	_replace(company_module, "setup_taxes_and_charges", setup_taxes_and_charges)
