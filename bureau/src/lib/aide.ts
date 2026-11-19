/** Centre d'aide du bureau : l'écran ouvert, le panneau « ? », les liens internes des articles. Le contenu vient du serveur (unicare/api/bureau_aide.py). */
import { ref } from 'vue'

export interface AideCarte {
	slug: string
	titre: string
	categorie: string
	resume: string
	duree_lecture: number
	/** Recherche : le passage du texte autour du mot trouvé. */
	extrait?: string
	/** Recherche : les sections du meilleur résultat. */
	sommaire?: AideTitre[]
}
export interface AideCategorie {
	slug: string
	titre: string
	description: string
	icone: string
	articles: AideCarte[]
}
export interface AideAccueil {
	categories: AideCategorie[]
	sur_cette_page: AideCarte[]
	peut_editer: boolean
}
export interface AideRecherche {
	page: AideCarte[]
	autres: AideCarte[]
}
export interface AideTitre {
	id: string
	titre: string
}
export interface AideArticle {
	slug: string
	titre: string
	resume: string
	statut: AideStatut
	html: string
	sommaire: AideTitre[]
	duree_lecture: number
	date_revision: string
	ecrans: string[]
	categorie: { slug: string; titre: string } | null
	precedent: AideCarte | null
	suivant: AideCarte | null
	peut_editer: boolean
}
export type AideStatut = 'Brouillon' | 'Publié'
export interface AideEdition {
	slug: string
	titre: string
	categorie: string
	statut: AideStatut
	ordre: number
	resume: string
	contenu_markdown: string
	html: string
	ecrans: string[]
	mots_cles: string
	source: string
	date_revision: string
	duree_lecture: number
	modified: string
}
export type AideValeurs = Partial<Pick<AideEdition, 'titre' | 'categorie' | 'statut' | 'ordre' | 'resume' | 'contenu_markdown' | 'ecrans' | 'mots_cles'>>
export interface AideListeArticle {
	slug: string
	titre: string
	categorie: string
	statut: AideStatut
	ordre: number
	resume: string
	ecrans: string[]
	source: string
}
export interface AideListe {
	categories: { slug: string; titre: string; description: string; icone: string; ordre: number; modified: string }[]
	articles: AideListeArticle[]
	statuts: AideStatut[]
}
export interface AideApercu {
	html: string
	sommaire: AideTitre[]
	duree_lecture: number
}

/** L'écran ouvert : l'`id` de l'entrée du menu, que la coquille du bureau tient à jour. */
export const ecranCourant = ref('')
/** Le panneau d'aide : fermé (`null`), ouvert sur l'accueil (`''`) ou sur un article (son slug). */
export const aidePanneau = ref<string | null>(null)

export function ouvrirAide(slug = '') {
	aidePanneau.value = slug
}
export function basculerAide() {
	aidePanneau.value = aidePanneau.value === null ? '' : null
}

/** Un sommaire n'aide qu'à partir de trois titres. */
export const SOMMAIRE_MIN = 3
export function sommaireUtile(sommaire: AideTitre[] | undefined) {
	return (sommaire?.length ?? 0) >= SOMMAIRE_MIN
}

export function dureeLabel(minutes: number) {
	return minutes ? `${minutes} min de lecture` : ''
}

const PREFIXE = '/bureau/aide/a/'
/** « /bureau/aide/a/ventes-devis#comment-faire » → { slug, ancre } ; un autre lien → `null`. */
export function lienArticle(href: string | null | undefined): { slug: string; ancre: string } | null {
	if (!href) return null
	let chemin = href
	try {
		const url = new URL(href, window.location.origin)
		if (url.origin !== window.location.origin) return null
		chemin = url.pathname + url.hash
	} catch {
		return null
	}
	if (!chemin.startsWith(PREFIXE)) return null
	const [slug, ancre = ''] = chemin.slice(PREFIXE.length).split('#')
	return slug ? { slug: decodeURIComponent(slug), ancre } : null
}

function saisie(target: EventTarget | null) {
	const element = target as HTMLElement | null
	return Boolean(element && (element.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(element.tagName)))
}
/** « ? » ouvre l'aide de n'importe quelle page : pas pendant une saisie, ni sous une fenêtre ouverte. */
export function estRaccourciAide(event: KeyboardEvent) {
	if (event.key !== '?' || event.ctrlKey || event.metaKey || event.altKey) return false
	return !saisie(event.target) && !document.querySelector('.dialog-scrim')
}

