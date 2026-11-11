# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Tableaux de bord des modules du poste de bureau (/bureau/tableau-de-bord/<module>).

Un tableau par module (Ventes, Achats, Stock, Trésorerie), toujours bâti de la même façon :
- quatre indicateurs, chacun relié à la liste qui le détaille (`lien` : page et vue de l'interface) ;
- une tendance (barres par mois ou par semaine) et une répartition (meilleurs clients, dépôts…) ;
- « À traiter » : de petites listes de cinq lignes au plus, les plus urgentes d'abord, avec leur total.

Les listes « À traiter » et les compteurs reprennent les vues des listes du bureau (mêmes fonctions), pour que
« Tout voir » affiche exactement ce qui a été compté. Les montants passent par `frappe.get_list`, donc par les droits :
un bloc dont le rôle ne lit pas le document n'est pas envoyé. La période (ce mois, 30 jours, trimestre, année)
change les indicateurs de flux et la répartition ; les listes « À traiter » montrent l'état du jour.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, cstr, date_diff, flt, get_first_day, getdate, today

from unicare.api.bureau_list import MAX_PAGE_LENGTH
from unicare.api.bureau_postes import require_bureau

MODULES = ("ventes", "achats", "stock", "tresorerie")
PERIODES = ("mois", "30j", "trimestre", "annee")
LIMITE = 5

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
MOIS_COURTS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def _readable(*doctypes):
	return all(frappe.has_permission(doctype, "read") for doctype in doctypes)


# Périodes ---------------------------------------------------------------------------------------------------------


def _quarter_start(day):
	return getdate(f"{day.year}-{(day.month - 1) // 3 * 3 + 1:02d}-01")


def periode(key, jour=None):
	"""Bornes de la période et de la précédente, de même durée, pour la comparaison."""
	fin = getdate(jour or today())
	if key == "30j":
		debut = add_days(fin, -29)
		return {
			"key": key,
			"debut": debut,
			"fin": fin,
			"avant_debut": add_days(debut, -30),
			"avant_fin": add_days(debut, -1),
			"libelle": _("30 derniers jours"),
			"avant": _("les 30 jours d'avant"),
		}
	if key == "trimestre":
		debut = _quarter_start(fin)
		avant_debut = add_months(debut, -3)
		trimestre = (fin.month - 1) // 3 + 1
		return {
			"key": key,
			"debut": debut,
			"fin": fin,
			"avant_debut": avant_debut,
			"avant_fin": min(add_days(avant_debut, date_diff(fin, debut)), add_days(debut, -1)),
			"libelle": f"T{trimestre} {fin.year}",
			"avant": f"T{(trimestre + 2) % 4 + 1}",
		}
	if key == "annee":
		debut = getdate(f"{fin.year}-01-01")
		avant_debut = getdate(f"{fin.year - 1}-01-01")
		return {
			"key": key,
			"debut": debut,
			"fin": fin,
			"avant_debut": avant_debut,
			"avant_fin": min(add_days(avant_debut, date_diff(fin, debut)), add_days(debut, -1)),
			"libelle": str(fin.year),
			"avant": str(fin.year - 1),
		}
	debut = get_first_day(fin)
	avant_debut = add_months(debut, -1)
	return {
		"key": "mois",
		"debut": debut,
		"fin": fin,
		"avant_debut": avant_debut,
		"avant_fin": min(add_days(avant_debut, date_diff(fin, debut)), add_days(debut, -1)),
		"libelle": f"{MOIS[fin.month - 1].capitalize()} {fin.year}",
		"avant": MOIS[avant_debut.month - 1],
	}


def _months(fin, count=12):
	"""Les `count` derniers mois, le plus ancien d'abord : (clé AAAA-MM, libellé court, titre)."""
	first = get_first_day(fin)
	out = []
	for offset in range(count - 1, -1, -1):
		day = add_months(first, -offset)
		titre = f"{MOIS[day.month - 1].capitalize()} {day.year}"
		out.append((f"{day.year}-{day.month:02d}", MOIS_COURTS[day.month - 1], titre))
	return out


def _weeks(fin, count=8):
	"""Les `count` dernières semaines (du lundi), la plus ancienne d'abord : (lundi, libellé, titre)."""
	monday = add_days(fin, -fin.weekday())
	out = []
	for offset in range(count - 1, -1, -1):
		day = add_days(monday, -7 * offset)
		label = f"{day.day} {MOIS_COURTS[day.month - 1]}"
		out.append((day, label, f"Semaine du {label}"))
	return out


def _variation(actuel, avant, libelle):
	if not avant:
		return None
	taux = (flt(actuel) - flt(avant)) / abs(flt(avant)) * 100
	signe = "↑" if taux >= 0 else "↓"
	texte = f"{signe} {abs(taux):.1f} %".replace(".", ",")
	return [{"texte": texte, "ton": "green" if taux >= 0 else None, "fort": True}, {"texte": _("par rapport à {0}").format(libelle)}]


# Lignes des listes « À traiter » ------------------------------------------------------------------------------------


def _jours(day):
	"""Badge d'une échéance : en retard, aujourd'hui, demain, dans N jours, ou la date."""
	if not day:
		return None
	ecart = date_diff(getdate(day), getdate(today()))
	if ecart < 0:
		return {"texte": _("en retard de {0} j").format(-ecart), "ton": "red"}
	if ecart == 0:
		return {"texte": _("aujourd'hui"), "ton": "amber"}
	if ecart == 1:
		return {"texte": _("demain"), "ton": "amber"}
	if ecart <= 7:
		return {"texte": _("dans {0} j").format(ecart), "ton": "amber" if ecart <= 3 else "gray"}
	day = getdate(day)
	return {"texte": f"{day.day} {MOIS_COURTS[day.month - 1]}", "ton": "gray"}


def _depuis(modified):
	ecart = date_diff(getdate(today()), getdate(modified))
	if ecart <= 0:
		return _("aujourd'hui")
	return _("depuis {0} j").format(ecart)


def _ligne(fiche, name, titre=None, detail=None, badge=None, montant=None, nature=None):
	return {
		"fiche": fiche,
		"name": name,
		"titre": titre or name,
		"detail": detail,
		"badge": badge,
		"montant": None if montant is None else flt(montant, 2),
		"nature": nature,
	}


def _liste(key, titre, lien, lignes, total, ton="gray"):
	return {"key": key, "titre": titre, "lien": lien, "lignes": lignes[:LIMITE], "total": total, "ton": ton if total else "gray"}


def _view(fn, view, sort=None, direction="asc", key=None):
	"""Une vue d'une liste du bureau : ses lignes triées, et son total."""
	response = fn(view=view, sort=sort, direction=direction, page_length=MAX_PAGE_LENGTH)
	rows_key = key or next(k for k, v in response.items() if isinstance(v, list) and k != "names")
	return response[rows_key], response["counts"]


BROUILLONS = {
	# doctype : (libellé court, fiche de l'interface, champ du tiers)
	"Quotation": ("Devis", "DevisFiche", "customer_name"),
	"Sales Order": ("Commande", "CommandeFiche", "customer_name"),
	"Delivery Note": ("Livraison", "LivraisonFiche", "customer_name"),
	"Sales Invoice": ("Facture", "FactureFiche", "customer_name"),
	"Supplier Quotation": ("Devis", "DevisFournisseurFiche", "supplier_name"),
	"Purchase Order": ("Commande", "CommandeAchatFiche", "supplier_name"),
	"Purchase Receipt": ("Réception", "ReceptionFiche", "supplier_name"),
	"Purchase Invoice": ("Facture", "FactureAchatFiche", "supplier_name"),
}


def _brouillons(doctypes, lien):
	"""Les brouillons de plusieurs pièces, les derniers modifiés d'abord."""
	rows, total = [], 0
	for doctype in doctypes:
		if not _readable(doctype):
			continue
		nature, fiche, tiers = BROUILLONS[doctype]
		found = frappe.get_list(doctype, filters={"docstatus": 0}, fields=["name", "modified", tiers], order_by="modified desc", limit_page_length=0)
		total += len(found)
		rows += [(row.modified, _ligne(fiche, row.name, detail=f"{row.get(tiers) or ''} · {_depuis(row.modified)}".strip(" ·"), nature=nature)) for row in found[:LIMITE]]
	rows.sort(key=lambda item: item[0], reverse=True)
	return _liste("brouillons", _("Brouillons à valider"), lien, [row for _modified, row in rows], total)


# Ventes -----------------------------------------------------------------------------------------------------------


def _sum(doctype, filters, field):
	rows = frappe.get_list(doctype, filters=filters, fields=[field], limit_page_length=0)
	return flt(sum(flt(row.get(field)) for row in rows), 2)


def _by_month(doctype, filters, field, date_field, mois):
	debut = getdate(f"{mois[0][0]}-01")
	rows = frappe.get_list(doctype, filters=[*filters, [date_field, ">=", debut]], fields=[field, date_field], limit_page_length=0)
	totals = defaultdict(float)
	for row in rows:
		day = getdate(row.get(date_field))
		totals[f"{day.year}-{day.month:02d}"] += flt(row.get(field))
	return [flt(totals[key], 2) for key, _label, _titre in mois]


def _by_week(doctype, filters, field, date_field, semaines, sign=None):
	debut = semaines[0][0]
	rows = frappe.get_list(doctype, filters=[*filters, [date_field, ">=", debut]], fields=[field, date_field], limit_page_length=0)
	totals = [0.0] * len(semaines)
	for row in rows:
		index = date_diff(getdate(row.get(date_field)), debut) // 7
		if 0 <= index < len(semaines):
			totals[index] += flt(row.get(field))
	return [flt(value, 2) for value in totals]


def _top(doctype, filters, group_field, label_field, field, fiche, limit=LIMITE):
	rows = frappe.get_list(doctype, filters=filters, fields=[group_field, label_field, field], limit_page_length=0)
	totals, labels = defaultdict(float), {}
	for row in rows:
		key = row.get(group_field)
		totals[key] += flt(row.get(field))
		labels[key] = row.get(label_field) or key
	ordered = sorted(totals.items(), key=lambda item: item[1], reverse=True)
	whole = sum(value for _key, value in ordered if value > 0)
	lignes = [{"label": labels[key], "valeur": flt(value, 2), "fiche": fiche, "name": key} for key, value in ordered[:limit] if value > 0]
	return lignes, whole


def _ventes(p):
	jour = getdate(today())
	indicateurs, listes, tendance, repartition = [], [], None, None

	if _readable("Sales Invoice"):
		periode_filtre = [["docstatus", "=", 1], ["posting_date", "between", [p["debut"], p["fin"]]]]
		avant_filtre = [["docstatus", "=", 1], ["posting_date", "between", [p["avant_debut"], p["avant_fin"]]]]
		facture = _sum("Sales Invoice", periode_filtre, "base_net_total")
		avant = _sum("Sales Invoice", avant_filtre, "base_net_total")
		indicateurs.append({
			"key": "facture",
			"label": _("Facturé ({0}, HT)").format(p["libelle"].lower() if p["key"] != "mois" else _("ce mois")),
			"valeur": facture,
			"format": "montant",
			"details": _variation(facture, avant, p["avant"]) or [{"texte": _("Rien à comparer sur {0}").format(p["avant"])}],
			"lien": {"page": "Factures"},
		})
		ouvertes = frappe.get_list(
			"Sales Invoice",
			filters=[["docstatus", "=", 1], ["outstanding_amount", ">", 0]],
			fields=["name", "customer_name", "customer", "due_date", "outstanding_amount"],
			order_by="due_date asc",
			limit_page_length=0,
		)
		retard = [row for row in ouvertes if row.due_date and getdate(row.due_date) < jour]
		indicateurs.append({
			"key": "reste",
			"label": _("Reste à encaisser"),
			"valeur": flt(sum(flt(row.outstanding_amount) for row in ouvertes), 2),
			"format": "montant",
			"details": [
				{"texte": _("{0} DA en retard").format(_money(sum(flt(row.outstanding_amount) for row in retard))), "ton": "red", "fort": True},
				{"texte": _("{0} facture(s)").format(len(retard))},
			]
			if retard
			else [{"texte": _("Aucune facture en retard")}],
			"lien": {"page": "Factures", "vue": "impayees"},
		})
		listes.append(_liste(
			"factures_retard",
			_("Factures en retard de paiement"),
			{"page": "Factures", "vue": "en_retard"},
			[
				_ligne("FactureFiche", row.name, detail=row.customer_name or row.customer, badge={"texte": _("{0} j").format(date_diff(jour, getdate(row.due_date))), "ton": "red"}, montant=row.outstanding_amount)
				for row in retard
			],
			len(retard),
			"red",
		))
		mois = _months(jour)
		paiements = _readable("Payment Entry")
		series = [{"key": "facture", "label": _("Facturé (TTC)")}]
		valeurs = [_by_month("Sales Invoice", [["docstatus", "=", 1]], "base_grand_total", "posting_date", mois)]
		if paiements:
			series.append({"key": "encaisse", "label": _("Encaissé")})
			valeurs.append(_by_month("Payment Entry", [["docstatus", "=", 1], ["payment_type", "=", "Receive"], ["party_type", "=", "Customer"]], "base_received_amount", "posting_date", mois))
		tendance = {
			"titre": _("Facturé et encaissé, 12 derniers mois") if paiements else _("Facturé, 12 derniers mois"),
			"series": series,
			"points": [{"label": label, "titre": titre, "valeurs": [serie[index] for serie in valeurs]} for index, (_key, label, titre) in enumerate(mois)],
		}
		lignes, whole = _top("Sales Invoice", periode_filtre, "customer", "customer_name", "base_net_total", "Client")
		part = sum(row["valeur"] for row in lignes) / whole * 100 if whole else 0
		repartition = {
			"titre": _("Meilleurs clients"),
			"sous_titre": _("facturé HT, {0}").format(p["libelle"].lower()),
			"lignes": lignes,
			"note": _("Les {0} premiers font {1} % du chiffre.").format(len(lignes), f"{part:.0f}") if lignes else None,
			"vide": _("Aucune facture sur la période."),
		}

	if _readable("Sales Order"):
		from unicare.api.bureau_commandes import get_commandes

		rows, counts = _view(get_commandes, "a_livrer", sort="livraison")
		reste = sum(flt(row["total_ttc"]) * (100 - flt(row["livre"])) / 100 for row in rows)
		indicateurs.append({
			"key": "a_livrer",
			"label": _("Commandes à livrer"),
			"valeur": counts["a_livrer"],
			"format": "nombre",
			"details": ([{"texte": _("{0} en retard").format(counts["en_retard"]), "ton": "red", "fort": True}] if counts["en_retard"] else [])
			+ [{"texte": f"{_money(reste)} DA"}],
			"lien": {"page": "Commandes", "vue": "a_livrer"},
		})
		listes.append(_liste(
			"commandes_a_livrer",
			_("Commandes à livrer"),
			{"page": "Commandes", "vue": "a_livrer"},
			[
				_ligne("CommandeFiche", row["name"], detail=row["client_label"] + (_(" · livrée à {0} %").format(f"{row['livre']:.0f}") if row["livre"] else ""), badge=_jours(row["livraison"]))
				for row in rows
			],
			counts["a_livrer"],
			"red" if counts["en_retard"] else "gray",
		))

	if _readable("Quotation"):
		from unicare.api.bureau_devis import get_devis_list

		rows, counts = _view(get_devis_list, "expirent", sort="valable")
		depuis = add_days(jour, -90)
		emis = frappe.get_list("Quotation", filters=[["docstatus", "=", 1], ["transaction_date", ">=", depuis]], fields=["status"], limit_page_length=0)
		commandes = sum(1 for row in emis if row.status in ("Ordered", "Partially Ordered"))
		indicateurs.append({
			"key": "devis",
			"label": _("Devis ouverts"),
			"valeur": counts["ouverts"],
			"format": "nombre",
			"details": [{"texte": _("Transformés en commande :")}, {"texte": f"{commandes / len(emis) * 100:.0f} %", "fort": True}, {"texte": _("sur 90 j")}]
			if emis
			else [{"texte": _("Aucun devis validé sur 90 j")}],
			"lien": {"page": "DevisListe", "vue": "ouverts"},
		})
		listes.append(_liste(
			"devis_expirent",
			_("Devis qui expirent sous 7 jours"),
			{"page": "DevisListe", "vue": "expirent"},
			[_ligne("DevisFiche", row["name"], detail=row["client_label"], badge=_jours(row["valable"]), montant=row["total_ttc"]) for row in rows],
			counts["expirent"],
			"amber",
		))

	listes.append(_brouillons(("Quotation", "Sales Order", "Delivery Note", "Sales Invoice"), {"page": "Factures", "vue": "brouillons"}))
	return {"indicateurs": indicateurs, "tendance": tendance, "repartition": repartition, "listes": listes}


def _money(value):
	return f"{flt(value, 0):,.0f}".replace(",", " ")


# Achats -----------------------------------------------------------------------------------------------------------


def _achats(p):
	jour = getdate(today())
	indicateurs, listes, tendance, repartition = [], [], None, None

	if _readable("Purchase Invoice"):
		periode_filtre = [["docstatus", "=", 1], ["posting_date", "between", [p["debut"], p["fin"]]]]
		achats = _sum("Purchase Invoice", periode_filtre, "base_net_total")
		avant = _sum("Purchase Invoice", [["docstatus", "=", 1], ["posting_date", "between", [p["avant_debut"], p["avant_fin"]]]], "base_net_total")
		variation = _variation(achats, avant, p["avant"])
		if variation:
			# Des achats en hausse ne sont ni bons ni mauvais : la variation reste neutre.
			variation[0]["ton"] = None
		indicateurs.append({
			"key": "achats",
			"label": _("Achats ({0}, HT)").format(p["libelle"].lower() if p["key"] != "mois" else _("ce mois")),
			"valeur": achats,
			"format": "montant",
			"details": variation or [{"texte": _("Rien à comparer sur {0}").format(p["avant"])}],
			"lien": {"page": "FacturesAchat"},
		})
		ouvertes = frappe.get_list(
			"Purchase Invoice",
			filters=[["docstatus", "=", 1], ["outstanding_amount", ">", 0]],
			fields=["name", "supplier_name", "supplier", "due_date", "outstanding_amount"],
			order_by="due_date asc",
			limit_page_length=0,
		)
		echues = [row for row in ouvertes if row.due_date and getdate(row.due_date) < jour]
		indicateurs.append({
			"key": "reste",
			"label": _("Reste à payer"),
			"valeur": flt(sum(flt(row.outstanding_amount) for row in ouvertes), 2),
			"format": "montant",
			"details": [
				{"texte": _("{0} DA échu").format(_money(sum(flt(row.outstanding_amount) for row in echues))), "ton": "red", "fort": True},
				{"texte": _("{0} facture(s)").format(len(echues))},
			]
			if echues
			else [{"texte": _("Rien d'échu")}],
			"lien": {"page": "FacturesAchat", "vue": "a_payer"},
		})
		semaine = [row for row in ouvertes if row.due_date and getdate(row.due_date) <= add_days(jour, 7)]
		listes.append(_liste(
			"factures_a_payer",
			_("Factures à payer sous 7 jours"),
			{"page": "FacturesAchat", "vue": "a_payer"},
			[_ligne("FactureAchatFiche", row.name, detail=row.supplier_name or row.supplier, badge=_echue(row.due_date), montant=row.outstanding_amount) for row in semaine],
			len(semaine),
			"red" if echues else "amber",
		))
		mois = _months(jour)
		valeurs = _by_month("Purchase Invoice", [["docstatus", "=", 1]], "base_net_total", "posting_date", mois)
		tendance = {
			"titre": _("Achats facturés (HT), 12 derniers mois"),
			"series": [{"key": "achats", "label": _("Achats (HT)")}],
			"points": [{"label": label, "titre": titre, "valeurs": [valeurs[index]]} for index, (_key, label, titre) in enumerate(mois)],
		}
		lignes, whole = _top("Purchase Invoice", periode_filtre, "supplier", "supplier_name", "base_net_total", "Fournisseur")
		repartition = {
			"titre": _("Principaux fournisseurs"),
			"sous_titre": _("acheté HT, {0}").format(p["libelle"].lower()),
			"lignes": lignes,
			"note": _("{0} pèse {1} % des achats.").format(lignes[0]["label"], f"{lignes[0]['valeur'] / whole * 100:.0f}") if lignes and whole else None,
			"vide": _("Aucune facture d'achat sur la période."),
		}

	if _readable("Purchase Order"):
		from unicare.api.bureau_commandes_achat import get_commandes_achat

		rows, counts = _view(get_commandes_achat, "a_recevoir", sort="reception")
		reste = sum(flt(row["total_ttc"]) * (100 - flt(row["recu"])) / 100 for row in rows)
		indicateurs.append({
			"key": "a_recevoir",
			"label": _("Commandes à recevoir"),
			"valeur": counts["a_recevoir"],
			"format": "nombre",
			"details": ([{"texte": _("{0} en retard").format(counts["en_retard"]), "ton": "red", "fort": True}] if counts["en_retard"] else [])
			+ [{"texte": f"{_money(reste)} DA"}],
			"lien": {"page": "CommandesAchat", "vue": "a_recevoir"},
		})
		listes.append(_liste(
			"commandes_a_recevoir",
			_("Commandes à recevoir"),
			{"page": "CommandesAchat", "vue": "a_recevoir"},
			[
				_ligne("CommandeAchatFiche", row["name"], detail=row["fournisseur_label"] + (_(" · reçue à {0} %").format(f"{row['recu']:.0f}") if row["recu"] else ""), badge=_jours(row["reception"]))
				for row in rows
			],
			counts["a_recevoir"],
			"red" if counts["en_retard"] else "gray",
		))

	if _readable("Purchase Receipt"):
		from unicare.api.bureau_receptions import get_receptions

		rows, counts = _view(get_receptions, "a_facturer", sort="date")
		indicateurs.append({
			"key": "a_facturer",
			"label": _("Réceptions à facturer"),
			"valeur": counts["a_facturer"],
			"format": "nombre",
			"details": [{"texte": _("Reçues, facture fournisseur pas encore saisie")}, {"texte": f"{_money(sum(flt(row['total_ttc']) for row in rows))} DA"}],
			"lien": {"page": "Receptions", "vue": "a_facturer"},
		})
		listes.append(_liste(
			"receptions_a_facturer",
			_("Réceptions à facturer"),
			{"page": "Receptions", "vue": "a_facturer"},
			[_ligne("ReceptionFiche", row["name"], detail=f"{row['fournisseur_label']} · {_recue(row['date'])}", montant=row["total_ttc"]) for row in rows],
			counts["a_facturer"],
			"amber",
		))

	listes.append(_brouillons(("Supplier Quotation", "Purchase Order", "Purchase Receipt", "Purchase Invoice"), {"page": "FacturesAchat", "vue": "brouillons"}))
	return {"indicateurs": indicateurs, "tendance": tendance, "repartition": repartition, "listes": listes}


def _echue(day):
	badge = _jours(day)
	ecart = date_diff(getdate(day), getdate(today())) if day else 0
	if badge and ecart < 0:
		badge["texte"] = _("échue de {0} j").format(-ecart)
	return badge


def _il_y_a(day, verbe):
	ecart = date_diff(getdate(today()), getdate(day))
	return _("{0} aujourd'hui").format(verbe) if ecart <= 0 else _("{0} il y a {1} j").format(verbe, ecart)


def _recue(day):
	return _il_y_a(day, _("reçue"))


# Stock ------------------------------------------------------------------------------------------------------------


def _stock(p):
	from unicare.api.bureau_stock import depots

	jour = getdate(today())
	indicateurs, listes, tendance, repartition = [], [], None, None

	if _readable("Bin"):
		from unicare.api.bureau_etat_stock import get_etat_stock

		noms = depots(include_disabled=True)
		bins = frappe.get_list("Bin", filters={"warehouse": ["in", noms or [""]]}, fields=["warehouse", "stock_value"], limit_page_length=0)
		valeur = flt(sum(flt(row.stock_value) for row in bins), 2)
		details = [{"texte": _("tous dépôts")}]
		if _readable("Stock Ledger Entry"):
			mouvement = _sum("Stock Ledger Entry", [["is_cancelled", "=", 0], ["warehouse", "in", noms or [""]], ["posting_date", ">", add_days(jour, -30)]], "stock_value_difference")
			variation = _variation(valeur, valeur - mouvement, "")
			if variation:
				details = [{"texte": _("tous dépôts ·")}, {**variation[0], "ton": None}, {"texte": _("sur 30 j")}]
		indicateurs.append({"key": "valeur", "label": _("Valeur du stock"), "valeur": valeur, "format": "montant", "details": details, "lien": {"page": "EtatStock", "vue": "en_stock"}})

		par_depot = defaultdict(float)
		for row in bins:
			par_depot[row.warehouse] += flt(row.stock_value)
		lignes = [{"label": name, "valeur": flt(value, 2), "fiche": "Depot", "name": name} for name, value in sorted(par_depot.items(), key=lambda item: item[1], reverse=True) if value > 0][:LIMITE]
		repartition = {"titre": _("Valeur par dépôt"), "sous_titre": _("aujourd'hui"), "lignes": lignes, "note": _("Un clic ouvre la fiche du dépôt."), "vide": _("Aucun stock valorisé.")}

		seuil, counts = _view(get_etat_stock, "sous_seuil", sort="quantite", key="lignes")
		indicateurs.append({
			"key": "rupture",
			"label": _("En rupture"),
			"valeur": counts["rupture"],
			"format": "nombre",
			"ton": "red" if counts["rupture"] else None,
			"details": [{"texte": _("article × dépôt à zéro ou moins")}],
			"lien": {"page": "EtatStock", "vue": "rupture"},
		})
		sans_commande = sum(1 for row in seuil if not flt(row["commande"]))
		indicateurs.append({
			"key": "sous_seuil",
			"label": _("Sous le seuil de réappro."),
			"valeur": counts["sous_seuil"],
			"format": "nombre",
			"details": [{"texte": _("{0} sans commande d'achat").format(sans_commande), "ton": "amber", "fort": True}, {"texte": _("en cours")}] if sans_commande else [{"texte": _("Tout est commandé")}] if seuil else [{"texte": _("Aucun article sous son seuil")}],
			"lien": {"page": "EtatStock", "vue": "sous_seuil"},
		})

		def badge(row):
			if flt(row["quantite"]) <= 0:
				return {"texte": _("rupture"), "ton": "red"}
			if flt(row["commande"]):
				return {"texte": _("commandé"), "ton": "blue"}
			return {"texte": _("à commander"), "ton": "amber"}

		listes.append(_liste(
			"sous_seuil",
			_("Articles sous le seuil"),
			{"page": "EtatStock", "vue": "sous_seuil"},
			[_ligne("LigneStock", row["name"], titre=row["designation"], detail=f"{row['depot']} · {_qty(row['quantite'])} / {_qty(row['seuil'])} {row['unite'] or ''}".strip(), badge=badge(row)) for row in seuil],
			counts["sous_seuil"],
			"amber",
		))

	if _readable("Batch"):
		from unicare.api.bureau_lots import get_lots

		perimes, counts = _view(get_lots, "perimes", sort="peremption")
		bientot, _counts = _view(get_lots, "expirent", sort="peremption")
		quantite = sum(flt(row["quantite"]) for row in perimes)
		unites = {row["unite"] for row in perimes}
		indicateurs.append({
			"key": "perimes",
			"label": _("Lots périmés en stock"),
			"valeur": counts["perimes"],
			"format": "nombre",
			"ton": "red" if counts["perimes"] else None,
			"details": ([{"texte": f"{_qty(quantite)} {unites.pop() or ''}".strip() + " ·"}] if perimes and len(unites) == 1 else [])
			+ [{"texte": _("{0} autre(s) périment sous 30 j").format(counts["expirent"])}],
			"lien": {"page": "Lots", "vue": "perimes"},
		})

		def lot(row, perime):
			return _ligne(
				"Lot",
				row["name"],
				detail=f"{row['designation']} · {_qty(row['quantite'])} {row['unite'] or ''}".strip(),
				badge={"texte": _("périmé"), "ton": "red"} if perime else _dans(row["peremption"]),
			)

		listes.append(_liste(
			"lots",
			_("Lots périmés ou qui périment sous 30 jours"),
			{"page": "Lots", "vue": "perimes" if counts["perimes"] else "expirent"},
			[lot(row, True) for row in perimes] + [lot(row, False) for row in bientot],
			counts["perimes"] + counts["expirent"],
			"red" if counts["perimes"] else "amber",
		))

	if _readable("Stock Reconciliation"):
		from unicare.api.bureau_inventaires import get_inventaires

		rows, counts = _view(get_inventaires, "brouillons", sort="modified", direction="desc")
		listes.append(_liste(
			"inventaires",
			_("Inventaires en cours"),
			{"page": "Inventaires", "vue": "brouillons"},
			[_ligne("InventaireFiche", row["name"], detail=" · ".join(filter(None, [row.get("depot"), _("{0} ligne(s)").format(row.get("lignes") or 0)])), badge={"texte": _depuis(row["modified"]), "ton": "gray"}) for row in rows],
			counts["brouillons"],
		))

	if _readable("Stock Entry"):
		from unicare.api.bureau_mouvements import get_mouvements

		rows, counts = _view(get_mouvements, "brouillons", sort="modified", direction="desc")
		natures = {"transfert": _("Transfert"), "entree": _("Entrée"), "sortie": _("Sortie")}
		listes.append(_liste(
			"mouvements",
			_("Mouvements en brouillon"),
			{"page": "Mouvements", "vue": "brouillons"},
			[
				_ligne("MouvementFiche", row["name"], detail=" · ".join(filter(None, [" → ".join(filter(None, [row.get("source"), row.get("cible")])), _depuis(row["modified"])])), nature=natures.get(row.get("nature"), _("Mouvement")))
				for row in rows
			],
			counts["brouillons"],
		))

	if _readable("Stock Ledger Entry", "Stock Entry"):
		semaines = _weeks(jour)
		entrees, sorties = _flux(semaines)
		tendance = {
			"titre": _("Entrées et sorties en valeur, par semaine"),
			"note": _("Hors transferts entre dépôts et reconditionnements : seul ce qui entre dans le stock ou en sort."),
			"series": [{"key": "entrees", "label": _("Entrées")}, {"key": "sorties", "label": _("Sorties")}],
			"points": [{"label": label, "titre": titre, "valeurs": [entrees[index], sorties[index]]} for index, (_day, label, titre) in enumerate(semaines)],
		}

	return {"indicateurs": indicateurs, "tendance": tendance, "repartition": repartition, "listes": listes, "sans_periode": True}


def _flux(semaines):
	"""Valeur entrée et sortie du stock par semaine. Une pièce qui ne fait que déplacer (solde nul) ne compte pas."""
	from unicare.api.bureau_stock import depots

	debut = semaines[0][0]
	rows = frappe.get_list(
		"Stock Ledger Entry",
		filters=[["is_cancelled", "=", 0], ["posting_date", ">=", debut], ["warehouse", "in", depots(include_disabled=True) or [""]]],
		fields=["voucher_type", "voucher_no", "posting_date", "stock_value_difference"],
		limit_page_length=0,
	)
	pieces = defaultdict(lambda: [None, 0.0])
	for row in rows:
		entry = pieces[(row.voucher_type, row.voucher_no)]
		entry[0] = min(entry[0], getdate(row.posting_date)) if entry[0] else getdate(row.posting_date)
		entry[1] += flt(row.stock_value_difference)
	entrees, sorties = [0.0] * len(semaines), [0.0] * len(semaines)
	for day, solde in pieces.values():
		index = date_diff(day, debut) // 7
		if not 0 <= index < len(semaines) or abs(solde) < 0.01:
			continue
		if solde > 0:
			entrees[index] += solde
		else:
			sorties[index] -= solde
	return [flt(value, 2) for value in entrees], [flt(value, 2) for value in sorties]


def _qty(value):
	value = flt(value, 3)
	text = f"{value:,.3f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",")
	return text


def _dans(day):
	ecart = date_diff(getdate(day), getdate(today()))
	return {"texte": _("dans {0} j").format(ecart), "ton": "amber" if ecart <= 15 else "gray"}


# Trésorerie -------------------------------------------------------------------------------------------------------


def _tresorerie(p):
	jour = getdate(today())
	indicateurs, listes, tendance, echeancier = [], [], None, None

	if _readable("Payment Entry"):
		from unicare.api.bureau_paiements import get_paiements

		periode_filtre = [["docstatus", "=", 1], ["posting_date", "between", [p["debut"], p["fin"]]]]
		recus = frappe.get_list("Payment Entry", filters=[*periode_filtre, ["payment_type", "=", "Receive"]], fields=["base_received_amount"], limit_page_length=0)
		verses = _sum("Payment Entry", [*periode_filtre, ["payment_type", "=", "Pay"]], "base_paid_amount")
		encaisse = flt(sum(flt(row.base_received_amount) for row in recus), 2)
		quand = _("ce mois") if p["key"] == "mois" else p["libelle"].lower()
		indicateurs.append({
			"key": "encaisse",
			"label": _("Encaissé ({0})").format(quand),
			"valeur": encaisse,
			"format": "montant",
			"details": [{"texte": _("{0} paiement(s) reçu(s)").format(len(recus))}],
			"lien": {"page": "Paiements", "vue": "encaissements"},
		})
		solde = encaisse - verses
		indicateurs.append({
			"key": "decaisse",
			"label": _("Décaissé ({0})").format(quand),
			"valeur": verses,
			"format": "montant",
			"details": [{"texte": _("Solde de la période")}, {"texte": f"{'+' if solde >= 0 else '−'} {_money(abs(solde))} DA", "ton": "green" if solde >= 0 else "red", "fort": True}],
			"lien": {"page": "Paiements", "vue": "decaissements"},
		})
		semaines = _weeks(jour)
		recu = _by_week("Payment Entry", [["docstatus", "=", 1], ["payment_type", "=", "Receive"]], "base_received_amount", "posting_date", semaines)
		verse = _by_week("Payment Entry", [["docstatus", "=", 1], ["payment_type", "=", "Pay"]], "base_paid_amount", "posting_date", semaines)
		tendance = {
			"titre": _("Encaissements et décaissements, par semaine"),
			"series": [{"key": "encaisse", "label": _("Encaissé")}, {"key": "decaisse", "label": _("Décaissé")}],
			"points": [{"label": label, "titre": titre, "valeurs": [recu[index], verse[index]]} for index, (_day, label, titre) in enumerate(semaines)],
		}
		brouillons, counts = _view(get_paiements, "brouillons", sort="modified", direction="desc")
		listes.append(_liste(
			"paiements_brouillons",
			_("Paiements en brouillon"),
			{"page": "Paiements", "vue": "brouillons"},
			[_ligne("PaiementFiche", row["name"], detail=" · ".join(filter(None, [row["tiers_label"], row.get("mode")])), montant=row["montant"], nature=_("Reçu") if row["sens"] == "Receive" else _("Versé")) for row in brouillons],
			counts["brouillons"],
		))
		avances, counts_avances = _view(get_paiements, "non_affectes", sort="date")
		listes.append(_liste(
			"avances",
			_("Avances non affectées"),
			{"page": "Paiements", "vue": "non_affectes"},
			[_ligne("PaiementFiche", row["name"], detail=f"{row['tiers_label']} · {_il_y_a(row['date'], _('reçue') if row['sens'] == 'Receive' else _('versée'))}", montant=row["non_affecte"]) for row in avances],
			counts_avances["non_affectes"],
			"amber",
		))

	buckets = [
		(_("Cette semaine"), jour, add_days(jour, 6 - jour.weekday())),
		(_("Semaine prochaine"), add_days(jour, 7 - jour.weekday()), add_days(jour, 13 - jour.weekday())),
		(_("Plus tard, sous 30 jours"), add_days(jour, 14 - jour.weekday()), add_days(jour, 30)),
	]
	sens = []
	for doctype, key, label, fiche, tiers, titre in (
		("Sales Invoice", "encaisser", _("À encaisser"), "FactureFiche", "customer_name", _("À encaisser sous 7 jours")),
		("Purchase Invoice", "payer", _("À payer"), "FactureAchatFiche", "supplier_name", _("À payer sous 7 jours")),
	):
		if not _readable(doctype):
			continue
		ouvertes = frappe.get_list(doctype, filters=[["docstatus", "=", 1], ["outstanding_amount", ">", 0]], fields=["name", tiers, "due_date", "outstanding_amount"], order_by="due_date asc", limit_page_length=0)
		retard = sum(flt(row.outstanding_amount) for row in ouvertes if row.due_date and getdate(row.due_date) < jour)
		a_venir = [row for row in ouvertes if row.due_date and jour <= getdate(row.due_date) <= add_days(jour, 30)]
		indicateurs.append({
			"key": key,
			"label": _("{0} sous 30 jours").format(label),
			"valeur": flt(sum(flt(row.outstanding_amount) for row in a_venir), 2),
			"format": "montant",
			"details": [{"texte": (_("+ {0} DA déjà en retard") if key == "encaisser" else _("+ {0} DA déjà échu")).format(_money(retard)), "ton": "red", "fort": True}] if retard else [{"texte": _("Rien en retard")}],
			"lien": {"page": "Factures" if key == "encaisser" else "FacturesAchat", "vue": "impayees" if key == "encaisser" else "a_payer"},
		})
		sens.append({"key": key, "label": label, "valeurs": [flt(sum(flt(row.outstanding_amount) for row in a_venir if debut <= getdate(row.due_date) <= fin), 2) for _label, debut, fin in buckets]})
		semaine = [row for row in ouvertes if row.due_date and getdate(row.due_date) <= add_days(jour, 7) and (key == "payer" or getdate(row.due_date) >= jour)]
		listes.insert(len(sens) - 1, _liste(
			f"{key}_7j",
			titre,
			{"page": "Factures" if key == "encaisser" else "FacturesAchat", "vue": "impayees" if key == "encaisser" else "a_payer"},
			[_ligne(fiche, row.name, detail=row.get(tiers), badge=_echue(row.due_date) if key == "payer" else _jours(row.due_date), montant=row.outstanding_amount) for row in semaine],
			len(semaine),
			"red" if any(getdate(row.due_date) < jour for row in semaine) else "amber",
		))
	if sens:
		echeancier = {
			"titre": _("Échéancier des 30 jours"),
			"series": [{"key": serie["key"], "label": serie["label"]} for serie in sens],
			"lignes": [{"label": label, "valeurs": [serie["valeurs"][index] for serie in sens]} for index, (label, _debut, _fin) in enumerate(buckets)],
			"note": _("D'après les échéances des factures non soldées."),
		}
	# L'ordre des indicateurs suit la maquette : encaissé, décaissé, à encaisser, à payer.
	return {"indicateurs": indicateurs, "tendance": tendance, "echeancier": echeancier, "listes": listes}


BUILDERS = {"ventes": _ventes, "achats": _achats, "stock": _stock, "tresorerie": _tresorerie}


@frappe.whitelist()
def get_tableau(module, periode_key="mois"):
	"""Le tableau de bord d'un module pour la période choisie."""
	require_bureau()
	if module not in MODULES:
		frappe.throw(_("Module inconnu."))
	if periode_key not in PERIODES:
		periode_key = "mois"
	p = periode(periode_key)
	payload = BUILDERS[module](p)
	return {
		"module": module,
		"periode": {"key": p["key"], "libelle": p["libelle"], "debut": str(p["debut"]), "fin": str(p["fin"])},
		"jour": str(getdate(today())),
		"indicateurs": payload.get("indicateurs", []),
		"tendance": payload.get("tendance"),
		"repartition": payload.get("repartition"),
		"echeancier": payload.get("echeancier"),
		"listes": payload.get("listes", []),
		"sans_periode": cint(payload.get("sans_periode")),
	}
