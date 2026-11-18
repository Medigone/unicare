# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Réglages, page Comptabilité (/bureau/compta) : bilan de la configuration, comptes par défaut, TVA, modes de
paiement, exercices et droit de timbre.

Tout s'applique à la société par défaut (`_company`). Les comptes proposés sont les comptes de détail de cette
société, filtrés par rôle (un compte client doit être de type « Receivable », etc.). Le barème du droit de timbre
est celui de la loi de finances, livré avec l'application (setup/data/algeria_fiscal.json) : affiché, pas modifié
ici. Droits : ceux d'ERPNext (Company, modèles de TVA, Mode of Payment, Fiscal Year).
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_years, cint, cstr, date_diff, flt, getdate, today

from unicare.api.bureau_devis import _company
from unicare.api.bureau_list import _parse
from unicare.api.bureau_postes import require_bureau
from unicare.chart_of_accounts.chart_of_accounts import SCF_CHART
from unicare.setup.algeria import bareme_timbre, get_account

COMPTE = "Account"
SOCIETE = "Company"
MODE = "Mode of Payment"
EXERCICE = "Fiscal Year"
TVA = {
	"vente": ("Sales Taxes and Charges Template", "Sales Taxes and Charges", "44571"),
	"achat": ("Purchase Taxes and Charges Template", "Purchase Taxes and Charges", "44566"),
}
MODE_TYPES = ("Cash", "Bank", "General")
# Avant la fin de l'exercice, le bilan rappelle de créer le suivant.
PREAVIS_EXERCICE = 60

# Comptes par défaut de la société : (champ, libellé, aide, filtre des comptes proposés, indispensable).
COMPTES = (
	(
		"Tiers",
		(
			("default_receivable_account", "Clients", "Ce que les clients doivent.", {"account_type": "Receivable"}, True),
			("default_payable_account", "Fournisseurs", "Ce qui est dû aux fournisseurs.", {"account_type": "Payable"}, True),
		),
	),
	(
		"Trésorerie",
		(
			("default_bank_account", "Banque", "Repris par les modes bancaires sans compte propre.", {"account_type": "Bank"}, True),
			("default_cash_account", "Caisse", "Repris par les modes espèces sans compte propre.", {"account_type": "Cash"}, True),
		),
	),
	(
		"Ventes et achats",
		(
			("default_income_account", "Ventes", "Chiffre d'affaires des articles sans compte propre.", {"root_type": "Income"}, True),
			("default_expense_account", "Coût des ventes", "Charge des articles vendus.", {"root_type": "Expense"}, True),
			("default_discount_account", "Remises accordées", None, {"root_type": ["in", ["Income", "Expense"]]}, False),
			("write_off_account", "Pertes et petits écarts", "Reste dû passé en perte.", {"root_type": "Expense"}, True),
			("round_off_account", "Écarts d'arrondi", None, {"root_type": "Expense"}, True),
		),
	),
	(
		"Stock",
		(
			("default_inventory_account", "Stock", "Valeur du stock.", {"account_type": "Stock"}, True),
			("stock_adjustment_account", "Variations des stocks", "Écarts d'inventaire et corrections.", {"root_type": "Expense"}, True),
			("stock_received_but_not_billed", "Réceptions non facturées", "En attente de la facture fournisseur.", {"root_type": "Liability"}, True),
			("expenses_included_in_valuation", "Frais accessoires d'achat", "Transport, douane… ajoutés au coût du stock.", {"root_type": "Expense"}, False),
		),
	),
)
CHAMPS = {field: (label, filtre, requis) for _groupe, rows in COMPTES for field, label, _aide, filtre, requis in rows}


def _societe():
	company = _company()
	if not company:
		frappe.throw(_("Aucune société par défaut : créez-la d'abord."))
	return company