/** L'aide-mémoire de l'éditeur : ce qu'on tape, et ce que ça donne. */
export const CONVENTIONS: { code: string; rendu: string }[] = [
	{ code: '## Titre', rendu: 'Une section ; trois sections ou plus font un sommaire' },
	{ code: ':btn[Valider]', rendu: 'Un bouton principal' },
	{ code: ':alt[Modifier]', rendu: 'Un bouton secondaire' },
	{ code: ':champ[Client]', rendu: "Un champ de l'écran" },
	{ code: ':chemin[Ventes > Devis]', rendu: 'Un chemin dans le menu' },
	{ code: ':pastille-vert[Payée]', rendu: 'Une pastille : vert, bleu, ambre, rouge ou gris' },
	{ code: '<kbd>N</kbd>', rendu: 'Une touche du clavier' },
	{ code: '> [!astuce] Texte', rendu: 'Un encadré : astuce, attention ou info' },
	{ code: '[texte](/bureau/aide/a/ventes-devis)', rendu: 'Un lien vers un autre article' },
]

/** Les libellés des écrans d'un article, dans l'ordre du menu ; un écran inconnu garde son identifiant. */
export function ecransLabels(ids: string[], ecrans: { id: string; label: string }[]) {
	return ids.map((id) => ecrans.find((ecran) => ecran.id === id)?.label ?? id)
}

function plain(texte: string) {
	return texte
		.normalize('NFD')
		.replace(/[̀-ͯ]/g, '')
		.toLowerCase()
}
/** Réglages › Aide : les articles d'un statut dont le titre, le résumé ou un écran contiennent chaque mot tapé. */
export function filtrerArticlesAide<T extends { titre: string; resume: string; statut: AideStatut; ecrans: string[] }>(articles: T[], recherche: string, statut: 'tous' | AideStatut) {
	const mots = plain(recherche).split(/\s+/).filter(Boolean)
	return articles.filter((article) => {
		if (statut !== 'tous' && article.statut !== statut) return false
		const texte = plain([article.titre, article.resume, ...article.ecrans].join(' '))
		return mots.every((mot) => texte.includes(mot))
	})
}

/** Les mots que les gens cherchent le plus, proposés sous la recherche du centre d'aide. */
export const SUGGESTIONS = ['Faire un devis', 'Inventaire', 'Encaisser', 'TVA', 'Mot de passe']

/** Les rubriques des circuits de tous les jours ; les autres sont des réglages. */
export const RUBRIQUES_QUOTIDIEN = ['ventes', 'achats', 'stock', 'production']

/** « Réglages : Ventes » dans la rubrique « Réglages » → « Ventes ». */
export function titreCourt(titre: string, rubrique: string) {
	const prefixe = `${rubrique} : `
	return titre.startsWith(prefixe) ? titre.slice(prefixe.length) : titre
}

export interface AideRubrique extends AideCategorie {
	vueEnsemble: AideCarte | null
	messages: AideCarte | null
	/** Les articles de la rubrique hors vue d'ensemble et messages, titres raccourcis. */
	etapes: AideCarte[]
}
/** Les rubriques de l'accueil, en deux groupes : le quotidien (des circuits, étape par étape) et les réglages. */
export function rangerRubriques(categories: AideCategorie[]) {
	const rubriques: AideRubrique[] = categories.map((cat) => ({
		...cat,
		vueEnsemble: cat.articles.find((a) => a.slug.endsWith('-vue-d-ensemble')) ?? null,
		messages: cat.articles.find((a) => a.slug.endsWith('-messages')) ?? null,
		etapes: cat.articles
			.filter((a) => !a.slug.endsWith('-vue-d-ensemble') && !a.slug.endsWith('-messages'))
			.map((a) => ({ ...a, titre: titreCourt(a.titre, cat.titre) })),
	}))
	return {
		quotidien: rubriques.filter((r) => RUBRIQUES_QUOTIDIEN.includes(r.slug)),
		reglages: rubriques.filter((r) => !RUBRIQUES_QUOTIDIEN.includes(r.slug)),
	}
}

/** Le texte découpé en morceaux, ceux qui contiennent un mot cherché marqués (sans tenir compte des accents). */
export function surligner(texte: string, recherche: string): { texte: string; trouve: boolean }[] {
	const mots = plain(recherche)
		.split(/\s+/)
		.filter((mot) => mot.length > 1)
	if (!texte || !mots.length) return texte ? [{ texte, trouve: false }] : []
	// une lettre accentuée devient une seule lettre sans accent : les positions restent celles du texte d'origine
	const normal = texte
		.split('')
		.map((c) => plain(c).charAt(0) || c)
		.join('')
	const marque = new Array<boolean>(texte.length).fill(false)
	for (const mot of mots) {
		for (let i = normal.indexOf(mot); i >= 0; i = normal.indexOf(mot, i + mot.length)) marque.fill(true, i, i + mot.length)
	}
	const morceaux: { texte: string; trouve: boolean }[] = []
	for (let i = 0; i < texte.length; i++) {
		const dernier = morceaux[morceaux.length - 1]
		if (dernier && dernier.trouve === marque[i]) dernier.texte += texte[i]
		else morceaux.push({ texte: texte[i], trouve: marque[i] })
	}
	return morceaux
}
