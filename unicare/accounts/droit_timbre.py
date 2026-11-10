"""Droit de timbre sur les factures de vente payées en espèces (Algérie).

Case « Paiement en espèces » (unicare_paiement_especes) cochée : une ligne de taxe « Montant réel » sur le compte de
timbre (44575 du plan SCF) est ajoutée ou mise à jour à chaque enregistrement, sur le TTC hors timbre. Case
décochée : la ligne est retirée. Barème dans unicare/setup/data/algeria_fiscal.json. Sans compte de timbre
(plan Standard), rien ne se passe.
"""

import frappe
from frappe.utils import cint, flt

from unicare.setup.algeria import bareme_timbre, get_account

DESCRIPTION = "Droit de timbre"


def calculer_timbre(montant_ttc, bareme=None):
	"""Timbre en DA pour un TTC en DA : taux de la tranche sur tout le montant, au centime, minimum du barème."""
	bareme = bareme or bareme_timbre()
	montant_ttc = flt(montant_ttc)
	if montant_ttc <= 0:
		return 0.0

	for tranche in bareme["tranches"]:
		if tranche["jusqu_a"] is None or montant_ttc <= tranche["jusqu_a"]:
			taux = flt(tranche["taux"])
			break

	# Pas d'arrondi au dinar : montant exact, au centime.
	return max(flt(montant_ttc * taux / 100, 2), flt(bareme["minimum"]))


def _paye_en_especes(doc):
	if not cint(doc.is_pos):
		return False
	for payment in doc.get("payments") or []:
		if flt(payment.amount) and frappe.get_cached_value("Mode of Payment", payment.mode_of_payment, "type") == "Cash":
			return True
	return False


def appliquer_droit_timbre(doc, method=None):
	if doc.docstatus != 0 or cint(doc.is_return):
		return

	bareme = bareme_timbre()
	compte = get_account(doc.company, bareme["compte"])
	if not compte:
		return

	if _paye_en_especes(doc):
		doc.unicare_paiement_especes = 1

	lignes = [t for t in doc.get("taxes") or [] if t.account_head == compte]

	if not cint(doc.get("unicare_paiement_especes")):
		if lignes:
			for ligne in lignes:
				doc.remove(ligne)
			doc.calculate_taxes_and_totals()
		return

	# Le barème est en dinars : base en devise société, hors timbre déjà calculé.
	timbre_actuel = sum(flt(t.base_tax_amount_after_discount_amount) for t in lignes)
	conversion = flt(doc.conversion_rate) or 1
	montant = flt(calculer_timbre(flt(doc.base_grand_total) - timbre_actuel, bareme) / conversion, 2)

	ligne = lignes[0] if lignes else None
	for doublon in lignes[1:]:
		doc.remove(doublon)
	if ligne and ligne.charge_type == "Actual" and flt(ligne.tax_amount, 2) == montant and len(lignes) == 1:
		return

	if not ligne:
		ligne = doc.append("taxes", {})
	ligne.update(
		{
			"charge_type": "Actual",
			"account_head": compte,
			"description": DESCRIPTION,
			"tax_amount": montant,
			"cost_center": ligne.cost_center or frappe.get_cached_value("Company", doc.company, "cost_center"),
			"included_in_print_rate": 0,
		}
	)
	doc.calculate_taxes_and_totals()