def _stale(doc, modified):
	if cstr(modified) != str(doc.modified):
		frappe.throw(
			_("Ces réglages viennent d'être modifiés par ailleurs. Ils ont été rechargés : vérifiez-les, puis recommencez."),
			frappe.TimestampMismatchError,
		)


def _comptes(company, filtre):
	return frappe.get_all(
		COMPTE,
		filters={"company": company, "is_group": 0, "disabled": 0, **filtre},
		order_by="lft asc",
		pluck="name",
	)


# --- Lecture ----------------------------------------------------------------------------------------------


def _tva(company, sens):
	doctype, child, _numero = TVA[sens]
	rows = frappe.get_all(
		doctype,
		filters={"company": company},
		fields=["name", "title", "is_default", "disabled", "modified"],
		order_by="disabled asc, title asc",
	)
	lignes = {}
	for row in frappe.get_all(
		child,
		filters={"parenttype": doctype, "parent": ["in", [row.name for row in rows] or [""]]},
		fields=["parent", "rate", "account_head"],
		order_by="idx asc",
	):
		lignes.setdefault(row.parent, []).append(row)
	return [
		{
			"name": row.name,
			"titre": row.title or row.name,
			"taux": sum(flt(line.rate) for line in lignes.get(row.name, [])),
			"compte": lignes[row.name][0].account_head if lignes.get(row.name) else None,
			"defaut": bool(cint(row.is_default)),
			"actif": not cint(row.disabled),
			"modified": str(row.modified),
		}
		for row in rows
	]


def _modes(company):
	societe = frappe.get_cached_value(SOCIETE, company, ["default_bank_account", "default_cash_account"], as_dict=True)
	comptes = {
		row.parent: row.default_account
		for row in frappe.get_all(
			"Mode of Payment Account", filters={"company": company}, fields=["parent", "default_account"]
		)
	}
	return [
		{
			"name": row.name,
			"type": row.type,
			"actif": bool(cint(row.enabled)),
			"compte": comptes.get(row.name),
			# Compte pris quand le mode n'en a pas (voir bureau_factures._payment_account).
			"repli": societe.default_cash_account if row.type == "Cash" else societe.default_bank_account,
			"modified": str(row.modified),
		}
		for row in frappe.get_all(MODE, fields=["name", "type", "enabled", "modified"], order_by="name asc")
	]


def _exercices(company):
	rows = frappe.get_all(
		EXERCICE,
		filters={"disabled": 0},
		fields=["name", "year_start_date", "year_end_date"],
		order_by="year_start_date desc",
	)
	# Un exercice sans société listée vaut pour toutes ; sinon, il doit lister celle-ci.
	liees = {}
	for row in frappe.get_all("Fiscal Year Company", fields=["parent", "company"]):
		liees.setdefault(row.parent, set()).add(row.company)
	jour = getdate(today())
	return [
		{
			"name": row.name,
			"debut": str(row.year_start_date),
			"fin": str(row.year_end_date),
			"en_cours": getdate(row.year_start_date) <= jour <= getdate(row.year_end_date),
		}
		for row in rows
		if not liees.get(row.name) or company in liees[row.name]
	]


def _suivant(exercices):
	"""L'exercice à créer après le dernier : mêmes dates, un an plus tard."""
	if not exercices:
		annee = getdate(today()).year
		return {"name": str(annee), "debut": f"{annee}-01-01", "fin": f"{annee}-12-31"}
	dernier = exercices[0]
	debut = add_days(dernier["fin"], 1)
	fin = add_years(dernier["fin"], 1)
	name = str(getdate(debut).year) if getdate(debut).year == getdate(fin).year else f"{getdate(debut).year}-{getdate(fin).year}"
	return {"name": name, "debut": str(debut), "fin": str(fin)}


