# Copyright (c) 2026, Intrapro and contributors
# For license information, please see license.txt
"""Rendu Markdown → HTML assaini des articles d'aide, à l'enregistrement : le bureau affiche `contenu_html` tel quel.

Le Markdown passe par markdown2 (`md_to_html`) puis par une liste blanche bleach. Les gabarits ajoutés ensuite
(boutons, champs, pastilles, encadrés) sont construits ici, à partir de texte déjà échappé : un texte saisi ne peut
pas produire d'autre balise que les leurs.

Conventions, pour garder le langage visuel des guides :
- `:btn[Valider]`, `:alt[Modifier]` : un bouton principal, un bouton secondaire ;
- `:champ[Client]` : un champ de l'écran ;
- `:chemin[Ventes > Devis]` : un chemin dans le menu ;
- `:pastille-vert[Payée]` (vert, bleu, ambre, rouge, gris) : une pastille de statut ;
- un bloc de citation qui commence par `[!astuce]`, `[!attention]` ou `[!info]` : un encadré ;
- `<kbd>Ctrl</kbd>` : une touche.
"""

import math
import re
import unicodedata

from frappe.utils import md_to_html, strip_html

ALLOWED_TAGS = frozenset(
	{
		"p", "br", "hr", "h2", "h3", "h4", "strong", "em", "b", "i", "u", "s", "code", "pre",
		"blockquote", "ul", "ol", "li", "a", "img", "table", "thead", "tbody", "tr", "th", "td", "kbd", "sup",
	}
)  # fmt: skip
ALLOWED_ATTRIBUTES = {
	"a": ["href", "title"],
	"img": ["src", "alt", "title"],
	"th": ["align"],
	"td": ["align"],
	"ol": ["start"],
}
ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto"})
SCRIPT_BLOCK = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)

PASTILLES = ("vert", "bleu", "ambre", "rouge", "gris")
DIRECTIVE = re.compile(
	r":(btn|alt|champ|chemin|pastille-(?:" + "|".join(PASTILLES) + r"))\[([^\]\n<]{1,120})\]"
)
ENCADRES = {"astuce": "Astuce", "attention": "Attention", "info": "À savoir"}
ENCADRE = re.compile(
	r"<blockquote>\s*<p>\s*\[!(astuce|attention|info)\]\s*(.*?)</blockquote>", re.IGNORECASE | re.DOTALL
)
TITRE = re.compile(r"<(h2|h3)>(.*?)</\1>", re.DOTALL)
MOTS_PAR_MINUTE = 200
ECRAN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _clean(fragment):
	import bleach

	return bleach.clean(
		SCRIPT_BLOCK.sub("", fragment or ""),
		tags=ALLOWED_TAGS,
		attributes=ALLOWED_ATTRIBUTES,
		protocols=ALLOWED_PROTOCOLS,
		strip=True,
	)


def ancre(texte):
	"""« Faire un devis » → « faire-un-devis » : l'identifiant d'un titre, pour le sommaire."""
	plain = "".join(
		c for c in unicodedata.normalize("NFD", strip_html(texte).lower()) if unicodedata.category(c) != "Mn"
	)
	return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:60] or "section"


def _directive(match):
	kind, texte = match.group(1), match.group(2).strip()
	if kind == "btn":
		return f'<span class="aide-btn">{texte}</span>'
	if kind == "alt":
		return f'<span class="aide-btn aide-btn-alt">{texte}</span>'
	if kind == "champ":
		return f'<span class="aide-champ">{texte}</span>'
	if kind == "chemin":
		parts = [part.strip() for part in re.split(r"&gt;|›", texte) if part.strip()]  # noqa: RUF001
		return '<span class="aide-chemin">' + '<i aria-hidden="true">›</i>'.join(parts) + "</span>"  # noqa: RUF001
	return f'<span class="aide-pastille aide-pastille-{kind.split("-", 1)[1]}">{texte}</span>'


def _encadre(match):
	kind = match.group(1).lower()
	return (
		f'<aside class="aide-encadre aide-encadre-{kind}"><p><strong>{ENCADRES[kind]} : </strong>'
		f"{match.group(2).strip()}</aside>"
	)


def _titres(html):
	vus = {}

	def remplacer(match):
		base = ancre(match.group(2))
		vus[base] = vus.get(base, 0) + 1
		ident = base if vus[base] == 1 else f"{base}-{vus[base]}"
		return f'<{match.group(1)} id="{ident}">{match.group(2)}</{match.group(1)}>'

	return TITRE.sub(remplacer, html)


def rendre(markdown):
	"""(HTML assaini, durée de lecture en minutes) d'un article."""
	html = _clean(md_to_html(markdown or ""))
	html = DIRECTIVE.sub(_directive, html)
	html = ENCADRE.sub(_encadre, html)
	html = _titres(html)
	mots = len(strip_html(html).split())
	return html, max(1, math.ceil(mots / MOTS_PAR_MINUTE)) if mots else 0


def sommaire(html):
	"""Les titres h2 d'un article rendu : [{id, titre}]."""
	return [
		{"id": ident, "titre": strip_html(titre).strip()}
		for ident, titre in re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', html or "", re.DOTALL)
	]


def nettoyer_ecrans(valeur):
	"""Les identifiants d'écrans, un par ligne, sans doublon ni valeur invalide."""
	vus = []
	for ecran in re.split(r"[\s,;]+", valeur or ""):
		ecran = ecran.strip().lower()
		if ecran and ECRAN.match(ecran) and ecran not in vus:
			vus.append(ecran)
	return "\n".join(vus)


_DIRECTIVE = re.compile(r":(?:btn|alt|champ|chemin|pastille-[a-z]+)\[([^\]\n]*)\]")
_LIEN = re.compile(r"!?\[([^\]\n]*)\]\([^)\n]*\)")
_EMPHASE = re.compile(r"(\*\*|__|\*|`)(?=\S)(.+?)(?<=\S)\1")


def texte_brut(md):
	"""Un texte court en Markdown (le résumé) sans sa syntaxe : `**x**`, `:champ[x]`, `[x](lien)` → x."""
	texte = _DIRECTIVE.sub(r"\1", md or "")
	texte = _LIEN.sub(r"\1", texte)
	texte = _EMPHASE.sub(r"\2", texte)
	return re.sub(r"\s+", " ", strip_html(texte)).strip()
