# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Import des guides d'utilisation (`docs/guides/*.html`) en articles d'aide.

Chaque guide devient une catégorie, découpée en articles : une vue d'ensemble, un article par étape
(`article.step#id`) et un article des messages et raccourcis. Le guide des réglages, sans étapes, donne un
article par module.

L'import se relance sans risque : un article absent est créé, un article importé et jamais retouché est mis à
jour, un article modifié à la main depuis l'import est laissé tel quel et signalé.

	bench --site <site> execute unicare.aide.import_guides.importer
"""

import hashlib
import os
import re

import frappe

GUIDES = os.path.join(
	os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "guides"
)

# guide : (titre de la catégorie, description, icône Lucide, ordre)
CATEGORIES = {
	"ventes": ("Ventes", "Du devis à l'encaissement.", "shopping-cart", 10),
	"achats": ("Achats", "De la demande de prix au paiement du fournisseur.", "truck", 20),
	"stock": ("Stock", "Articles, dépôts, mouvements, inventaires et lots.", "package", 30),
	"production": ("Production", "Recettes, ordres et clôture de la production.", "factory", 40),
	"tarifs": ("Tarifs et prix", "Les tarifs de vente et d'achat, et leurs prix.", "tag", 50),
	"listes": ("Listes de choix", "Catégories, raisons, unités : les listes des pièces.", "list", 60),
	"seuils": ("Stock et seuils", "Dépôts, seuils de réapprovisionnement, paramètres.", "gauge", 70),
	"compta": (
		"Comptabilité et trésorerie",
		"Comptes, TVA, modes de paiement, exercices, timbre.",
		"landmark",
		80,
	),
	"utilisateurs": ("Utilisateurs", "Comptes, rôles, mots de passe, qui fait quoi.", "users", 90),
	"reglages": ("Réglages", "Où se règle quoi, et l'ordre à suivre la première fois.", "settings", 100),
}

# Les écrans du bureau (l'`id` des entrées du menu) où chaque article est proposé « Sur cette page ».
# `_vue` : la vue d'ensemble ; une étape absente prend les écrans de `_defaut`.
ECRANS = {
	"ventes": {
		"_vue": ["tableau-ventes"],
		"client": ["clients"],
		"devis": ["devis"],
		"commande": ["commandes"],
		"livraison": ["livraisons"],
		"facture": ["factures"],
		"encaissement": ["paiements", "factures"],
	},
	"achats": {
		"_vue": ["tableau-achats"],
		"fournisseur": ["fournisseurs"],
		"devis": ["devis-fournisseurs"],
		"commande": ["commandes-achat"],
		"reception": ["receptions"],
		"facture": ["factures-achat"],
		"paiement": ["paiements", "factures-achat"],
	},
	"stock": {
		"_vue": ["tableau-stock"],
		"referentiel": ["articles", "depots"],
		"consulter": ["etat-stock"],
		"mouvement": ["mouvements"],
		"inventaire": ["inventaires"],
		"lots": ["lots"],
	},
	"production": {
		"_vue": ["tableau-production", "reglages-production"],
		"recette": ["recettes"],
		"_defaut": ["ordres"],
	},
	"tarifs": {"_vue": ["tarifs"], "_defaut": ["tarifs"]},
	"listes": {"_vue": ["listes"], "_defaut": ["listes"]},
	"seuils": {
		"_vue": ["reglages-stock"],
		"depots": ["reglages-stock", "depots"],
		"_defaut": ["reglages-stock"],
	},
	"compta": {"_vue": ["compta"], "_defaut": ["compta"]},
	"utilisateurs": {"_vue": ["utilisateurs"], "_defaut": ["utilisateurs"]},
	"reglages": {
		"_vue": [],
		"r-ventes": ["tarifs", "listes"],
		"r-achats": ["tarifs", "listes"],
		"r-stock": ["reglages-stock", "depots", "articles"],
		"r-tresor": ["compta"],
		"r-prod": ["reglages-production"],
		"r-users": ["utilisateurs"],
	},
}

MESSAGES = ("messages", "raccourcis")
PASTILLES = {
	"p-green": "vert",
	"p-blue": "bleu",
	"p-amber": "ambre",
	"p-red": "rouge",
	"p-grey": "gris",
	"p-violet": "bleu",
}
BLOCS = {
	"p",
	"div",
	"ol",
	"ul",
	"table",
	"details",
	"h2",
	"h3",
	"h4",
	"section",
	"article",
	"aside",
	"header",
}
DIRECTIVE_INTERDITS = re.compile(r"[\]\[<\n]")


# ---------------------------------------------------------------- HTML → Markdown


class Convertisseur:
	"""Le Markdown d'un morceau de guide, avec les conventions du rendu (`:btn[…]`, `:champ[…]`…)."""

	def __init__(self, liens):
		self.liens = liens  # ancre du guide (ou « guide-x.html#ancre ») → lien de l'aide

	# -- en ligne

	def texte(self, el):
		return re.sub(r"\s+", " ", self.inline(el)).strip()

	def inline(self, el):
		from bs4 import NavigableString, Tag

		if isinstance(el, NavigableString):
			if type(el).__name__ == "Comment":
				return ""
			return self.echapper(str(el))
		if not isinstance(el, Tag):
			return ""
		name, cls = el.name, el.get("class") or []
		if name in ("svg", "script", "style"):
			return ""
		if name == "br":
			return "  \n"
		inner = lambda: "".join(self.inline(c) for c in el.children)  # noqa: E731
		brut = lambda: re.sub(r"\s+", " ", el.get_text(" ", strip=True))  # noqa: E731
		if name in ("b", "strong"):
			return self.entourer(inner(), "**")
		if name in ("em",) or (name == "i" and "path" not in (el.parent.get("class") or [])):
			return self.entourer(inner(), "*")
		if name == "q":
			return f"« {inner().strip()} »"
		if name == "kbd":
			return f"<kbd>{self.echapper(brut())}</kbd>"
		if name == "sup":
			return f"<sup>{self.echapper(brut())}</sup>"
		if name == "code" or (name == "span" and "mono" in (el.get("style") or "")):
			return f"`{brut()}`"
		if name == "a":
			href = self.lien(el.get("href") or "")
			return f"[{inner().strip()}]({href})" if href else inner()
		if name == "small":
			return f" ({inner().strip()})"
		if name == "span":
			if "btn" in cls:
				return self.directive("alt" if "alt" in cls else "btn", brut(), inner)
			if "field" in cls:
				return self.directive("champ", brut(), inner)
			if "path" in cls:
				parts = [
					re.sub(r"\s+", " ", t).strip()
					for t in el.find_all(string=True)
					if t.strip() not in ("", "›")  # noqa: RUF001
				]
				return self.directive("chemin", " > ".join(p for p in parts if p), inner)
			if "pill" in cls:
				couleur = next((PASTILLES[c] for c in cls if c in PASTILLES), "gris")
				return self.directive(f"pastille-{couleur}", brut(), inner)
			if "tag-new" in cls:
				return f" *({brut()})*"
			if "effect" in cls:
				return f" *({brut()})*"
			if "eyebrow" in cls or "dot" in cls or "mod-dot" in cls:
				return ""
		return inner()

	def directive(self, kind, texte, repli):
		texte = texte.strip()
		if not texte or len(texte) > 120 or DIRECTIVE_INTERDITS.search(texte):
			return self.entourer(repli(), "**")
		texte = texte.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_")
		return f":{kind}[{texte}]" + (" " if kind.startswith("pastille") else "")

	@staticmethod
	def entourer(texte, marque):
		coeur = texte.strip()
		if not coeur:
			return texte
		avant = " " if texte[:1].isspace() else ""
		apres = " " if texte[-1:].isspace() else ""
		return f"{avant}{marque}{coeur}{marque}{apres}"

	@staticmethod
	def echapper(texte):
		texte = texte.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
		return texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

	def lien(self, href):
		if href.startswith(("http://", "https://", "mailto:")):
			return href
		cle = href.lstrip("./")
		if cle in self.liens:
			return self.liens[cle]
		if cle.startswith("#") and cle[1:] in self.liens:
			return self.liens[cle[1:]]
		return ""

	# -- blocs

	def blocs(self, el, titre=2):
		"""Les blocs Markdown d'un élément ; `titre` : le niveau de ses h2."""
		from bs4 import NavigableString, Tag

		if isinstance(el, NavigableString):
			texte = self.texte(el)
			return [texte] if texte else []
		if not isinstance(el, Tag):
			return []
		name, cls = el.name, el.get("class") or []
		if (
			name in ("svg", "footer", "script", "style")
			or "step-num" in cls
			or el.get("aria-hidden") == "true"
		):
			return []
		if name in ("h2", "h3", "h4"):
			niveau = min(4, int(name[1]) - 2 + titre)
			texte = self.texte(el)
			return [f"{'#' * niveau} {texte}"] if texte else []
		if name == "p":
			texte = self.texte(el)
			if not texte:
				return []
			if "fix" in cls:
				return [f"> [!astuce] {texte}"]
			return [texte]
		if name == "ol" and "route" in cls:
			return self.route(el)
		if name in ("ol", "ul"):
			return [self.liste(el, ordonnee=name == "ol")]
		if name == "table":
			return [self.tableau(el)]
		if name == "details":
			summary = el.find("summary")
			corps = [b for c in el.children if c is not summary for b in self.blocs(c, titre)]
			return [f"{'#' * min(4, titre + 1)} {self.texte(summary) if summary else ''}", *corps]
		if "states" in cls:
			return [self.etats(el)]
		if "keys" in cls:
			return [self.touches(el)]
		if "setting" in cls:
			return self.reglage(el, titre)
		if "where" in cls:
			return ["\n".join(f"- {self.texte(span)}" for span in el.find_all("span", recursive=False))]
		if "flux-item" in cls or ("place" in cls and not el.find(["h3", "p"])):
			return [f"- {self.texte(el)}"]
		if "eyebrow" in cls:
			return []
		# conteneur : ses blocs, ou un paragraphe s'il ne contient que du texte en ligne
		if any(isinstance(c, Tag) and c.name in BLOCS for c in el.children):
			sortie = []
			for c in el.children:
				sortie.extend(self.blocs(c, titre))
			return sortie
		texte = self.texte(el)
		return [texte] if texte else []

	def liste(self, el, ordonnee):
		lignes = []
		for i, li in enumerate(el.find_all("li", recursive=False), 1):
			marque = f"{i}." if ordonnee else "-"
			sous = [c for c in li.children if getattr(c, "name", None) in ("ul", "ol")]
			texte = re.sub(r"\s+", " ", "".join(self.inline(c) for c in li.children if c not in sous)).strip()
			lignes.append(f"{marque} {texte}")
			for s in sous:
				lignes.extend("    " + ligne for ligne in self.liste(s, s.name == "ol").splitlines())
		return "\n".join(lignes)

	def route(self, el):
		sortie, items = [], []
		for li in el.find_all("li", recursive=False):
			if "lane" in (li.get("class") or []):
				if items:
					sortie.append("\n".join(items))
					items = []
				sortie.append(f"**{self.texte(li)}**")
				continue
			cible = li.find("a")
			t, d = li.select_one(".t"), li.select_one(".d")
			effet = li.select_one(".effect")
			nom = self.texte(t) if t else self.texte(li)
			if cible and self.lien(cible.get("href") or ""):
				nom = re.sub(
					r"^(.*?)( \(.*\))?$",
					lambda m: f"[{m.group(1)}]({self.lien(cible.get('href'))}){m.group(2) or ''}",
					nom,
				)
			ligne = f"- **{nom}**" if not nom.startswith("[") else f"- {nom}"
			if d:
				ligne += f" : {self.texte(d)}"
			if effet:
				ligne += f" *{self.echapper(effet.get_text(' ', strip=True))}.*"
			items.append(ligne)
		if items:
			sortie.append("\n".join(items))
		return sortie

	def etats(self, el):
		lignes = []
		for state in el.find_all("div", class_="state", recursive=False):
			pill = state.find(class_="pill")
			texte = " ".join(self.texte(p) for p in state.find_all("p"))
			lignes.append(f"- {self.inline(pill).strip() if pill else ''} : {texte}")
		return "\n".join(lignes)

	def touches(self, el):
		lignes = []
		for key in el.find_all("div", class_="key", recursive=False):
			span = key.find("span", recursive=False)
			label = re.sub(
				r"\s+", " ", "".join(str(s) for s in key.find_all(string=True, recursive=False))
			).strip()
			lignes.append(f"- {self.echapper(label)} : {self.texte(span) if span else ''}")
		return "\n".join(lignes)

	def reglage(self, el, titre):
		h3 = el.find("h3")
		who = el.find(class_="who")
		sortie = [f"{'#' * min(4, titre + 1)} {self.texte(h3)}"] if h3 else []
		if who and "bureau" not in (who.get("class") or []):
			sortie.append(f"*Réglé par : {self.texte(who)}.*")
		where = el.find(class_="where-to")
		if where:
			span = where.find("span", recursive=False)
			if span:
				sortie.append(f"**Où :** {self.texte(span)}")
			sortie.extend(self.texte(p) for p in where.find_all("p"))
		return sortie

	def tableau(self, el):
		lignes = []
		for i, tr in enumerate(el.find_all("tr")):
			cells = [self.texte(c).replace("|", "\\|") for c in tr.find_all(["th", "td"])]
			lignes.append("| " + " | ".join(cells) + " |")
			if i == 0:
				lignes.append("|" + "---|" * len(cells))
		return "\n".join(lignes)