def _bilan(societe, valeurs, tva, modes, exercices, timbre):
	def point(code, label, etat, detail, ancre):
		return {"code": code, "label": label, "etat": etat, "detail": detail, "ancre": ancre}

	jour = getdate(today())
	en_cours = next((row for row in exercices if row["en_cours"]), None)
	suivant_existe = en_cours and any(getdate(row["debut"]) > getdate(en_cours["fin"]) for row in exercices)
	if not en_cours:
		exercice = point("exercice", "Exercice comptable", "manque", _("Aucun exercice ne couvre aujourd'hui : aucune pièce ne peut être validée."), "exercices")
	elif not suivant_existe and date_diff(en_cours["fin"], jour) <= PREAVIS_EXERCICE:
		exercice = point(
			"exercice",
			"Exercice comptable",
			"attention",
			_("L'exercice {0} se termine le {1} et le suivant n'existe pas encore.").format(
				en_cours["name"], frappe.format(en_cours["fin"], {"fieldtype": "Date"})
			),
			"exercices",
		)
	else:
		exercice = point("exercice", "Exercice comptable", "ok", _("Exercice {0} en cours.").format(en_cours["name"]), "exercices")

	manquants = [CHAMPS[field][0] for field, (_l, _f, requis) in CHAMPS.items() if requis and not valeurs.get(field)]
	sans_compte = [row["name"] for row in modes if row["actif"] and not row["compte"]]
	sans_repli = [row["name"] for row in modes if row["actif"] and not row["compte"] and not row["repli"]]

	def tva_point(sens, label):
		defaut = next((row for row in tva[sens] if row["defaut"] and row["actif"]), None)
		if defaut:
			return point(f"tva_{sens}", label, "ok", _("Par défaut : {0}.").format(defaut["titre"]), "tva")
		return point(f"tva_{sens}", label, "manque", _("Aucun taux par défaut : les nouvelles pièces partent sans TVA."), "tva")

	tarifs = {
		"vente": frappe.db.get_single_value("Selling Settings", "selling_price_list"),
		"achat": frappe.db.get_single_value("Buying Settings", "buying_price_list"),
	}
	return [
		exercice,
		point(
			"plan",
			"Plan comptable",
			"ok" if societe.chart_of_accounts == SCF_CHART else "attention",
			_("Plan SCF algérien.") if societe.chart_of_accounts == SCF_CHART else _("La société n'utilise pas le plan SCF Unicare."),
			"comptes",
		),
		point(
			"comptes",
			"Comptes par défaut",
			"manque" if manquants else "ok",
			_("À renseigner : {0}.").format(", ".join(manquants)) if manquants else _("Tous les comptes indispensables sont posés."),
			"comptes",
		),
		tva_point("vente", "TVA des ventes"),
		tva_point("achat", "TVA des achats"),
		point(
			"modes",
			"Modes de paiement",
			"manque" if sans_repli else ("attention" if sans_compte else "ok"),
			_("Sans compte, ni compte de repli : {0}.").format(", ".join(sans_repli))
			if sans_repli
			else _("Sans compte propre (le compte banque ou caisse par défaut est pris) : {0}.").format(", ".join(sans_compte))
			if sans_compte
			else _("Chaque mode actif a son compte."),
			"modes",
		),
		point(
			"timbre",
			"Droit de timbre",
			"ok" if timbre else "manque",
			_("Compté sur {0}.").format(timbre) if timbre else _("Le compte {0} n'existe pas : le timbre n'est pas ajouté aux factures payées en espèces.").format(bareme_timbre()["compte"]),
			"timbre",
		),
		point(
			"tarifs",
			"Tarifs par défaut",
			"ok" if all(tarifs.values()) else "manque",
			_("Ventes : {0} · Achats : {1}.").format(tarifs["vente"], tarifs["achat"]) if all(tarifs.values()) else _("Choisissez-les dans la page Tarifs et prix des réglages."),
			"tarifs",
		),
	]


