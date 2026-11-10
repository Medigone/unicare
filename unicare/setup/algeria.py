"""Comptabilité algérienne : plan SCF, comptes par défaut de la société et modèles de TVA.

Nouveau site : tout se fait à la création de la société (assistant d'installation), via les hooks de Company.
Site déjà installé : migrer_societe, à lancer à la main, d'abord en simulation :

	bench --site <site> execute unicare.setup.algeria.migrer_societe --kwargs '{"company": "Unicare"}'
	bench --site <site> execute unicare.setup.algeria.migrer_societe --kwargs '{"company": "Unicare", "dry_run": 0}'
"""

import json
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint, flt

from unicare.chart_of_accounts.chart_of_accounts import SCF_CHART, get_unicare_chart, get_unicare_defaults

DATA_DIR = Path(__file__).parent / "data"

TAX_TEMPLATE_DOCTYPES = (
	"Sales Taxes and Charges Template",
	"Purchase Taxes and Charges Template",
	"Item Tax Template",
)

STOCK_ACCOUNT_TYPES = ("Stock", "Stock Received But Not Billed", "Stock Adjustment")

# Champs de paramétrage (hors transactions) qui pointent vers un compte, re-pointés par la migration.
ACCOUNT_REFERENCES = {
	"Item Default": ("income_account", "expense_account"),
	"Warehouse": ("account",),
	"Mode of Payment Account": ("default_account",),
	"Party Account": ("account", "advance_account"),
	"Asset Category Account": (
		"fixed_asset_account",
		"accumulated_depreciation_account",
		"depreciation_expense_account",
		"capital_work_in_progress_account",
	),
	"POS Profile": ("write_off_account", "account_for_change_amount", "income_account", "expense_account"),
	"Bank Account": ("account",),
}


def _load(fname):
	with open(DATA_DIR / fname, encoding="utf-8") as f:
		return json.load(f)


def get_account(company, account_number):
	"""Le compte de détail portant ce numéro dans la société, ou None."""
	return frappe.db.get_value(
		"Account", {"company": company, "account_number": account_number, "is_group": 0}, "name"
	)


# --- Création de la société -----------------------------------------------------------------------------


def appliquer_defaults(company, force=False):
	"""Comptes par défaut de la société selon unicare_defaults du plan. force : remplace les valeurs déjà posées."""
	doc = company if not isinstance(company, str) else frappe.get_doc("Company", company)
	defaults = get_unicare_defaults(doc.chart_of_accounts)
	values = {}
	for fieldname, account_number in defaults.items():
		account = get_account(doc.name, account_number)
		if account and (force or not doc.get(fieldname)) and doc.get(fieldname) != account:
			values[fieldname] = account

	if values:
		doc.db_set(values)
	return values


def creer_taxes(company):
	"""Modèles de TVA (ventes, achats, articles) ; existants laissés tels quels (même titre)."""
	from erpnext.setup.setup_wizard.operations.taxes_setup import from_detailed_data

	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {} does not exist yet. Taxes setup aborted.").format(company))

	from_detailed_data(company, _load("algeria_tax.json"))


def bareme_timbre():
	return _load("algeria_fiscal.json")


# --- Migration d'une société existante ------------------------------------------------------------------


def _iter_chart(tree, parent_number=None):
	"""(nom, données, nœud parent) dans l'ordre parent avant enfants ; les racines n'ont pas de parent."""
	for name, child in tree.items():
		if not isinstance(child, dict):
			continue
		yield name, child, parent_number
		yield from _iter_chart(
			{k: v for k, v in child.items() if isinstance(v, dict)},
			child.get("account_number") or ("root", name),
		)


def _is_group(child):
	return cint(child.get("is_group")) or any(isinstance(v, dict) for v in child.values())


def _balance(account):
	return flt(
		frappe.db.sql(
			"select sum(debit) - sum(credit) from `tabGL Entry` where account=%s and is_cancelled=0", account
		)[0][0]
	)


