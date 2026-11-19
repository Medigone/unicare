# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Centre d'aide du bureau : lecture des articles publiés (panneau « ? », pages /aide) et édition (Réglages > Aide).

La lecture est ouverte à tout compte du bureau, sur les articles publiés seulement. L'édition suit les droits
d'écriture sur `Article Aide`.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr

from unicare.aide import index as aide_index
from unicare.aide.rendu import nettoyer_ecrans, rendre, sommaire, texte_brut
from unicare.api.bureau_list import _parse
from unicare.api.bureau_postes import require_bureau

ARTICLE = "Article Aide"
CATEGORIE = "Categorie Aide"
STATUTS = ("Brouillon", "Publié")
CHAMPS_EDITABLES = (
	"titre",
	"categorie",
	"statut",
	"ordre",
	"resume",
	"contenu_markdown",
	"ecrans",
	"mots_cles",
)


def _stale(doc, modified):
	if cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Cet article vient d'être modifié par ailleurs. Il a été rechargé : vérifiez-le, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)


def _editeur():
	require_bureau()
	if not frappe.has_permission(ARTICLE, "write"):
		frappe.throw(_("Votre compte ne peut pas modifier l'aide."), frappe.PermissionError)


def _peut_editer():
	return bool(frappe.has_permission(ARTICLE, "write"))


def _categories(data, articles=None):
	articles = data["articles"] if articles is None else articles
	return [
		{
			"slug": cat["name"],
			"titre": cat["titre"],
			"description": cat.get("description") or "",
			"icone": cat.get("icone") or "",
			"articles": [aide_index.carte(a) for a in articles if a["categorie"] == cat["name"]],
		}
		for cat in data["categories"]
	]


# ---------------------------------------------------------------- lecture


@frappe.whitelist()
def get_accueil(ecran=None):
	"""Les catégories et leurs articles, et ceux de l'écran ouvert (« Sur cette page »)."""
	require_bureau()
	data = aide_index.index()
	return {
		"categories": [cat for cat in _categories(data) if cat["articles"]],
		"sur_cette_page": [aide_index.carte(a) for a in aide_index.pour_ecran(ecran, data["articles"])],
		"peut_editer": _peut_editer(),
	}


@frappe.whitelist()
def get_contexte(ecran=None):
	"""Les articles de l'écran ouvert seulement : ce que le panneau montre en premier."""
	require_bureau()
	return {"sur_cette_page": [aide_index.carte(a) for a in aide_index.pour_ecran(ecran)]}


@frappe.whitelist()
def rechercher(q=None, ecran=None):
	require_bureau()
	return aide_index.rechercher(cstr(q), ecran)


@frappe.whitelist()
def get_categorie(slug):
	require_bureau()
	data = aide_index.index()
	cat = next((c for c in _categories(data) if c["slug"] == slug), None)
	if not cat or not cat["articles"]:
		frappe.throw(_("Cette rubrique d'aide n'existe pas."), frappe.DoesNotExistError)
	return cat


def _lire(slug, brouillon=False):
	if not slug or not frappe.db.exists(ARTICLE, slug):
		frappe.throw(_("Cet article d'aide n'existe pas."), frappe.DoesNotExistError)
	doc = frappe.get_doc(ARTICLE, slug)
	if doc.statut != "Publié" and not (brouillon and _peut_editer()):
		frappe.throw(_("Cet article d'aide n'existe pas."), frappe.DoesNotExistError)
	return doc


@frappe.whitelist()
def get_article(slug):
	"""Un article : son contenu, son sommaire, sa rubrique, et ses voisins dans la rubrique."""
	require_bureau()
	doc = _lire(slug, brouillon=True)
	data = aide_index.index()
	freres = [a for a in data["articles"] if a["categorie"] == doc.categorie]
	rang = next((i for i, a in enumerate(freres) if a["slug"] == doc.name), None)
	cat = next((c for c in data["categories"] if c["name"] == doc.categorie), None)
	return {
		"slug": doc.name,
		"titre": doc.titre,
		"resume": texte_brut(doc.resume),
		"statut": doc.statut,
		"html": doc.contenu_html or "",
		"sommaire": sommaire(doc.contenu_html),
		"duree_lecture": cint(doc.duree_lecture),
		"date_revision": cstr(doc.date_revision),
		"ecrans": (doc.ecrans or "").split(),
		"categorie": {"slug": cat["name"], "titre": cat["titre"]} if cat else None,
		"precedent": aide_index.carte(freres[rang - 1]) if rang else None,
		"suivant": aide_index.carte(freres[rang + 1])
		if rang is not None and rang + 1 < len(freres)
		else None,
		"peut_editer": _peut_editer(),
	}


# ---------------------------------------------------------------- édition