@frappe.whitelist()
def get_compta():
	require_bureau()
	frappe.has_permission(COMPTE, "read", throw=True)
	company = _societe()
	societe = frappe.get_doc(SOCIETE, company)
	valeurs = {field: societe.get(field) for field in CHAMPS}
	tva = {sens: _tva(company, sens) for sens in TVA}
	modes = _modes(company)
	exercices = _exercices(company)
	timbre = get_account(company, bareme_timbre()["compte"])
	return {
		"societe": {"name": company, "modified": str(societe.modified), "devise": societe.default_currency},
		"bilan": _bilan(societe, valeurs, tva, modes, exercices, timbre),
		"comptes": {
			"groupes": [
				{
					"titre": groupe,
					"champs": [
						{"field": field, "label": label, "aide": aide, "requis": requis, "valeur": valeurs.get(field)}
						for field, label, aide, _filtre, requis in rows
					],
				}
				for groupe, rows in COMPTES
			],
			"options": {field: _comptes(company, filtre) for field, (_l, filtre, _r) in CHAMPS.items()},
		},
		"tva": tva,
		"modes": modes,
		"comptes_tresorerie": _comptes(company, {"account_type": ["in", ["Bank", "Cash"]]}),
		"exercices": exercices,
		"exercice_suivant": _suivant(exercices),
		"timbre": {**bareme_timbre(), "compte_nom": timbre},
		"droits": {
			"comptes": bool(frappe.has_permission(SOCIETE, "write", doc=company)),
			"tva": {sens: bool(frappe.has_permission(TVA[sens][0], "write")) for sens in TVA},
			"tva_creer": {sens: bool(frappe.has_permission(TVA[sens][0], "create")) for sens in TVA},
			"modes": bool(frappe.has_permission(MODE, "write")),
			"modes_creer": bool(frappe.has_permission(MODE, "create")),
			"exercices": bool(frappe.has_permission(EXERCICE, "create")),
		},
	}


# --- Écritures --------------------------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def save_comptes(modified, values=None):
	"""Comptes par défaut de la société. Un champ vide est refusé s'il est indispensable."""
	require_bureau()
	company = _societe()
	doc = frappe.get_doc(SOCIETE, company)
	doc.check_permission("write")
	_stale(doc, modified)
	values = _parse(values) or {}
	for field, (label, filtre, requis) in CHAMPS.items():
		if field not in values:
			continue
		compte = cstr(values.get(field)).strip()
		if not compte:
			if requis:
				frappe.throw(_("Le compte « {0} » est indispensable.").format(label))
		elif compte not in _comptes(company, filtre):
			frappe.throw(_("Le compte {0} ne convient pas pour « {1} ».").format(compte, label))
		doc.set(field, compte or None)
	doc.save()
	return get_compta()


def _template(sens, name, modified):
	if sens not in TVA:
		frappe.throw(_("Choisissez la TVA des ventes ou des achats."))
	doc = frappe.get_doc(TVA[sens][0], name)
	if doc.company != _societe():
		frappe.throw(_("Ce taux appartient à une autre société."))
	doc.check_permission("write")
	_stale(doc, modified)
	return doc


@frappe.whitelist(methods=["POST"])
def set_tva(sens, name, modified, action):
	"""`defaut` : le taux repris par les nouvelles pièces ; `activer` / `desactiver` : proposé ou non."""
	require_bureau()
	doc = _template(sens, name, modified)
	if action == "defaut":
		if cint(doc.disabled):
			frappe.throw(_("Activez ce taux avant d'en faire le taux par défaut."))
		# ERPNext retire « par défaut » des autres modèles de la société à l'enregistrement.
		doc.is_default = 1
	elif action == "desactiver":
		if cint(doc.is_default):
			frappe.throw(_("C'est le taux par défaut : choisissez-en un autre par défaut avant de le désactiver."))
		doc.disabled = 1
	elif action == "activer":
		doc.disabled = 0
	else:
		frappe.throw(_("Action inconnue."))
	doc.save()
	return get_compta()