def _creer_plan(company, chart, existing_accounts, dry_run):
	"""Crée les comptes SCF manquants. Renvoie {numéro ou ("root", nom): nom du compte}."""
	created, mapping = [], {}
	currency = frappe.get_cached_value("Company", company, "default_currency")
	for name, child, parent_key in _iter_chart(chart["tree"]):
		root_type = child.get("root_type") if parent_key is None else None
		key = child.get("account_number") or ("root", name)
		if child.get("account_number"):
			found = frappe.db.get_value(
				"Account",
				{"company": company, "account_number": child["account_number"], "name": ("not in", existing_accounts)},
			)
		else:
			found = frappe.db.get_value(
				"Account",
				{
					"company": company,
					"account_name": name,
					"parent_account": ("is", "not set"),
					"name": ("not in", existing_accounts),
				},
			)
		if found:
			mapping[key] = found
			continue

		created.append(f"{child.get('account_number') or ''} {name}".strip())
		if dry_run:
			mapping[key] = name
			continue

		parent = mapping.get(parent_key) if parent_key else None
		parent_root_type = frappe.db.get_value("Account", parent, "root_type") if parent else None
		root_type = root_type or parent_root_type
		account = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": name,
				"account_number": child.get("account_number") or "",
				"company": company,
				"parent_account": parent,
				"is_group": _is_group(child),
				"root_type": root_type,
				"report_type": "Balance Sheet"
				if root_type in ("Asset", "Liability", "Equity")
				else "Profit and Loss",
				"account_type": child.get("account_type"),
				"account_currency": currency,
			}
		)
		account.flags.ignore_mandatory = True
		account.insert(ignore_permissions=True)
		mapping[key] = account.name
	return created, mapping


def migrer_societe(company, dry_run=1, commit=1):
	"""Passe une société existante au plan SCF Unicare, avec ses comptes par défaut et ses modèles de TVA.

	1. Libère les numéros de compte déjà pris par l'ancien plan, puis crée les comptes SCF manquants.
	2. Re-pointe les comptes par défaut de la société et les paramétrages (articles, magasins, modes de paiement...).
	3. Désactive les anciens modèles de TVA (17 %, 7 %...) et crée les modèles 19 %/9 % ; supprime les modèles
	   dont la société n'existe plus.
	4. Anciens comptes : supprimés s'ils n'ont aucune écriture ni lien, désactivés si leur solde est nul, sinon
	   listés pour un virement manuel par écriture de journal (relancer ensuite pour les désactiver).

	dry_run (par défaut) : rien n'est écrit, le rapport dit ce qui serait fait. Faire une sauvegarde avant.
	commit=0 : laisse la transaction ouverte (tests).
	"""
	dry_run = cint(dry_run)
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Société {0} introuvable.").format(company))

	chart = get_unicare_chart(SCF_CHART)
	doc = frappe.get_doc("Company", company)
	report = {"company": company, "dry_run": dry_run}

	scf_numbers = {
		child["account_number"] for _name, child, _p in _iter_chart(chart["tree"]) if child.get("account_number")
	}
	already_scf = doc.chart_of_accounts == SCF_CHART
	existing = frappe.get_all(
		"Account",
		filters={"company": company},
		fields=["name", "account_name", "account_number", "parent_account"],
		order_by="lft desc",
	)
	# Anciens comptes : tout ce qui existe, sauf les comptes SCF d'une migration déjà faite (relance).
	old_accounts = [
		a.name
		for a in existing
		if not (
			already_scf
			and (
				a.account_number in scf_numbers or (not a.parent_account and a.account_name in chart["tree"])
			)
		)
	]

	# 1. Numéros en conflit, puis comptes SCF.
	conflicts = [a.name for a in existing if a.name in old_accounts and a.account_number in scf_numbers]
	report["numeros_liberes"] = conflicts
	if not dry_run:
		for name in conflicts:
			frappe.db.set_value("Account", name, "account_number", "", update_modified=False)
	created, mapping = _creer_plan(company, chart, old_accounts, dry_run)
	report["comptes_crees"] = len(created)

	# 2. Re-pointage : ancien compte par défaut -> compte SCF du même rôle.
	repoint, cleared = {}, []
	for fieldname, number in chart["unicare_defaults"].items():
		old, new = doc.get(fieldname), mapping.get(number)
		if old and new and old in old_accounts:
			repoint.setdefault(old, new)
	# Autres champs compte de la société (avances, provisoire...) : vidés s'ils visent un ancien compte.
	for field in frappe.get_meta("Company").get("fields", {"fieldtype": "Link", "options": "Account"}):
		if field.fieldname not in chart["unicare_defaults"] and doc.get(field.fieldname) in old_accounts:
			cleared.append(f"{field.fieldname} : {doc.get(field.fieldname)}")
			if not dry_run:
				doc.db_set(field.fieldname, None)
	report["comptes_par_defaut"] = {k: mapping.get(v) for k, v in chart["unicare_defaults"].items()}
	report["champs_societe_vides"] = cleared
	report["re_pointes"] = _repoint_references(repoint, set(old_accounts), dry_run)

	# 3. Modèles de TVA.
	report["modeles"] = _migrer_modeles(company, dry_run)

	if not dry_run:
		doc.db_set("chart_of_accounts", SCF_CHART)
		appliquer_defaults(doc.name, force=True)
		creer_taxes(company)

	# 4. Anciens comptes.
	report["anciens_comptes"] = _nettoyer_anciens(old_accounts, dry_run)

	if not dry_run and cint(commit):
		frappe.db.commit()
	return report


