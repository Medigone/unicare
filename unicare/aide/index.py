# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Index du centre d'aide : les catégories et les articles publiés, en cache, et la recherche sans accents."""

import re
import unicodedata

import frappe
from frappe.utils import cint, strip_html

from unicare.aide.rendu import sommaire, texte_brut

CLE = "unicare:aide:index"
MAX_RESULTATS = 20
POIDS = (("titre", 8), ("mots_cles", 5), ("resume", 3), ("texte", 1))
# Des mots qu'on trouve dans presque chaque article (« avoir » est aussi un verbe) : dans le texte, ils ne comptent
# qu'employés comme nom (« un avoir », « l'avoir », « des avoirs »), sans quoi « avoir » renverrait tout le centre
# d'aide. Dans le titre et les mots-clés, ils comptent toujours.
MOTS_COURANTS = frozenset(
	"le la les un une des du de au aux et ou en a pour par sur dans avec sans ce cet cette ces qui que quoi "
	"est sont etre avoir ont fait faire vous on il elle ne pas plus se sa son ses votre vos".split()
)
CHAMPS_COURANTS = ("titre", "mots_cles")
DETERMINANT = r"(?:\b(?:un|une|les|des|ce|cet|cette|ces|votre|vos)\s+|\bl['\u2019]\s*)"
AVANT, APRES = 60, 120


def plain(texte):
	return "".join(
		c for c in unicodedata.normalize("NFD", (texte or "").casefold()) if unicodedata.category(c) != "Mn"
	)


def vider_cache():
	frappe.cache.delete_value(CLE)


def index():
	"""{categories: [...], articles: [...]} des articles publiés, triés par catégorie puis ordre."""
	cached = frappe.cache.get_value(CLE)
	if cached:
		return cached
	categories = frappe.get_all(
		"Categorie Aide",
		fields=["name", "titre", "description", "icone", "ordre"],
		order_by="ordre asc, titre asc",
	)
	rang = {row.name: i for i, row in enumerate(categories)}
	articles = []
	for row in frappe.get_all(
		"Article Aide",
		filters={"statut": "Publié"},
		fields=[
			"name",
			"titre",
			"categorie",
			"resume",
			"ordre",
			"ecrans",
			"mots_cles",
			"contenu_html",
			"duree_lecture",
		],
		limit_page_length=0,
	):
		articles.append(
			{
				"slug": row.name,
				"titre": row.titre,
				"categorie": row.categorie,
				"resume": texte_brut(row.resume),
				"ordre": cint(row.ordre),
				"ecrans": (row.ecrans or "").split(),
				"mots_cles": row.mots_cles or "",
				"texte": _texte(row.contenu_html),
				"sommaire": sommaire(row.contenu_html),
				"duree_lecture": cint(row.duree_lecture),
			}
		)
	articles.sort(key=lambda a: (rang.get(a["categorie"], 999), a["ordre"], a["titre"]))
	data = {"categories": [dict(row) for row in categories], "articles": articles}
	frappe.cache.set_value(CLE, data)
	return data


def _texte(html):
	"""Le texte d'un article rendu, sur une ligne, sans coller les mots de deux blocs voisins."""
	html = re.sub(r"</?(?:p|li|h\d|td|th|tr|br|div|aside|blockquote|i)\b[^>]*>", " ", html or "")
	return " ".join(strip_html(html).split())


def carte(article):
	"""Ce qu'une liste montre d'un article."""
	return {key: article[key] for key in ("slug", "titre", "categorie", "resume", "duree_lecture")}


def pour_ecran(ecran, articles=None):
	ecran = (ecran or "").strip()
	if not ecran:
		return []
	return [a for a in (articles if articles is not None else index()["articles"]) if ecran in a["ecrans"]]


def _plain_indexe(texte):
	"""Le texte sans accents ni majuscules, et pour chaque caractère sa position dans le texte d'origine."""
	sortie, positions = [], []
	for i, c in enumerate(texte):
		for n in plain(c):
			sortie.append(n)
			positions.append(i)
	return "".join(sortie), positions


def extrait(texte, mots):
	"""Le passage du texte autour du premier mot trouvé, coupé aux mots, avec « … » aux bouts."""
	normal, positions = _plain_indexe(texte)
	trouves = [i for i in (_position(mot, normal) for mot in mots) if i >= 0]
	if not trouves:
		return ""
	centre = positions[min(trouves)]
	debut, fin = max(0, centre - AVANT), min(len(texte), centre + APRES)
	phrase = texte.rfind(". ", debut, centre)
	if phrase >= 0:
		debut = phrase + 2  # le début de la phrase plutôt qu'un mot coupé
	elif debut:
		debut = texte.find(" ", debut, centre) + 1 or debut
	if fin < len(texte):
		coupe = texte.rfind(" ", centre, fin)
		fin = coupe if coupe > centre else fin
	return f"{'… ' if debut else ''}{texte[debut:fin].strip()}{' …' if fin < len(texte) else ''}"


def _position(mot, champ, toujours=False):
	"""Où le mot se trouve dans un champ déjà sans accents ; un mot courant, seulement employé comme nom."""
	if toujours or mot not in MOTS_COURANTS:
		return champ.find(mot)
	trouve = re.search(DETERMINANT + "(" + re.escape(mot) + r")s?\b", champ)
	return trouve.start(1) if trouve else -1


def _trouve(mot, champs, key):
	return _position(mot, champs[key], toujours=key in CHAMPS_COURANTS) >= 0


def rechercher(q, ecran=None):
	"""Les articles où se trouve chaque mot tapé, les mieux placés d'abord : {page: [...], autres: [...]}.

	Chaque carte porte un `extrait` du texte autour du mot trouvé ; la première, son `sommaire`."""
	mots = [mot for mot in plain(q).split() if len(mot) > 1]
	if not mots:
		return {"page": [], "autres": []}
	poids = dict(POIDS)
	scores = []
	for article in index()["articles"]:
		champs = {key: plain(article[key]) for key, _poids in POIDS}
		if not all(any(_trouve(mot, champs, key) for key in poids) for mot in mots):
			continue
		score = sum(poids[key] for mot in mots for key in poids if _trouve(mot, champs, key))
		scores.append((score, article))
	scores.sort(key=lambda item: -item[0])
	trouves = []
	for rang, (_score, article) in enumerate(scores[:MAX_RESULTATS]):
		trouve = {**carte(article), "extrait": extrait(article["texte"], mots)}
		if not rang:
			trouve["sommaire"] = article.get("sommaire", [])
		trouves.append((article, trouve))
	ecran = (ecran or "").strip()
	return {
		"page": [t for a, t in trouves if ecran and ecran in a["ecrans"]],
		"autres": [t for a, t in trouves if not (ecran and ecran in a["ecrans"])],
	}
