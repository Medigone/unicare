# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Documents internes de production, prêts pour le gabarit unicare/templates/impression/interne.html.

- Ordre de conditionnement : fiche d'ordre (à remplir en atelier), checklist avant production, compte rendu de
  production (après la clôture) ;
- Mouvement de stock : bon de transfert de matières (préparation, compléments, rebuts), et les autres mouvements.

Ces pièces ne sortent pas de l'entreprise : pas de mentions légales, le numéro de l'ordre en grand. Comme pour les
pièces commerciales, un seul tableau (matières, contrôles, lignes du mouvement) se découpe en pages ; ce qui le
précède va sur la première page, ce qui le suit sur la dernière.
"""

import frappe
from frappe.utils import cint, flt, get_datetime, now_datetime

from unicare.impression import pagination as P
from unicare.impression.contexte import societe
from unicare.impression.montants import date_fr, quantite

VIDE = None  # une cellule à remplir à la main
MOINS = chr(0x2212)


def _px(mm):
	return f"{round(mm * 1000 / 190)}px"


def _dt(valeur):
	"""« 20/11/2026 07:45 »."""
	return get_datetime(valeur).strftime("%d/%m/%Y %H:%M") if valeur else ""


def _duree(minutes):
	minutes = cint(minutes)
	if not minutes:
		return ""
	heures, reste = divmod(minutes, 60)
	if not heures:
		return f"{reste} min"
	return f"{heures} h {reste:02d}" if reste else f"{heures} h"


def _depot(nom):
	return (frappe.db.get_value("Warehouse", nom, "warehouse_name") or nom) if nom else ""


def _utilisateur(user=None):
	user = user or frappe.session.user
	return frappe.db.get_value("User", user, "full_name") or user


def _peremption(lot):
	date = frappe.db.get_value("Batch", lot, "expiry_date") if lot else None
	return date.strftime("%m/%Y") if date else ""


def _signe(valeur):
	valeur = flt(valeur, 3)
	if not valeur:
		return "0"
	return ("+ " if valeur > 0 else MOINS + " ") + quantite(abs(valeur))


def _base(doc, titre, sous_titre, numero, droite):
	# l'ordre de conditionnement n'a pas de société : celle par défaut
	company = (
		doc.get("company")
		or frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.get_all("Company", pluck="name", limit=1)[0]
	)
	soc = societe(company)
	return {
		"titre": titre,
		"sous_titre": sous_titre,
		"numero": numero,
		"droite": [(libelle, valeur) for libelle, valeur in droite if valeur],
		"maison": f"{soc['nom'].upper()} · DOCUMENT INTERNE",
		"pied": f"Document interne · imprimé le {now_datetime().strftime('%d/%m/%Y à %H:%M')} par {_utilisateur()}",
		"avant": [],
		"apres": [],
	}


# ------------------------------------------------------------------------------------------- les hauteurs


def _hauteur(section):
	t = section["type"]
	if t == "boites":
		return 14 + 4.4 * max(
			len(b.get("lignes") or []) + (2 if b.get("texte") else 0) + (1 if b.get("grand") else 0)
			for b in section["boites"]
		)
	if t == "etapes":
		return 26
	if t == "chiffres":
		return 26
	if t == "tableau":
		return 10 + P.LIGNE_TITRE + P.LIGNE * len(section["lignes"]) + (6 if section.get("note") else 0)
	if t == "deux_tableaux":
		return 10 + P.LIGNE_TITRE + P.LIGNE * max(len(x["lignes"]) for x in section["tableaux"])
	if t == "saisies":
		return 16 + 7 * section.get("lignes", 0)
	if t == "lignes":
		return 12 + 7 * section["nombre"]
	if t == "texte":
		return 14 + 4.6 * max(1, len(section["texte"]) // 105 + 1)
	if t == "decision":
		return 16
	if t == "note":
		return 7
	if t == "signatures":
		return 30
	return 10


def _terminer(ctx, colonnes, lignes):
	ctx["colonnes"] = colonnes
	entete = 30 + sum(_hauteur(s) + 4 for s in ctx["avant"]) + (6 if ctx.get("titre_tableau") else 0)
	fin = sum(_hauteur(s) + 4 for s in ctx["apres"])
	ctx["pages"] = P.paginer(lignes, fin, entete=entete)
	return ctx


def _ligne(idx, cellules, designation="", sous=0, groupe=None):
	return {
		"idx": idx,
		"cellules": cellules,
		"groupe": groupe,
		"hauteur": P.LIGNE if groupe else P.hauteur_ligne(designation, sous_lignes=sous, caracteres=30),
		"sommes": {},
	}


def _col(cle, titre, mm=None, num=False, saisie=False, centre=False):
	return {
		"cle": cle,
		"titre": titre,
		"largeur": _px(mm) if mm else None,
		"num": num,
		"saisie": saisie,
		"centre": centre,
	}


# ------------------------------------------------------------------------------------- l'ordre : la fiche


def _resume(doc):
	produit = f"{doc.produit_fini} · {doc.nom_produit}" if doc.nom_produit else doc.produit_fini
	return [
		("Article", produit),
		("Quantité prévue", f"{quantite(doc.qty_prevue)} {doc.uom or ''}".strip()),
		("Lot produit fini", doc.lot_pf or "à générer"),
		("Recette", doc.recette),
		("Date prévue", date_fr(doc.date_prevue)),
	]


def _depots(doc):
	return [
		("Fûts (vrac)", _depot(doc.warehouse_mp)),
		("Conditionnement", _depot(doc.warehouse_conditionnement)),
		("Atelier", _depot(doc.warehouse_atelier)),
		("Produits finis", _depot(doc.warehouse_pf)),
		("Rebuts", _depot(doc.warehouse_rebuts)),
	]


def _titre_ordre(doc):
	return f"{doc.nom_produit or doc.produit_fini} · {quantite(doc.qty_prevue)} {doc.uom or ''}".strip()


def fiche_ordre(doc):
	termine = doc.workflow_state == "Terminé"
	ctx = _base(
		doc, "FICHE D'ORDRE DE PRODUCTION", _titre_ordre(doc), doc.name, [("Statut", doc.workflow_state)]
	)
	ctx["code_barres"] = doc.name
	ctx["avant"] = [
		{
			"type": "boites",
			"boites": [
				{"titre": "Produit", "lignes": _resume(doc)},
				{"titre": "Dépôts", "lignes": [ligne for ligne in _depots(doc) if ligne[1]]},
			],
		},
		{
			"type": "etapes",
			"etapes": [
				("1. Planification", _dt(doc.date_heure_planification)),
				("2. Préparation", _dt(doc.date_heure_preparation)),
				("3. Production", _dt(doc.date_heure_production)),
				("4. Clôture", _dt(doc.date_heure_cloture)),
			],
		},
	]
	ctx["titre_tableau"] = f"Matières (recette pour {quantite(doc.qty_prevue)} {doc.uom or ''}".strip() + ")"
	colonnes = [
		_col("idx", "N°", 6),
		_col("ref", "Réf.", 20),
		_col("designation", "Désignation"),
		_col("type", "Type", 16),
		_col("lot", "Lot", 22),
		_col("theorique", "Théorique", 19, num=True),
		_col("reel", "Réel", 17, num=True, saisie=True),
		_col("complement", "Complément", 23, num=True, saisie=True),
		_col("unite", "Unité", 15),
	]
	lignes = []
	for m in doc.matieres:
		designation = m.item_name or m.item_code
		lignes.append(
			_ligne(
				m.idx,
				{
					"idx": str(m.idx),
					"ref": m.item_code,
					"designation": designation,
					"type": "Fût" if m.type_ingredient == "Fût" else "Cond.",
					"lot": m.batch_no or "—",
					"theorique": quantite(m.qty_theorique),
					"reel": quantite(m.qty_reelle) if termine else VIDE,
					"complement": quantite(m.qty_complement) if flt(m.qty_complement) else VIDE,
					"unite": m.uom or "",
				},
				designation,
			)
		)
	rebuts = [
		{
			"Article": f"{r.item_code} · {r.item_name}",
			"Lot": r.batch_no or "—",
			"Quantité": quantite(r.qty),
			"Unité": r.uom or "",
			"Motif": "",
		}
		for r in doc.rebuts
	]
	ctx["apres"] = [
		{
			"type": "tableau",
			"titre": "Rebuts matières" if rebuts else "Rebuts matières (à remplir pendant la production)",
			"colonnes": [
				_col("Article", "Article"),
				_col("Lot", "Lot", 26),
				_col("Quantité", "Quantité", 20, num=True),
				_col("Unité", "Unité", 16),
				_col("Motif", "Motif", 45),
			],
			"lignes": rebuts
			or [dict.fromkeys(("Article", "Lot", "Quantité", "Unité", "Motif")) for _i in range(3)],
		},
		{
			"type": "saisies",
			"titre": "Résultat",
			"champs": [
				("Quantité produite", quantite(doc.qty_reelle_pf) if termine else VIDE, doc.uom or ""),
				("Produit fini rebuté", quantite(doc.qty_rebut) if termine else VIDE, doc.uom or ""),
				("Rendement", quantite(round(flt(doc.rendement_reel), 1)) if termine else VIDE, "%"),
			],
			"lignes": 2,
		},
		{
			"type": "signatures",
			"signatures": [
				("Chef d'atelier", "Nom, date, signature"),
				("Contrôle qualité", "Libération du lot : nom, date, signature"),
			],
		},
	]
	return _terminer(ctx, colonnes, lignes)


# --------------------------------------------------------------------------------- l'ordre : la checklist


def checklist(doc):
	ctx = _base(
		doc,
		"CHECKLIST AVANT PRODUCTION",
		(f"Modèle « {doc.modele_checklist} », " if doc.modele_checklist else "")
		+ "à remplir avant le démarrage de la ligne",
		doc.name,
		[("Préparé le", _dt(doc.date_heure_preparation))],
	)
	lot_vrac = next((m for m in doc.matieres if m.type_ingredient == "Fût" and m.batch_no), None)
	gauche = [
		("Produit", f"{doc.produit_fini} · {doc.nom_produit or ''}".strip(" ·")),
		("Lot à produire", doc.lot_pf or "à générer"),
	]
	if lot_vrac:
		gauche.append(("Lot vrac", f"{lot_vrac.batch_no} · {lot_vrac.item_name}"))
	droite = [
		("Quantité", f"{quantite(doc.qty_prevue)} {doc.uom or ''}".strip()),
		("Atelier", _depot(doc.warehouse_atelier)),
		("Transfert", doc.stock_entry_preparation),
	]
	ctx["avant"] = [
		{
			"type": "boites",
			"boites": [
				{"titre": "Ordre", "lignes": gauche},
				{"titre": "Ligne", "lignes": [d for d in droite if d[1]]},
			],
		}
	]
	ctx["titre_tableau"] = "Contrôles"
	colonnes = [
		_col("idx", "N°", 6),
		_col("controle", "Contrôle"),
		_col("conforme", "Conforme", 34),
		_col("par", "Contrôlé par", 34, saisie=True),
		_col("heure", "Heure", 17, saisie=True),
	]
	lignes = []
	for row in doc.checklist:
		fait = cint(row.conforme)
		lignes.append(
			_ligne(
				row.idx,
				{
					"idx": str(row.idx),
					"controle": row.controle,
					"obligatoire": cint(row.obligatoire),
					"observation": row.observation or "",
					"conforme": {"cases": ["Oui", "Non"], "coche": "Oui" if fait else None},
					"par": _utilisateur(row.controle_par) if fait and row.controle_par else VIDE,
					"heure": get_datetime(row.date_heure).strftime("%H:%M")
					if fait and row.date_heure
					else VIDE,
				},
				row.controle,
				sous=1 if row.observation else 0,
			)
		)
	ctx["apres"] = [
		{
			"type": "note",
			"texte": "Un contrôle obligatoire non conforme bloque le démarrage : Unicare refuse de passer l'ordre en production tant qu'il n'est pas coché conforme.",
		},
		{"type": "lignes", "titre": "Observations", "nombre": 3},
		{"type": "decision", "titre": "Démarrage de la production", "cases": ["Autorisé", "Refusé"]},
		{
			"type": "signatures",
			"signatures": [
				("Opérateur de ligne", "Nom, signature"),
				("Responsable production", "Nom, signature"),
			],
		},
	]
	ctx["pied"] = f"Document interne · à classer avec la fiche d'ordre {doc.name}"
	return _terminer(ctx, colonnes, lignes)


# ---------------------------------------------------------------------------- l'ordre : le compte rendu


def _mouvements(doc):
	"""Les mouvements de stock de l'ordre, dans l'ordre où ils ont été passés."""
	noms = frappe.get_all(
		"Stock Entry",
		filters={"custom_ordre_conditionnement": doc.name, "docstatus": 1},
		fields=["name", "posting_date", "posting_time", "purpose"],
		order_by="posting_date asc, posting_time asc, creation asc",
	)
	libelles = {
		doc.stock_entry_preparation: "Transfert préparation",
		doc.stock_entry_production: "Production (repack)",
		doc.stock_entry_rebuts: "Transfert rebuts",
	}
	complements = {c.stock_entry: c.item_name or c.item_code for c in doc.complements if c.stock_entry}
	lignes = []
	for m in noms:
		libelle = libelles.get(m.name) or (
			f"Complément {complements[m.name].lower()}" if m.name in complements else m.purpose
		)
		lignes.append(
			{
				"Mouvement": libelle,
				"N°": m.name,
				"Date": get_datetime(f"{m.posting_date} {m.posting_time}").strftime("%d/%m %H:%M"),
			}
		)
	return lignes


def _remarque(doc):
	texte = frappe.db.get_value(
		"Comment",
		{
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"comment_type": "Comment",
			"content": ["like", "%Clôture hors tolérance%"],
		},
		"content",
		order_by="creation desc",
	)
	from frappe.utils import strip_html

	return strip_html(texte or "").strip()


def compte_rendu(doc):
	cloture = _dt(doc.date_heure_cloture)
	ctx = _base(
		doc,
		"COMPTE RENDU DE PRODUCTION",
		f"{doc.nom_produit or doc.produit_fini}" + (f" · lot {doc.lot_pf}" if doc.lot_pf else ""),
		doc.name,
		[("Statut", doc.workflow_state + (f" · clôturé le {cloture}" if cloture else ""))],
	)
	unite = doc.uom or ""
	ctx["avant"] = [
		{
			"type": "chiffres",
			"chiffres": [
				("Prévu", quantite(doc.qty_prevue), unite, False),
				("Produit", quantite(doc.qty_reelle_pf), f"{unite}, entrées au magasin produits finis", True),
				("Rebut produit fini", quantite(doc.qty_rebut), unite, False),
				("Rendement", f"{quantite(round(flt(doc.rendement_reel), 1))} %", "produit / prévu", False),
			],
		},
		{
			"type": "deux_tableaux",
			"tableaux": [
				{
					"titre": "Déroulement",
					"colonnes": [
						_col("Étape", "Étape"),
						_col("Date et heure", "Date et heure"),
						_col("Durée", "Durée", num=True),
					],
					"lignes": [
						{
							"Étape": "Planification",
							"Date et heure": _dt(doc.date_heure_planification),
							"Durée": _duree(doc.duree_planification) or "—",
						},
						{
							"Étape": "Préparation",
							"Date et heure": _dt(doc.date_heure_preparation),
							"Durée": _duree(doc.duree_preparation) or "—",
						},
						{
							"Étape": "Production",
							"Date et heure": _dt(doc.date_heure_production),
							"Durée": _duree(doc.duree_production) or "—",
						},
						{"Étape": "Clôture", "Date et heure": cloture, "Durée": "—"},
						{
							"Étape": "Total",
							"Date et heure": "",
							"Durée": _duree(doc.duree_totale) or "—",
							"_fort": True,
						},
					],
				},
				{
					"titre": "Mouvements de stock",
					"colonnes": [_col("Mouvement", "Mouvement"), _col("N°", "N°"), _col("Date", "Date")],
					"lignes": _mouvements(doc)
					or [{"Mouvement": "Aucun mouvement validé", "N°": "", "Date": ""}],
				},
			],
		},
	]
	ctx["titre_tableau"] = "Consommation des matières"
	colonnes = [
		_col("ref", "Réf.", 20),
		_col("designation", "Désignation"),
		_col("lot", "Lot", 22),
		_col("theorique", "Théorique", 19, num=True),
		_col("complement", "Complément", 20, num=True),
		_col("utilise", "Utilisé", 17, num=True),
		_col("ecart", "Écart", 16, num=True),
		_col("unite", "Unité", 12),
	]
	lignes = []
	for m in doc.matieres:
		designation = m.item_name or m.item_code
		lignes.append(
			_ligne(
				m.idx,
				{
					"ref": m.item_code,
					"designation": designation,
					"lot": m.batch_no or "—",
					"theorique": quantite(m.qty_theorique),
					"complement": quantite(m.qty_complement),
					"utilise": quantite(m.qty_reelle),
					"ecart": _signe(flt(m.qty_reelle) - flt(m.qty_theorique)),
					"unite": m.uom or "",
				},
				designation,
			)
		)
	ctx["apres"] = [
		{
			"type": "note",
			"texte": f"Écart = utilisé {MOINS} théorique. Un écart positif est une consommation en plus de la recette.",
		}
	]
	if doc.rebuts:
		ctx["apres"].append(
			{
				"type": "tableau",
				"titre": f"Rebuts matières, transférés au {_depot(doc.warehouse_rebuts) or 'magasin rebuts'}",
				"colonnes": [
					_col("Réf.", "Réf.", 20),
					_col("Désignation", "Désignation"),
					_col("Lot", "Lot", 26),
					_col("Quantité", "Quantité", 20, num=True),
					_col("Unité", "Unité", 14),
				],
				"lignes": [
					{
						"Réf.": r.item_code,
						"Désignation": r.item_name,
						"Lot": r.batch_no or "—",
						"Quantité": quantite(r.qty),
						"Unité": r.uom or "",
					}
					for r in doc.rebuts
				],
			}
		)
	remarque = _remarque(doc)
	if remarque:
		ctx["apres"].append({"type": "texte", "titre": "Remarque de clôture", "texte": remarque})
	ctx["apres"].append(
		{
			"type": "signatures",
			"signatures": [
				("Chef d'atelier", "Nom, date, signature"),
				("Contrôle qualité", "Lot libéré : nom, date, signature"),
			],
		}
	)
	return _terminer(ctx, colonnes, lignes)


# ------------------------------------------------------------------------------- les mouvements de stock

TITRES_MOUVEMENT = {
	"Material Transfer": "BON DE TRANSFERT DE MATIÈRES",
	"Material Transfer for Manufacture": "BON DE TRANSFERT DE MATIÈRES",
	"Material Issue": "BON DE SORTIE DE STOCK",
	"Material Receipt": "BON D'ENTRÉE EN STOCK",
	"Repack": "BON DE PRODUCTION",
	"Manufacture": "BON DE PRODUCTION",
}


TYPES_MOUVEMENT = {
	"Material Transfer": "Transfert",
	"Material Transfer for Manufacture": "Transfert pour fabrication",
	"Material Issue": "Sortie",
	"Material Receipt": "Entrée",
	"Repack": "Reconditionnement",
	"Manufacture": "Fabrication",
}


def mouvement(doc):
	ordre = (
		frappe.get_doc("Ordre de Conditionnement", doc.custom_ordre_conditionnement)
		if doc.get("custom_ordre_conditionnement")
		and frappe.db.exists("Ordre de Conditionnement", doc.custom_ordre_conditionnement)
		else None
	)
	role = ""
	if ordre:
		role = {
			ordre.stock_entry_preparation: "Préparation",
			ordre.stock_entry_rebuts: "Rebuts",
			ordre.stock_entry_production: "Production",
		}.get(doc.name) or ("Complément" if any(c.stock_entry == doc.name for c in ordre.complements) else "")
	sous_titre = (
		f"{role} de l'ordre {ordre.name} · {ordre.nom_produit or ordre.produit_fini}"
		if ordre and role
		else (doc.remarks or "").strip()[:90]
	)
	droite = [
		("Date", _dt(f"{doc.posting_date} {doc.posting_time}")),
		("Type", TYPES_MOUVEMENT.get(doc.purpose, doc.stock_entry_type or doc.purpose)),
	]
	if doc.docstatus == 0:
		droite.append(("Statut", "Brouillon"))
	elif doc.docstatus == 2:
		droite.append(("Statut", "ANNULÉ"))
	ctx = _base(doc, TITRES_MOUVEMENT.get(doc.purpose, "MOUVEMENT DE STOCK"), sous_titre, doc.name, droite)

	sources = _uniques_depots(i.s_warehouse for i in doc.items)
	cibles = _uniques_depots(i.t_warehouse for i in doc.items)
	boites = []
	if sources:
		boites.append({"titre": "Depuis", "grand": " · ".join(sources), "lignes": []})
	if cibles:
		vers = {"titre": "Vers", "grand": " · ".join(cibles), "lignes": []}
		if ordre:
			vers["lignes"] = [
				("Ordre", f"{ordre.name} · {quantite(ordre.qty_prevue)} {ordre.uom or ''}".strip()),
				("Lot à produire", ordre.lot_pf or "à générer"),
			]
		boites.append(vers)
	if boites:
		ctx["avant"] = [{"type": "boites", "boites": boites}]

	# le demandé de la préparation : ce que la recette prévoit pour l'ordre
	demandes = {}
	if ordre and role == "Préparation":
		for m in ordre.matieres:
			demandes[m.item_code] = flt(demandes.get(m.item_code)) + flt(m.qty_theorique)
	avec_demande = bool(demandes)
	colonnes = [
		_col("idx", "N°", 6),
		_col("ref", "Réf.", 20),
		_col("designation", "Désignation"),
		_col("lot", "Lot", 22),
		_col("peremption", "Péremption", 22),
	]
	if avec_demande:
		colonnes.append(_col("demande", "Demandé", 18, num=True))
	colonnes += [
		_col("qte", "Remis" if avec_demande else "Quantité", 17, num=True),
		_col("unite", "Unité", 13),
		_col("recu", "Reçu", 11, centre=True),
	]

	lignes, groupe, numero = [], None, 0
	for item in doc.items:
		cle = (item.s_warehouse, item.t_warehouse)
		if len(sources) + len(cibles) > 2 and cle != groupe:
			groupe = cle
			libelle = " → ".join(d for d in (_depot(item.s_warehouse), _depot(item.t_warehouse)) if d)
			lignes.append(_ligne(None, {}, groupe=libelle))
		numero += 1
		designation = item.item_name or item.item_code
		cellules = {
			"idx": str(numero),
			"ref": item.item_code,
			"designation": designation,
			"lot": item.batch_no or "—",
			"peremption": _peremption(item.batch_no) or "—",
			"qte": quantite(item.qty),
			"unite": item.uom or item.stock_uom or "",
			"recu": {"cases": [""], "coche": None},
		}
		if avec_demande:
			cellules["demande"] = quantite(demandes.get(item.item_code, item.qty))
		lignes.append(_ligne(numero, cellules, designation))
	ctx["apres"] = [
		{
			"type": "note",
			"texte": f"{numero} article{'s' if numero > 1 else ''}. Les quantités sont celles enregistrées dans Unicare ; un écart se note ci-dessous et se corrige par un complément.",
		},
		{"type": "lignes", "titre": "Écarts constatés à la réception", "nombre": 2},
		{
			"type": "signatures",
			"signatures": [
				("Remis par (magasin)", "Nom, heure, signature"),
				("Reçu par", "Nom, heure, signature"),
			],
		},
	]
	return _terminer(ctx, colonnes, lignes)


def _uniques_depots(noms):
	vus = []
	for nom in noms:
		libelle = _depot(nom)
		if libelle and libelle not in vus:
			vus.append(libelle)
	return vus


DOCUMENTS_ORDRE = {"fiche": fiche_ordre, "checklist": checklist, "compte_rendu": compte_rendu}


def contexte_production(doc, document="fiche"):
	"""Méthode Jinja des formats internes : `document` choisit la pièce de l'ordre (fiche, checklist, compte_rendu)."""
	if doc.doctype == "Stock Entry":
		return mouvement(doc)
	return DOCUMENTS_ORDRE[document](doc)