def _repoint_references(repoint, old_accounts, dry_run):
	"""Paramétrages qui visent un ancien compte : re-pointés si le rôle est connu, listés sinon."""
	done, unknown = [], []
	for doctype, fields in ACCOUNT_REFERENCES.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		for fieldname in fields:
			if not frappe.get_meta(doctype).has_field(fieldname):
				continue
			rows = frappe.get_all(
				doctype, filters={fieldname: ("in", list(old_accounts))}, fields=["name", fieldname], limit_page_length=0
			)
			for row in rows:
				old = row[fieldname]
				label = f"{doctype} {row.name}.{fieldname} : {old}"
				if old in repoint:
					done.append(f"{label} -> {repoint[old]}")
					if not dry_run:
						frappe.db.set_value(doctype, row.name, fieldname, repoint[old], update_modified=False)
				else:
					unknown.append(label)
	return {"faits": done, "a_revoir": unknown}


def _migrer_modeles(company, dry_run):
	"""Désactive les modèles de la société qui ne sont pas aux taux 19/9/0 ; supprime ceux des sociétés disparues."""
	companies = set(frappe.get_all("Company", pluck="name"))
	disabled, deleted = [], []
	for doctype in TAX_TEMPLATE_DOCTYPES:
		child = "Item Tax Template Detail" if doctype == "Item Tax Template" else (
			"Sales Taxes and Charges" if doctype.startswith("Sales") else "Purchase Taxes and Charges"
		)
		rate_field = "tax_rate" if doctype == "Item Tax Template" else "rate"
		for template in frappe.get_all(doctype, fields=["name", "company", "disabled"]):
			if template.company not in companies:
				deleted.append(f"{doctype} {template.name}")
				if not dry_run:
					frappe.delete_doc(doctype, template.name, ignore_permissions=True, force=True)
				continue
			if template.company != company or template.disabled:
				continue
			rates = frappe.get_all(child, filters={"parent": template.name, "parenttype": doctype}, pluck=rate_field)
			if any(flt(r) not in (19, 9, 0) for r in rates):
				disabled.append(f"{doctype} {template.name}")
				if not dry_run:
					values = {"disabled": 1}
					if doctype != "Item Tax Template":
						values["is_default"] = 0
					frappe.db.set_value(doctype, template.name, values, update_modified=False)
	return {"desactives": disabled, "supprimes_societe_absente": deleted}


def _nettoyer_anciens(old_accounts, dry_run):
	"""Feuilles d'abord (ordre lft décroissant), pour que les groupes soient vides quand on les traite."""
	deleted, disabled, a_virer = [], [], []
	for name in old_accounts:
		if not frappe.db.exists("Account", name):
			continue
		has_gl = frappe.db.exists("GL Entry", {"account": name, "is_cancelled": 0})
		if has_gl:
			balance = _balance(name)
			if abs(balance) > 0.005:
				ligne = {"compte": name, "solde": balance}
				if frappe.db.get_value("Account", name, "account_type") in STOCK_ACCOUNT_TYPES:
					# Un compte de stock ne se solde pas par écriture de journal : on régénère les écritures des
					# mouvements de stock avec les nouveaux comptes.
					ligne["conseil"] = (
						"Repost Item Valuation avec « Repost Only Accounting Ledgers » sur les mouvements concernés"
					)
				a_virer.append(ligne)
				continue
			disabled.append(name)
			if not dry_run:
				frappe.db.set_value("Account", name, "disabled", 1, update_modified=False)
			continue

		if dry_run:
			deleted.append(name)
			continue
		frappe.db.savepoint("unicare_supprimer_compte")
		try:
			frappe.delete_doc("Account", name, ignore_permissions=True)
			deleted.append(name)
		except Exception:
			# Lié ailleurs (brouillon, paramétrage non re-pointé) ou groupe non vide : on le garde désactivé.
			frappe.db.rollback(save_point="unicare_supprimer_compte")
			frappe.clear_last_message()
			disabled.append(name)
			frappe.db.set_value("Account", name, "disabled", 1, update_modified=False)
	return {"supprimes": deleted, "desactives": disabled, "a_virer_par_ecriture": a_virer}