def markdown(blocs):
	texte = "\n\n".join(b.strip("\n") for b in blocs if b and b.strip())
	return re.sub(r"\n{3,}", "\n\n", texte).strip() + "\n"


# ---------------------------------------------------------------- découpage d'un guide


def lire_guide(fichier):
	"""(clé du guide, [articles]) : chaque article est un dict prêt à enregistrer."""
	from bs4 import BeautifulSoup

	cle = os.path.basename(fichier)[len("guide-") : -len(".html")]
	with open(fichier, encoding="utf-8") as f:
		soup = BeautifulSoup(f.read(), "html.parser")
	wrap = soup.select_one("div.wrap") or soup
	titre_cat = CATEGORIES[cle][0]
	ecrans = ECRANS.get(cle, {})
	sections = wrap.find_all("section", recursive=False)
	etapes = wrap.select("article.step[id]")
	slug_vue, slug_msg = f"{cle}-vue-d-ensemble", f"{cle}-messages"

	# les morceaux : (slug, titre, [éléments], écrans, id de l'ancre)
	morceaux = []
	vue, msgs, par_module = [], [], []
	for section in sections:
		h2 = section.find("h2", id=True)
		ident = h2.get("id") if h2 else ""
		if section.select_one("article.step"):
			continue
		if ident in MESSAGES:
			msgs.append(section)
		elif cle == "reglages" and ident.startswith("r-"):
			par_module.append((ident, section))
		else:
			vue.append(section)

	liens = {}
	for section in vue:
		for h2 in section.find_all(["h2"], id=True):
			liens[h2["id"]] = f"/bureau/aide/a/{slug_vue}"
	for section in msgs:
		for h2 in section.find_all(["h2"], id=True):
			liens[h2["id"]] = f"/bureau/aide/a/{slug_msg}"
	for step in etapes:
		liens[step["id"]] = f"/bureau/aide/a/{cle}-{step['id']}"
	for ident, _section in par_module:
		liens[ident] = f"/bureau/aide/a/{cle}-{ident[2:]}"
	conv = Convertisseur(liens | LIENS_GUIDES)

	header = wrap.find("header")
	lead = header.select_one("p.lead") if header else None
	resume_vue = conv.texte(lead) if lead else ""
	blocs_vue = []
	if header:
		blocs_vue += [conv.texte(lead)] if lead else []
		where = header.select_one(".where")
		blocs_vue += conv.blocs(where) if where else []
	for section in vue:
		blocs_vue += conv.blocs(section)
	morceaux.append(
		{
			"slug": slug_vue,
			"titre": f"{titre_cat} : vue d'ensemble",
			"resume": resume_vue,
			"markdown": markdown(blocs_vue),
			"ecrans": ecrans.get("_vue", []),
			"source": f"guide-{cle}#vue",
		}
	)

	tous_ecrans = list(ecrans.get("_vue", []))
	for step in etapes:
		ident = step["id"]
		body = step.select_one(".step-body") or step
		h2 = body.find("h2")
		why = body.select_one("p.why")
		blocs = []
		for c in body.children:
			if c is h2:
				continue
			# dans une étape, les h3 (« Comment faire », « Bon à savoir ») deviennent des h2, pour le sommaire
			blocs += conv.blocs(c, titre=1)
		pris = ecrans.get(ident, ecrans.get("_defaut", []))
		tous_ecrans += pris
		morceaux.append(
			{
				"slug": f"{cle}-{ident}",
				"titre": re.sub(r"\s*\*\(.*\)\*$", "", conv.texte(h2)) if h2 else ident,
				"resume": conv.texte(why) if why else "",
				"markdown": markdown(blocs),
				"ecrans": pris,
				"source": f"guide-{cle}#{ident}",
			}
		)

	for ident, section in par_module:
		h2 = section.find("h2")
		head = section.select_one(".section-head p")
		blocs = [b for c in section.children for b in conv.blocs(c, titre=1) if not b.startswith("# ")]
		pris = ecrans.get(ident, [])
		tous_ecrans += pris
		morceaux.append(
			{
				"slug": f"{cle}-{ident[2:]}",
				"titre": f"Réglages : {conv.texte(h2)}" if h2 else ident,
				"resume": conv.texte(head) if head else f"Les réglages du module {conv.texte(h2)}.",
				"markdown": markdown(blocs),
				"ecrans": pris,
				"source": f"guide-{cle}#{ident}",
			}
		)

	if msgs:
		blocs = []
		for section in msgs:
			blocs += conv.blocs(section)
		morceaux.append(
			{
				"slug": slug_msg,
				"titre": f"{titre_cat} : messages et raccourcis",
				"resume": "Ce que veulent dire les messages de blocage, et les raccourcis clavier.",
				"markdown": markdown(blocs),
				"ecrans": list(dict.fromkeys(tous_ecrans)),
				"source": f"guide-{cle}#messages",
			}
		)
	for i, morceau in enumerate(morceaux, 1):
		morceau["ordre"] = i * 10
		morceau["categorie"] = cle
		morceau["ecrans"] = list(dict.fromkeys(morceau["ecrans"]))
	return cle, morceaux