@frappe.whitelist()
def list_articles():
	"""Toutes les rubriques et tous les articles, brouillons compris, pour Réglages > Aide."""
	_editeur()
	categories = frappe.get_all(
		CATEGORIE,
		fields=["name", "titre", "description", "icone", "ordre", "modified"],
		order_by="ordre asc, titre asc",
	)
	articles = frappe.get_all(
		ARTICLE,
		fields=["name", "titre", "categorie", "statut", "ordre", "resume", "ecrans", "source", "modified"],
		order_by="ordre asc, titre asc",
		limit_page_length=0,
	)
	return {
		"categories": [
			{
				"slug": c.name,
				"titre": c.titre,
				"description": c.description or "",
				"icone": c.icone or "",
				"ordre": cint(c.ordre),
				"modified": str(c.modified),
			}
			for c in categories
		],
		"articles": [
			{
				"slug": a.name,
				"titre": a.titre,
				"categorie": a.categorie,
				"statut": a.statut,
				"ordre": cint(a.ordre),
				"resume": a.resume or "",
				"ecrans": (a.ecrans or "").split(),
				"source": a.source or "",
			}
			for a in articles
		],
		"statuts": list(STATUTS),
	}


def _edition(doc):
	return {
		"slug": doc.name,
		"titre": doc.titre,
		"categorie": doc.categorie,
		"statut": doc.statut,
		"ordre": cint(doc.ordre),
		"resume": doc.resume or "",
		"contenu_markdown": doc.contenu_markdown or "",
		"html": doc.contenu_html or "",
		"ecrans": (doc.ecrans or "").split(),
		"mots_cles": doc.mots_cles or "",
		"source": doc.source or "",
		"date_revision": cstr(doc.date_revision),
		"duree_lecture": cint(doc.duree_lecture),
		"modified": str(doc.modified),
	}


@frappe.whitelist()
def get_article_edition(slug):
	_editeur()
	return _edition(_lire(slug, brouillon=True))


def _appliquer(doc, valeurs):
	for champ in CHAMPS_EDITABLES:
		if champ not in valeurs:
			continue
		valeur = valeurs[champ]
		if champ == "ecrans":
			valeur = nettoyer_ecrans("\n".join(valeur) if isinstance(valeur, list | tuple) else cstr(valeur))
		elif champ == "ordre":
			valeur = cint(valeur)
		elif champ == "statut" and valeur not in STATUTS:
			frappe.throw(_("Statut inconnu : {0}.").format(valeur))
		else:
			valeur = cstr(valeur)
		doc.set(champ, valeur)
	if not cstr(doc.titre).strip():
		frappe.throw(_("Donnez un titre à l'article."))
	if not doc.categorie or not frappe.db.exists(CATEGORIE, doc.categorie):
		frappe.throw(_("Choisissez la rubrique de l'article."))


@frappe.whitelist()
def save_article(slug, modified, valeurs):
	_editeur()
	valeurs = _parse(valeurs) or {}
	doc = _lire(slug, brouillon=True)
	_stale(doc, modified)
	_appliquer(doc, valeurs)
	doc.save()
	return _edition(doc)


def _slug_libre(titre):
	from unicare.aide.rendu import ancre

	base = ancre(titre)
	slug, n = base, 1
	while frappe.db.exists(ARTICLE, slug):
		n += 1
		slug = f"{base}-{n}"
	return slug


@frappe.whitelist()
def create_article(valeurs):
	_editeur()
	valeurs = _parse(valeurs) or {}
	titre = cstr(valeurs.get("titre")).strip()
	if not titre:
		frappe.throw(_("Donnez un titre à l'article."))
	doc = frappe.new_doc(ARTICLE)
	doc.slug = _slug_libre(titre)
	doc.statut = "Brouillon"
	if not valeurs.get("ordre") and valeurs.get("categorie"):
		dernier = frappe.db.get_value(ARTICLE, {"categorie": valeurs["categorie"]}, "max(ordre)")
		valeurs["ordre"] = cint(dernier) + 10
	_appliquer(doc, valeurs)
	doc.insert()
	return _edition(doc)


@frappe.whitelist()
def delete_article(slug, modified):
	_editeur()
	doc = _lire(slug, brouillon=True)
	_stale(doc, modified)
	if not frappe.has_permission(ARTICLE, "delete", doc=doc):
		frappe.throw(_("Votre compte ne peut pas supprimer cet article."), frappe.PermissionError)
	frappe.delete_doc(ARTICLE, doc.name)
	return {"ok": True}


@frappe.whitelist()
def apercu(markdown=None):
	"""Le rendu d'un Markdown en cours de saisie, sans rien enregistrer."""
	_editeur()
	html, minutes = rendre(cstr(markdown))
	return {"html": html, "sommaire": sommaire(html), "duree_lecture": minutes}


@frappe.whitelist()
def save_categorie(slug, modified, valeurs):
	_editeur()
	valeurs = _parse(valeurs) or {}
	if not frappe.db.exists(CATEGORIE, slug):
		frappe.throw(_("Cette rubrique d'aide n'existe pas."), frappe.DoesNotExistError)
	doc = frappe.get_doc(CATEGORIE, slug)
	if cstr(modified) != str(doc.modified):
		frappe.throw(
			_(
				"Cette rubrique vient d'être modifiée par ailleurs. Elle a été rechargée : vérifiez-la, puis recommencez."
			),
			frappe.TimestampMismatchError,
		)
	for champ in ("titre", "description", "icone"):
		if champ in valeurs:
			doc.set(champ, cstr(valeurs[champ]).strip())
	if "ordre" in valeurs:
		doc.ordre = cint(valeurs["ordre"])
	if not doc.titre:
		frappe.throw(_("Donnez un titre à la rubrique."))
	doc.save()
	return {"slug": doc.name, "titre": doc.titre, "modified": str(doc.modified)}