@frappe.whitelist(methods=["POST"])
def create_tva(sens, taux, titre=None):
	"""Nouveau taux de TVA, sur le compte de TVA collectée (ventes) ou déductible (achats) du plan SCF."""
	require_bureau()
	if sens not in TVA:
		frappe.throw(_("Choisissez la TVA des ventes ou des achats."))
	doctype, _child, numero = TVA[sens]
	frappe.has_permission(doctype, "create", throw=True)
	company = _societe()
	texte = cstr(taux).replace(",", ".").replace("%", "").strip()
	try:
		taux = float(texte)
	except ValueError:
		frappe.throw(_("Taux illisible : {0}.").format(texte))
	if taux < 0 or taux >= 100:
		frappe.throw(_("Le taux est un pourcentage entre 0 et 99."))
	compte = get_account(company, numero)
	if not compte:
		frappe.throw(_("Le compte de TVA {0} n'existe pas dans le plan de la société.").format(numero))
	affiche = f"{taux:g}".replace(".", ",")
	titre = cstr(titre).strip() or (f"TVA {affiche}%" if sens == "vente" else f"TVA déductible {affiche}%")
	if frappe.db.exists(doctype, {"title": titre, "company": company}):
		frappe.throw(_("Un taux s'appelle déjà « {0} ».").format(titre))
	doc = frappe.new_doc(doctype)
	doc.update({"title": titre, "company": company})
	doc.append(
		"taxes",
		{"charge_type": "On Net Total", "account_head": compte, "rate": taux, "description": titre, "category": "Total", "add_deduct_tax": "Add"}
		if sens == "achat"
		else {"charge_type": "On Net Total", "account_head": compte, "rate": taux, "description": titre},
	)
	doc.insert()
	return get_compta()


@frappe.whitelist(methods=["POST"])
def save_mode(name=None, modified=None, values=None):
	"""Crée (sans `name`) ou modifie un mode de paiement : type, compte pour la société, actif."""
	require_bureau()
	company = _societe()
	values = _parse(values) or {}
	if name:
		doc = frappe.get_doc(MODE, name)
		doc.check_permission("write")
		_stale(doc, modified)
	else:
		frappe.has_permission(MODE, "create", throw=True)
		nom = cstr(values.get("nom")).strip()
		if not nom:
			frappe.throw(_("Donnez un nom au mode de paiement."))
		if frappe.db.exists(MODE, nom):
			frappe.throw(_("Un mode s'appelle déjà « {0} ».").format(nom))
		doc = frappe.new_doc(MODE)
		doc.mode_of_payment = nom
	kind = values.get("type") or doc.type
	if kind not in MODE_TYPES:
		frappe.throw(_("Choisissez le type : espèces ou banque."))
	doc.type = kind
	doc.enabled = 0 if values.get("actif") is False else 1
	compte = cstr(values.get("compte")).strip()
	if compte and compte not in _comptes(company, {"account_type": ["in", ["Bank", "Cash"]]}):
		frappe.throw(_("Choisissez un compte de banque ou de caisse de la société."))
	rows = [
		{"company": row.company, "default_account": row.default_account}
		for row in doc.get("accounts") or []
		if row.company != company
	]
	if compte:
		rows.append({"company": company, "default_account": compte})
	doc.set("accounts", rows)
	doc.save() if name else doc.insert()
	return get_compta()


@frappe.whitelist(methods=["POST"])
def create_exercice():
	"""Crée l'exercice qui suit le dernier (mêmes dates, un an plus tard)."""
	require_bureau()
	frappe.has_permission(EXERCICE, "create", throw=True)
	company = _societe()
	suivant = _suivant(_exercices(company))
	if frappe.db.exists(EXERCICE, suivant["name"]):
		frappe.throw(_("L'exercice {0} existe déjà.").format(suivant["name"]))
	doc = frappe.new_doc(EXERCICE)
	doc.update({"year": suivant["name"], "year_start_date": suivant["debut"], "year_end_date": suivant["fin"]})
	doc.insert()
	return get_compta()