def _liens_guides():
	"""Les liens d'un guide vers un autre (« guide-tarifs.html#calcule ») : vers l'article correspondant."""
	liens = {}
	for cle in CATEGORIES:
		liens[f"guide-{cle}.html"] = f"/bureau/aide/a/{cle}-vue-d-ensemble"
	return liens


LIENS_GUIDES = _liens_guides()


def _completer_liens_guides():
	"""Ajoute aux liens entre guides les ancres de chaque étape (une lecture rapide des fichiers)."""
	for fichier in fichiers():
		cle = os.path.basename(fichier)[len("guide-") : -len(".html")]
		with open(fichier, encoding="utf-8") as f:
			for ident in re.findall(r'<article class="step[^"]*" id="([^"]+)"', f.read()):
				LIENS_GUIDES[f"guide-{cle}.html#{ident}"] = f"/bureau/aide/a/{cle}-{ident}"


def fichiers():
	if not os.path.isdir(GUIDES):
		return []
	return sorted(
		os.path.join(GUIDES, f)
		for f in os.listdir(GUIDES)
		if f.startswith("guide-") and f.endswith(".html") and f[len("guide-") : -len(".html")] in CATEGORIES
	)


# ---------------------------------------------------------------- enregistrement


def empreinte(morceau):
	brut = "\x1f".join(
		[morceau["titre"], morceau["resume"], morceau["markdown"], "\n".join(morceau["ecrans"])]
	)
	return hashlib.sha256(brut.encode("utf-8")).hexdigest()[:32]


