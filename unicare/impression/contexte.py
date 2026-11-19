# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Ce qu'une pièce imprimée affiche, prêt pour le gabarit commun (unicare/templates/impression/piece.html).

Une seule mise en page pour toutes les pièces : en-tête du vendeur, titre et numéro, tiers et références, tableau
découpé en pages avec report, puis sur la dernière page les totaux, la somme en lettres, les encadrés
(récapitulatif TVA, conditions, échéancier…) et les signatures. Chaque type de pièce ne fait que remplir ce
contexte.

Mentions de la réglementation algérienne (décret exécutif n° 05-468 du 10 décembre 2005) : raison sociale, forme
juridique, capital, adresse, RC, NIF, NIS et AI du vendeur et de l'acheteur, numéro et date, désignation, quantité,
prix unitaire HT, taux et montant de la TVA, total TTC en chiffres et en lettres, mode de paiement ; la facture
d'avoir cite la facture d'origine.
"""

import json
import re

import frappe
from frappe.utils import cint, flt, strip_html

from unicare.impression import pagination as P
from unicare.impression.montants import date_fr, en_lettres, montant, quantite, taux

# --------------------------------------------------------------------------------------------- les parties


def _texte(valeur):
	"""Une adresse ou un texte saisi en HTML (« 12 rue…<br>Alger ») → une ligne : « 12 rue…, Alger »."""
	valeur = re.sub(r"<br\s*/?>|</p>|</div>|\n", ", ", valeur or "", flags=re.I)
	valeur = strip_html(valeur)
	return re.sub(r"(\s*,\s*)+", ", ", " ".join(valeur.split())).strip(" ,")


def _ids(doc, prefixe):
	"""[("RC", "…"), ("NIF", "…"), ("NIS", "…"), ("AI", "…")] lus dans les champs `<prefixe>rc`, `<prefixe>nif`…"""
	return [(cle, (doc.get(prefixe + cle.lower()) or "").strip()) for cle in ("RC", "NIF", "NIS", "AI")]


def societe(company):
	c = frappe.get_cached_doc("Company", company)
	capital = flt(c.get("unicare_capital_social"))
	return {
		"nom": (c.get("unicare_raison_sociale") or "").strip() or c.company_name,
		"forme": (c.get("unicare_forme_juridique") or "").strip(),
		"capital": montant(capital, 0) if capital else "",
		"adresse": ", ".join(
			p
			for p in (
				_texte(c.get("unicare_adresse")),
				frappe.db.get_value("Commune", c.get("unicare_commune"), "nom")
				if c.get("unicare_commune")
				else "",
				frappe.db.get_value("Wilaya", c.get("unicare_wilaya"), "nom")
				if c.get("unicare_wilaya")
				else "",
			)
			if p
		),
		"site": c.website or "",
		"telephone": c.phone_no or "",
		"email": c.email or "",
		"logo": c.company_logo or "",
		"ids": _ids(c, "unicare_"),
		"banque": c.get("unicare_banque") or "",
		"rib": c.get("unicare_rib") or "",
	}


def _adresse_tiers(doctype, name, adresse_piece=None):
	if adresse_piece:
		return _texte(adresse_piece)
	principale = frappe.db.get_value(
		doctype, name, "customer_primary_address" if doctype == "Customer" else "supplier_primary_address"
	)
	if principale:
		from frappe.contacts.doctype.address.address import get_address_display

		return _texte(get_address_display(principale))
	return ""


def tiers(doctype, name, libelle, adresse_piece=None, nom=None):
	"""Le client ou le fournisseur : raison sociale, forme, adresse et les quatre identifiants."""
	if not name or not frappe.db.exists(doctype, name):
		return {
			"libelle": libelle,
			"nom": nom or name or "",
			"forme": "",
			"adresse": _texte(adresse_piece),
			"ids": [],
		}
	t = frappe.get_cached_doc(doctype, name)
	forme = (t.get("custom_forme_juridique") or "").strip()
	return {
		"libelle": libelle,
		"nom": nom or (t.customer_name if doctype == "Customer" else t.supplier_name),
		"forme": "" if forme in ("Non Précisé", "Personne Physique") else forme,
		"adresse": _adresse_tiers(doctype, name, adresse_piece),
		# les quatre identifiants, même vides : une pièce sans NIF du client se voit tout de suite
		"ids": [(cle, valeur or "—") for cle, valeur in _ids(t, "custom_nº_")],
	}


# ------------------------------------------------------------------------------------------------- la TVA


def _compte_timbre(company):
	from unicare.setup.algeria import bareme_timbre, get_account

	try:
		return get_account(company, bareme_timbre()["compte"])
	except Exception:
		return None


def _taxes(doc):
	"""(lignes de TVA, lignes de timbre) : le timbre se lit à part, après la TVA."""
	timbre = _compte_timbre(doc.company)
	tva, timbres = [], []
	for t in doc.get("taxes") or []:
		(
			timbres
			if (timbre and t.account_head == timbre) or (t.description or "").strip() == "Droit de timbre"
			else tva
		).append(t)
	return tva, timbres


def _taux_par_article(doc, lignes_tva):
	"""{item_code: taux} : le taux de chaque article, lu dans le détail de chaque ligne de taxe."""
	taux_articles = {}
	for ligne in lignes_tva:
		try:
			detail = json.loads(ligne.item_wise_tax_detail or "{}")
		except ValueError:
			detail = {}
		for code in _uniques(item.item_code or item.item_name for item in doc.items):
			valeur = detail.get(code)
			rate = flt(valeur[0]) if isinstance(valeur, list) and valeur else flt(ligne.rate)
			taux_articles[code] = flt(taux_articles.get(code)) + rate
	return taux_articles


def _recap_tva(doc, lignes_tva, taux_articles, signe=1):
	"""[(taux, base HT, TVA)] ; la TVA de chaque taux est recalée pour que la somme soit celle de la pièce."""
	bases = {}
	for item in doc.items:
		rate = flt(taux_articles.get(item.item_code or item.item_name))
		bases[rate] = flt(bases.get(rate)) + abs(flt(item.net_amount))
	total_tva = abs(sum(flt(t.tax_amount_after_discount_amount) for t in lignes_tva))
	groupes = sorted(bases.items())
	recap, cumul = [], 0.0
	for i, (rate, base) in enumerate(groupes):
		tva = flt(base * rate / 100, 2) if i < len(groupes) - 1 else flt(total_tva - cumul, 2)
		cumul += tva
		recap.append((taux(rate), montant(base), montant(tva)))
	return recap, total_tva


# ------------------------------------------------------------------------------------------- les tableaux

COLONNES_ARTICLES = [
	{"cle": "idx", "titre": "N°", "largeur": "37px"},
	{"cle": "ref", "titre": "Réf.", "largeur": "111px"},
	{"cle": "designation", "titre": "Désignation"},
	{"cle": "qte", "titre": "Qté", "num": True, "largeur": "79px", "somme": "quantite"},
	{"cle": "unite", "titre": "Unité", "largeur": "79px"},
	{"cle": "pu", "titre": "P.U. HT", "num": True, "largeur": "116px"},
	{"cle": "tva", "titre": "TVA", "num": True, "largeur": "63px"},
	{"cle": "montant", "titre": "Montant HT", "num": True, "largeur": "142px", "somme": "montant"},
]


def _lot(item):
	"""« Lot L2611-014 · péremption 11/2028 » sous la désignation, quand l'article sort d'un lot."""
	if not item.get("batch_no"):
		return []
	peremption = frappe.db.get_value("Batch", item.batch_no, "expiry_date")
	return [f"Lot {item.batch_no}" + (f" · péremption {peremption.strftime('%m/%Y')}" if peremption else "")]


def _lignes_articles(doc, taux_articles, avec_lot=False):
	lignes = []
	for item in doc.items:
		designation = item.item_name or item.item_code
		sous = _lot(item) if avec_lot else []
		lignes.append(
			{
				"idx": item.idx,
				"cellules": {
					"idx": str(item.idx),
					"ref": item.item_code or "",
					"designation": designation,
					"qte": quantite(abs(flt(item.qty))),
					"unite": item.uom or "",
					"pu": montant(abs(flt(item.net_rate))),
					"tva": taux(taux_articles.get(item.item_code or item.item_name)),
					"montant": montant(abs(flt(item.net_amount))),
				},
				"sous": sous,
				"hauteur": P.hauteur_ligne(designation, sous_lignes=len(sous)),
				"sommes": {"qte": abs(flt(item.qty)), "montant": abs(flt(item.net_amount))},
			}
		)
	return lignes


def _formater_sommes(colonnes, sommes):
	if sommes is None:
		return None
	sortie = {}
	for col in colonnes:
		if col.get("somme"):
			valeur = flt(sommes.get(col["cle"]))
			sortie[col["cle"]] = quantite(valeur) if col["somme"] == "quantite" else montant(valeur)
	return sortie


# ------------------------------------------------------------------------------------------ la fin de page


def _hauteur_fin(ctx):
	"""La place, en mm, de ce qui suit le tableau sur la dernière page."""
	h = 4
	if ctx.get("totaux"):
		h += 6 * len(ctx["totaux"]) + 14
	if ctx.get("lettres"):
		h += 16
	for bloc in ctx.get("encadres") or []:
		if bloc["type"] == "reserves":
			h += 34
		elif bloc["type"] == "tva":
			h += 16 + 6 * len(bloc["lignes"])
		elif bloc["type"] == "kv":
			h += 13 + 4.4 * len(bloc["lignes"])
		else:
			h += 13 + 4.6 * max(
				1, len(bloc.get("texte") or "") // 105 + (bloc.get("texte") or "").count("\n")
			)
	if ctx.get("signatures"):
		h += max(36, 16 + 4.4 * len((ctx.get("a_gauche") or {}).get("lignes") or []))
	if ctx.get("note"):
		h += 7
	return h


def _hauteur_entete(ctx):
	"""La place, en mm, de l'en-tête de la première page : vendeur et titre, puis tiers et références."""
	soc = ctx["societe"]
	vendeur = 7 + 4.6 * sum(
		1 for v in (soc["forme"] or soc["capital"], soc["adresse"], soc["telephone"] or soc["email"]) if v
	)
	vendeur += 18 if soc["logo"] else 0
	titre = 10 + 4.4 * len(ctx["meta"])
	tiers_bloc, refs = ctx["tiers"], ctx["refs"]
	lignes_tiers = 2 + len(tiers_bloc["ids"]) + (1 if tiers_bloc["forme"] or tiers_bloc["adresse"] else 0)
	lignes_refs = (
		1 + len(refs["lignes"]) + (len(refs.get("texte") or "") // 50 + 1 if refs.get("texte") else 0)
	)
	hauteur = max(vendeur, titre) + 4 + 9 + 4.4 * max(lignes_tiers, lignes_refs) + 6
	return hauteur + (16 if ctx.get("montant_recu") else 0)


def _terminer(ctx, lignes):
	"""Pagine le tableau et met les reports en forme."""
	ctx.setdefault("encadres", [])
	entete = _hauteur_entete(ctx)
	pages = P.paginer(lignes, _hauteur_fin(ctx), entete=entete)
	for page in pages:
		page["report_entree"] = _formater_sommes(ctx["colonnes"], page["report_entree"])
		page["report_sortie"] = _formater_sommes(ctx["colonnes"], page["report_sortie"])
		page["cumul_final"] = _formater_sommes(ctx["colonnes"], page["cumul_final"])
	ctx["pages"] = pages
	ctx["colonne_report"] = next(i for i, col in enumerate(ctx["colonnes"]) if col.get("somme"))
	return ctx


def _statut(doc, meta):
	if doc.docstatus == 2:
		meta.append(("Statut", "ANNULÉE"))
	elif doc.docstatus == 0 and doc.doctype in ("Sales Invoice", "Payment Entry"):
		meta.append(("Statut", "Brouillon, sans valeur"))
	return meta


def _uniques(valeurs):
	vus = []
	for valeur in valeurs:
		if valeur and valeur not in vus:
			vus.append(valeur)
	return vus


def _pieces(doctype, noms, champ_date):
	"""« CC-2026-00087 du 10/11/2026, … » ; sans date connue, le numéro seul."""
	textes = []
	for nom in noms:
		date = date_fr(frappe.db.get_value(doctype, nom, champ_date))
		textes.append(f"{nom} du {date}" if date else nom)
	return ", ".join(textes)


def _conditions(doc):
	texte = _texte_long(doc.get("terms"))
	return {"type": "texte", "titre": "Conditions", "texte": texte} if texte else None


def _texte_long(html):
	"""Conditions saisies dans l'éditeur : le texte, paragraphe par paragraphe."""
	html = re.sub(r"<br\s*/?>|</p>|</li>|</div>", "\n", html or "", flags=re.I)
	return "\n".join(line.strip() for line in strip_html(html).splitlines() if line.strip())


def _paiement(doc):
	if cint(doc.get("unicare_paiement_especes")):
		return "Espèces"
	return doc.get("payment_terms_template") or "Virement ou chèque"


def _reglement(soc, reference):
	lignes = [("Banque", soc["banque"]), ("RIB", soc["rib"])]
	lignes = [ligne for ligne in lignes if ligne[1]]
	if reference:
		lignes.append(("Référence", f"Rappeler {reference} sur le virement"))
	return {"type": "kv", "titre": "Règlement", "lignes": lignes} if lignes else None


def _echeancier(doc):
	echeances = doc.get("payment_schedule") or []
	if len(echeances) < 2:
		return None
	lignes = [
		(f"Échéance du {date_fr(e.due_date)}", f"{montant(e.payment_amount)} DA ({taux(e.invoice_portion)})")
		for e in echeances
	]
	return {"type": "kv", "titre": "Échéancier de paiement", "lignes": lignes}


def _totaux_vente(doc, lignes_tva, lignes_timbre, recap, total_tva):
	totaux = [("Total HT", f"{montant(abs(flt(doc.net_total)))} DA")]
	if len(recap) > 1:
		totaux += [(f"TVA {rate}", f"{tva} DA") for rate, _base, tva in recap]
	else:
		totaux.append((f"TVA {recap[0][0]}" if recap else "TVA", f"{montant(total_tva)} DA"))
	timbre = abs(sum(flt(t.tax_amount_after_discount_amount) for t in lignes_timbre))
	if timbre:
		totaux.append(("Droit de timbre", f"{montant(timbre)} DA"))
	ttc = abs(flt(doc.grand_total))
	net = (
		abs(flt(doc.rounded_total))
		if flt(doc.get("rounded_total")) and not cint(doc.get("disable_rounded_total"))
		else ttc
	)
	if flt(net - ttc, 2):
		totaux.append(("Arrondi", f"{montant(net - ttc)} DA"))
	return totaux, net


# ------------------------------------------------------------------------------------------ les pièces


def _base(doc, titre, meta, tiers_bloc, refs):
	return {
		"titre": titre,
		"nom": doc.name,
		"date": date_fr(doc.get("posting_date") or doc.get("transaction_date")),
		"meta": _statut(doc, meta),
		"societe": societe(doc.company),
		"tiers": tiers_bloc,
		"refs": {**refs, "lignes": [(libelle, valeur) for libelle, valeur in refs["lignes"] if valeur]},
		"colonnes": COLONNES_ARTICLES,
	}


def facture(doc):
	avoir = cint(doc.is_return)
	lignes_tva, lignes_timbre = _taxes(doc)
	taux_articles = _taux_par_article(doc, lignes_tva)
	recap, total_tva = _recap_tva(doc, lignes_tva, taux_articles)
	meta = [("N°", doc.name), ("Date", date_fr(doc.posting_date))]
	if avoir:
		if doc.return_against:
			meta.append(("Facture d'origine", _pieces("Sales Invoice", [doc.return_against], "posting_date")))
	elif doc.due_date:
		meta.append(("Échéance", date_fr(doc.due_date)))
	client = tiers(
		"Customer", doc.customer, "Client" if avoir else "Facturé à", doc.address_display, doc.customer_name
	)
	commandes = _uniques(i.sales_order for i in doc.items)
	livraisons = _uniques(i.delivery_note for i in doc.items)
	if avoir:
		motif = (doc.remarks or "").strip()
		refs = {
			"libelle": "Motif de l'avoir",
			"texte": "" if motif in ("", "No Remarks") else motif,
			"lignes": [],
		}
		refs["lignes"].append(("Imputation", "À déduire du solde du client"))
	else:
		lignes = []
		if doc.po_no:
			lignes.append(
				("Votre bon de commande", doc.po_no + (f" du {date_fr(doc.po_date)}" if doc.po_date else ""))
			)
		if commandes:
			lignes.append(("Commande", _pieces("Sales Order", commandes, "transaction_date")))
		if livraisons:
			lignes.append(("Bon de livraison", _pieces("Delivery Note", livraisons, "posting_date")))
		lignes.append(("Mode de paiement", _paiement(doc)))
		refs = {"libelle": "Références", "lignes": lignes}

	ctx = _base(doc, "FACTURE D'AVOIR" if avoir else "FACTURE", meta, client, refs)
	totaux, net = _totaux_vente(doc, lignes_tva, lignes_timbre, recap, total_tva)
	soc = ctx["societe"]
	ctx.update(
		{
			"totaux": totaux,
			"total": ("Total de l'avoir TTC" if avoir else "Net à payer TTC", f"{montant(net)} DA"),
			"lettres": (
				f"Arrêtée la présente facture d'avoir à la somme de : <b>{en_lettres(net)}</b> toutes taxes comprises, en faveur du client."
				if avoir
				else f"Arrêtée la présente facture à la somme de : <b>{en_lettres(net)}</b> toutes taxes comprises."
			),
			"encadres": [
				b
				for b in (
					{
						"type": "tva",
						"titre": "Récapitulatif TVA",
						"colonnes": ("Taux", "Base HT", "TVA à régulariser" if avoir else "Montant TVA"),
						"lignes": recap,
					},
				)
				if b and (b["type"] != "tva" or b["lignes"])
			],
			"signatures": [("Cachet et signature", "")],
			# le règlement se lit à gauche du cachet, sur la même rangée
			"a_gauche": None if avoir else _reglement(soc, doc.name),
		}
	)
	return _terminer(ctx, _lignes_articles(doc, taux_articles))


def devis(doc):
	lignes_tva, lignes_timbre = _taxes(doc)
	taux_articles = _taux_par_article(doc, lignes_tva)
	recap, total_tva = _recap_tva(doc, lignes_tva, taux_articles)
	meta = [("N°", doc.name), ("Date", date_fr(doc.transaction_date))]
	if doc.valid_till:
		meta.append(("Valable jusqu'au", date_fr(doc.valid_till)))
	est_client = doc.quotation_to == "Customer"
	client = tiers(
		"Customer",
		doc.party_name if est_client else None,
		"Proposé à",
		doc.address_display,
		doc.customer_name or doc.party_name,
	)
	lignes = []
	if doc.get("contact_display"):
		lignes.append(("À l'attention de", doc.contact_display))
	if doc.get("payment_terms_template"):
		lignes.append(("Paiement", doc.payment_terms_template))
	if doc.valid_till:
		lignes.append(("Validité de l'offre", f"Jusqu'au {date_fr(doc.valid_till)}"))
	ctx = _base(doc, "DEVIS", meta, client, {"libelle": "Votre demande", "lignes": lignes})
	totaux, net = _totaux_vente(doc, lignes_tva, lignes_timbre, recap, total_tva)
	ctx.update(
		{
			"totaux": totaux,
			"total": ("Total TTC", f"{montant(net)} DA"),
			"lettres": f"Arrêté le présent devis à la somme de : <b>{en_lettres(net)}</b> toutes taxes comprises.",
			"encadres": [b for b in (_conditions(doc),) if b],
			"signatures": [
				("Pour " + ctx["societe"]["nom"], "Cachet et signature"),
				(
					"Bon pour accord du client",
					"Date, nom, cachet et signature, précédés de la mention « Bon pour accord ».",
				),
			],
		}
	)
	return _terminer(ctx, _lignes_articles(doc, taux_articles))


def commande(doc):
	lignes_tva, lignes_timbre = _taxes(doc)
	taux_articles = _taux_par_article(doc, lignes_tva)
	recap, total_tva = _recap_tva(doc, lignes_tva, taux_articles)
	client = tiers("Customer", doc.customer, "Client", doc.address_display, doc.customer_name)
	lignes = []
	if doc.po_no:
		lignes.append(
			("Votre bon de commande", doc.po_no + (f" du {date_fr(doc.po_date)}" if doc.po_date else ""))
		)
	devis_lies = _uniques(i.prevdoc_docname for i in doc.items)
	if devis_lies:
		lignes.append(("Notre devis", _pieces("Quotation", devis_lies, "transaction_date")))
	if doc.delivery_date:
		lignes.append(("Livraison prévue", date_fr(doc.delivery_date)))
	if doc.get("shipping_address"):
		lignes.append(("Adresse de livraison", _texte(doc.shipping_address)))
	if doc.get("payment_terms_template"):
		lignes.append(("Paiement", doc.payment_terms_template))
	ctx = _base(
		doc,
		"CONFIRMATION DE COMMANDE",
		[("N°", doc.name), ("Date", date_fr(doc.transaction_date))],
		client,
		{"libelle": "Commande", "lignes": lignes},
	)
	totaux, net = _totaux_vente(doc, lignes_tva, lignes_timbre, recap, total_tva)
	ctx.update(
		{
			"totaux": totaux,
			"total": ("Total TTC", f"{montant(net)} DA"),
			"lettres": f"Arrêtée la présente commande à la somme de : <b>{en_lettres(net)}</b> toutes taxes comprises.",
			"encadres": [b for b in (_echeancier(doc), _conditions(doc)) if b],
			"signatures": [("Cachet et signature", "")],
		}
	)
	return _terminer(ctx, _lignes_articles(doc, taux_articles))


def livraison(doc):
	client = tiers(
		"Customer",
		doc.customer,
		"Livré à",
		doc.get("shipping_address") or doc.address_display,
		doc.customer_name,
	)
	lignes_refs = []
	commandes = _uniques(i.against_sales_order for i in doc.items)
	if commandes:
		lignes_refs.append(("Commande", _pieces("Sales Order", commandes, "transaction_date")))
	if doc.po_no:
		lignes_refs.append(("Votre bon de commande", doc.po_no))
	depots = _uniques(i.warehouse for i in doc.items)
	if depots:
		lignes_refs.append(
			(
				"Expédié depuis",
				", ".join(frappe.db.get_value("Warehouse", d, "warehouse_name") or d for d in depots),
			)
		)
	if doc.get("transporter_name"):
		lignes_refs.append(("Transporteur", doc.transporter_name))
	if doc.get("vehicle_no"):
		lignes_refs.append(("Véhicule", doc.vehicle_no))
	if doc.get("lr_no"):
		lignes_refs.append(
			("Lettre de voiture", doc.lr_no + (f" du {date_fr(doc.lr_date)}" if doc.get("lr_date") else ""))
		)
	ctx = _base(
		doc,
		"BON DE LIVRAISON",
		[("N°", doc.name), ("Date", date_fr(doc.posting_date))],
		client,
		{"libelle": "Expédition", "lignes": lignes_refs},
	)
	# En Algérie le bon de livraison est valorisé comme une facture : prix unitaires, TVA et totaux.
	lignes_tva, lignes_timbre = _taxes(doc)
	taux_articles = _taux_par_article(doc, lignes_tva)
	recap, total_tva = _recap_tva(doc, lignes_tva, taux_articles)
	totaux, net = _totaux_vente(doc, lignes_tva, lignes_timbre, recap, total_tva)
	ctx.update(
		{
			"totaux": totaux,
			"total": ("Total TTC", f"{montant(net)} DA"),
			"lettres": f"Arrêté le présent bon de livraison à la somme de : <b>{en_lettres(net)}</b> toutes taxes comprises.",
			"encadres": [
				b
				for b in (
					{
						"type": "tva",
						"titre": "Récapitulatif TVA",
						"colonnes": ("Taux", "Base HT", "Montant TVA"),
						"lignes": recap,
					},
					{"type": "reserves", "titre": "Réserves à la réception"},
				)
				if b["type"] != "tva" or b["lignes"]
			],
			"signatures": [
				("Expédié par", "Magasinier : nom, date, signature"),
				("Reçu par le client", "Nom, date et heure, cachet et signature"),
			],
		}
	)
	return _terminer(ctx, _lignes_articles(doc, taux_articles, avec_lot=True))


COLONNES_REGLEMENT = [
	{"cle": "piece", "titre": "Pièce"},
	{"cle": "date", "titre": "Date", "largeur": "116px"},
	{"cle": "ttc", "titre": "Montant TTC", "num": True, "largeur": "147px"},
	{"cle": "deja", "titre": "Déjà réglé", "num": True, "largeur": "137px"},
	{"cle": "regle", "titre": "Réglé ce jour", "num": True, "largeur": "147px", "somme": "montant"},
	{"cle": "reste", "titre": "Reste dû", "num": True, "largeur": "137px"},
]
LIBELLES_PIECES = {
	"Sales Invoice": "Facture",
	"Purchase Invoice": "Facture",
	"Sales Order": "Commande",
	"Purchase Order": "Commande",
	"Journal Entry": "Écriture",
}


def paiement(doc):
	recu = doc.payment_type == "Receive"
	doctype = (
		"Customer" if doc.party_type == "Customer" else "Supplier" if doc.party_type == "Supplier" else None
	)
	partie = (
		tiers(doctype, doc.party, "Reçu de" if recu else "Payé à", None, doc.party_name)
		if doctype
		else tiers("Customer", None, "Tiers", None, doc.party_name)
	)
	compte = doc.paid_to if recu else doc.paid_from
	lignes_refs = [("Mode", doc.mode_of_payment or "")]
	if doc.reference_no:
		lignes_refs.append(
			(
				"Référence",
				doc.reference_no + (f" du {date_fr(doc.reference_date)}" if doc.reference_date else ""),
			)
		)
	if compte:
		lignes_refs.append(("Compte", frappe.db.get_value("Account", compte, "account_name") or compte))
	ctx = _base(
		doc,
		"REÇU DE PAIEMENT" if recu else "AVIS DE PAIEMENT",
		[("N°", doc.name), ("Date", date_fr(doc.posting_date))],
		partie,
		{"libelle": "Règlement", "lignes": lignes_refs},
	)
	ctx["colonnes"] = COLONNES_REGLEMENT
	ctx["montant_recu"] = f"{montant(doc.paid_amount)} DA"
	lignes = []
	for ref in doc.get("references") or []:
		libelle = LIBELLES_PIECES.get(ref.reference_doctype, ref.reference_doctype)
		if flt(ref.total_amount) < 0:
			libelle = "Avoir"
		date_piece = frappe.db.get_value(
			ref.reference_doctype,
			ref.reference_name,
			"posting_date"
			if "Invoice" in ref.reference_doctype or ref.reference_doctype == "Journal Entry"
			else "transaction_date",
		)
		total = flt(ref.total_amount)
		reste_avant = flt(ref.outstanding_amount)
		piece = f"{libelle} {ref.reference_name}"
		lignes.append(
			{
				"idx": ref.idx,
				"cellules": {
					"piece": piece,
					"date": date_fr(date_piece),
					"ttc": montant(total),
					"deja": montant(total - reste_avant),
					"regle": montant(ref.allocated_amount),
					"reste": montant(reste_avant - flt(ref.allocated_amount)),
				},
				"sous": [],
				"hauteur": P.LIGNE,
				"sommes": {"regle": flt(ref.allocated_amount)},
			}
		)
	if flt(doc.unallocated_amount):
		lignes.append(
			{
				"idx": len(lignes) + 1,
				"cellules": {
					"piece": "Non affecté (avance)",
					"date": "",
					"ttc": "",
					"deja": "",
					"regle": montant(doc.unallocated_amount),
					"reste": "",
				},
				"sous": [],
				"hauteur": P.LIGNE,
				"sommes": {"regle": flt(doc.unallocated_amount)},
			}
		)
	ctx.update(
		{
			"totaux": [],
			"total": ("Total réglé", f"{montant(doc.paid_amount)} DA"),
			"lettres": f"Arrêté le présent reçu à la somme de : <b>{en_lettres(doc.paid_amount)}</b>."
			if recu
			else f"Arrêté le présent avis à la somme de : <b>{en_lettres(doc.paid_amount)}</b>.",
			"signatures": [
				("Pour " + ctx["societe"]["nom"], "Caissier ou comptable : nom, cachet et signature")
			],
		}
	)
	return _terminer(ctx, lignes)


def commande_achat(doc):
	lignes_tva, _timbres = _taxes(doc)
	taux_articles = _taux_par_article(doc, lignes_tva)
	recap, total_tva = _recap_tva(doc, lignes_tva, taux_articles)
	fournisseur = tiers(
		"Supplier", doc.supplier, "Fournisseur", doc.get("address_display"), doc.supplier_name
	)
	lignes = []
	if doc.get("set_warehouse"):
		lignes.append(
			(
				"Livrer à",
				frappe.db.get_value("Warehouse", doc.set_warehouse, "warehouse_name") or doc.set_warehouse,
			)
		)
	if doc.get("shipping_address_display"):
		lignes.append(("Adresse", _texte(doc.shipping_address_display)))
	if doc.schedule_date:
		lignes.append(("Date souhaitée", date_fr(doc.schedule_date)))
	devis_lies = _uniques(i.supplier_quotation for i in doc.items)
	if devis_lies:
		lignes.append(("Votre devis", _pieces("Supplier Quotation", devis_lies, "transaction_date")))
	if doc.get("payment_terms_template"):
		lignes.append(("Paiement", doc.payment_terms_template))
	ctx = _base(
		doc,
		"BON DE COMMANDE",
		[("N°", doc.name), ("Date", date_fr(doc.transaction_date))],
		fournisseur,
		{"libelle": "Livraison", "lignes": lignes},
	)
	totaux = [
		("Total HT", f"{montant(doc.net_total)} DA"),
		(f"TVA {recap[0][0]}" if len(recap) == 1 else "TVA", f"{montant(total_tva)} DA"),
	]
	ctx.update(
		{
			"totaux": totaux,
			"total": ("Total TTC", f"{montant(doc.grand_total)} DA"),
			"lettres": f"Arrêté le présent bon de commande à la somme de : <b>{en_lettres(doc.grand_total)}</b> toutes taxes comprises.",
			"encadres": [b for b in (_conditions(doc),) if b],
			"signatures": [
				("Émis par", "Responsable des achats : cachet et signature"),
				("Accusé de réception du fournisseur", "Date, nom, cachet et signature"),
			],
		}
	)
	return _terminer(ctx, _lignes_articles(doc, taux_articles))


CONSTRUCTEURS = {
	"Sales Invoice": facture,
	"Quotation": devis,
	"Sales Order": commande,
	"Delivery Note": livraison,
	"Payment Entry": paiement,
	"Purchase Order": commande_achat,
}


def contexte_impression(doc):
	"""Méthode Jinja des formats d'impression Unicare : le contexte de la pièce, quel que soit son type."""
	return CONSTRUCTEURS[doc.doctype](doc)
