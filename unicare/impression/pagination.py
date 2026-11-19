# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Découper les lignes d'une pièce en pages A4, avec le report des quantités et des montants d'une page à l'autre.

Le PDF (wkhtmltopdf) ne sait pas où il coupera ni répéter un sous-total : on coupe donc nous-mêmes, à partir d'une
estimation de la hauteur de chaque ligne en millimètres. Chaque page est une boîte de hauteur fixe ; la dernière
reçoit les totaux, la somme en lettres et les signatures (`hauteur_fin`).

Hauteurs, en mm, d'une page A4 imprimée avec 10 mm de marge (277 mm utiles) ; elles suivent les styles de
unicare/templates/impression/base.html.
"""

import math

from frappe.utils import flt

PAGE = 275
PIED = 12  # mentions légales et « Page n/N »
ENTETE = 74  # vendeur, titre, tiers et références (estimation par défaut ; voir contexte._hauteur_entete)
ENTETE_SUITE = 22  # en-tête réduit des pages suivantes
LIGNE_TITRE = 8  # en-tête du tableau
LIGNE_REPORT = 8  # « Total à reporter » / « Report de la page n »
LIGNE = 7.7  # une ligne d'article sur une ligne de texte
LIGNE_EN_PLUS = 4.2  # chaque ligne de texte en plus (désignation longue, lot)
CARACTERES = 40  # caractères de désignation par ligne de texte, à 9 pt dans la colonne la plus large


def hauteur_ligne(designation, sous_lignes=0, caracteres=CARACTERES):
	lignes = max(1, math.ceil(len(designation or "") / caracteres)) + sous_lignes
	return LIGNE + (lignes - 1) * LIGNE_EN_PLUS


def paginer(lignes, hauteur_fin, entete=ENTETE):
	"""[{..., "hauteur": mm, "sommes": {col: valeur}}] → pages [{lignes, numero, report_entree, report_sortie}].

	Une page pleine finit par « Total à reporter » ; la suivante commence par « Report de la page n », avec les
	mêmes chiffres. La fin (totaux…) va sur la dernière page ; si elle n'y tient pas, la dernière ligne passe à la
	page suivante avec elle, pour qu'aucune page ne porte les totaux sans article.
	"""
	premiere = PAGE - PIED - entete - LIGNE_TITRE - LIGNE_REPORT
	suivante = PAGE - PIED - ENTETE_SUITE - LIGNE_TITRE - 2 * LIGNE_REPORT
	pages, reste = [[]], premiere
	for ligne in lignes:
		if ligne["hauteur"] > reste and pages[-1]:
			pages.append([])
			reste = suivante
		pages[-1].append(ligne)
		reste -= ligne["hauteur"]
	# sur la dernière page, la place du « Total à reporter » sert au « Total des lignes » ; une pièce d'une seule
	# page n'a ni l'un ni l'autre
	if len(pages) == 1:
		reste += LIGNE_REPORT
	if reste < hauteur_fin and pages[-1]:
		deplacee = pages[-1].pop() if len(pages[-1]) > 1 else None
		pages.append([deplacee] if deplacee else [])

	total, resultat = len(pages), []
	cumul, derniere_vue = {}, 0
	for numero, contenu in enumerate(pages, 1):
		entree = dict(cumul) if numero > 1 else None
		avant = derniere_vue
		for ligne in contenu:
			for colonne, valeur in (ligne.get("sommes") or {}).items():
				cumul[colonne] = flt(cumul.get(colonne)) + flt(valeur)
		resultat.append(
			{
				"numero": numero,
				"total": total,
				"premiere": numero == 1,
				"derniere": numero == total,
				"lignes": contenu,
				"report_entree": entree,
				"report_sortie": dict(cumul) if numero < total else None,
				"cumul_final": dict(cumul) if numero == total and total > 1 else None,
				"ligne_avant": avant,
				"derniere_ligne": contenu[-1]["idx"] if contenu else avant,
			}
		)
		derniere_vue = resultat[-1]["derniere_ligne"]
	return resultat