def _empreinte_actuelle(doc):
	return empreinte(
		{
			"titre": doc.titre or "",
			"resume": doc.resume or "",
			"markdown": doc.contenu_markdown or "",
			"ecrans": (doc.ecrans or "").split(),
		}
	)


def _categorie(cle):
	titre, description, icone, ordre = CATEGORIES[cle]
	if frappe.db.exists("Categorie Aide", cle):
		return
	frappe.get_doc(
		{
			"doctype": "Categorie Aide",
			"slug": cle,
			"titre": titre,
			"description": description,
			"icone": icone,
			"ordre": ordre,
		}
	).insert(ignore_permissions=True)


def importer(guides=None):
	"""Crée ou met à jour les articles tirés des guides. Rend {crees, mis_a_jour, inchanges, gardes}."""
	_completer_liens_guides()
	bilan = {"crees": [], "mis_a_jour": [], "inchanges": [], "gardes": []}
	for fichier in fichiers():
		cle, morceaux = lire_guide(fichier)
		if guides and cle not in guides:
			continue
		_categorie(cle)
		for morceau in morceaux:
			signe = empreinte(morceau)
			valeurs = {
				"titre": morceau["titre"],
				"categorie": morceau["categorie"],
				"resume": morceau["resume"],
				"contenu_markdown": morceau["markdown"],
				"ecrans": "\n".join(morceau["ecrans"]),
				"ordre": morceau["ordre"],
				"source": morceau["source"],
				"empreinte_source": signe,
			}
			if not frappe.db.exists("Article Aide", morceau["slug"]):
				frappe.get_doc(
					{"doctype": "Article Aide", "slug": morceau["slug"], "statut": "Publié", **valeurs}
				).insert(ignore_permissions=True)
				bilan["crees"].append(morceau["slug"])
				continue
			doc = frappe.get_doc("Article Aide", morceau["slug"])
			if doc.empreinte_source == signe:
				bilan["inchanges"].append(doc.name)
			elif doc.empreinte_source and _empreinte_actuelle(doc) != doc.empreinte_source:
				bilan["gardes"].append(doc.name)  # retouché à la main depuis l'import : on n'y touche pas
			else:
				doc.update(valeurs)
				doc.save(ignore_permissions=True)
				bilan["mis_a_jour"].append(doc.name)
	if bilan["gardes"]:
		print("Articles modifiés à la main, laissés tels quels :", ", ".join(bilan["gardes"]))
	print(
		f"Aide : {len(bilan['crees'])} créé(s), {len(bilan['mis_a_jour'])} mis à jour, "
		f"{len(bilan['inchanges'])} inchangé(s), {len(bilan['gardes'])} gardé(s)."
	)
	return bilan
