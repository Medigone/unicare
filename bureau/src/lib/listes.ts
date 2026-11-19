/** Réglages › Listes de choix : valeurs des listes déroulantes du bureau (unicare/api/bureau_listes.py). */

export type ListeCode = 'raisons' | 'clients' | 'fournisseurs' | 'articles' | 'unites'
export type ListeModule = 'ventes' | 'achats' | 'stock'

export interface ListeResume {
	code: ListeCode
	label: string
	aide: string
	/** Module où la liste sert : range la liste dans la page. */
	module: ListeModule
	total: number
	/** Unités seulement : celles proposées dans les listes. */
	actifs: number | null
	/** Valeurs que rien n'utilise (unités : parmi les proposées). */
	inutilisees: number
	/** Fiches classées avec une valeur de la liste (null pour les unités). */
	fiches: number | null
	/** Page du bureau qui liste les fiches d'une valeur, filtrée sur `doctype.champ` ; `fiches` les nomme. */
	lien: { page: string; doctype: string; champ: string; fiches: string }
	/** La liste accepte la fusion d'une valeur dans une autre (pas les unités). */
	fusion: boolean
	/** Catégories et groupes : les valeurs sont rangées dans des dossiers. */
	arbre: boolean
	dossiers: number
	droits: { creer: boolean; modifier: boolean; supprimer: boolean; renommer_utilisee: boolean }
}

export interface ListeValeur {
	name: string
	modified: string
	/** Fiches et pièces qui l'utilisent : une valeur utilisée ne se supprime pas. */
	usages: number
	/** Détail des usages par source : { articles: 64, prix: 120 }. */
	detail?: Record<string, number>
	actif: boolean
	/** Unités : quantités entières seulement. */
	entier?: boolean
	/** Arbre : un dossier range des valeurs, il ne se choisit pas sur une fiche. */
	dossier?: boolean
	/** Arbre : le dossier qui la contient ; null à la racine. */
	parent?: string | null
}

/** Une ligne de l'arbre affiché : la valeur, sa profondeur et, pour un dossier, ce qu'il contient. */
export interface LigneArbre {
	valeur: ListeValeur
	niveau: number
	ouvert: boolean
	/** Dossier : nombre de valeurs (non dossiers) qu'il contient, à tous les niveaux. */
	contenu: number
	/** Dossier : nombre direct d'enfants (valeurs et sous-dossiers). */
	enfants: number
	/** Dossier : somme des usages de ses valeurs. */
	usagesTotal: number
}

/** Deux valeurs qui ne diffèrent que par les accents, la casse ou le pluriel : fusionner `source` dans `cible`. */
export interface Doublon {
	source: string
	cible: string
	usages: number
}

export interface FichesValeur {
	total: number
	fiches: { name: string; titre: string }[]
}

export type ValeurVue = 'toutes' | 'utilisees' | 'inutilisees' | 'proposees' | 'retirees'
/** Ancien nom, gardé pour les unités. */
export type UniteVue = 'actives' | 'toutes'

export const MODULES: { key: ListeModule; label: string }[] = [
	{ key: 'ventes', label: 'Ventes' },
	{ key: 'achats', label: 'Achats' },
	{ key: 'stock', label: 'Stock' },
]

/** Filtres de la liste : « Proposées / Retirées » pour les unités, « Utilisées / Inutilisées » ailleurs. */
export function vuesDe(code: ListeCode): { key: ValeurVue; label: string }[] {
	return code === 'unites'
		? [
				{ key: 'proposees', label: 'Proposées' },
				{ key: 'retirees', label: 'Retirées' },
				{ key: 'toutes', label: 'Toutes' },
			]
		: [
				{ key: 'toutes', label: 'Toutes' },
				{ key: 'utilisees', label: 'Utilisées' },
				{ key: 'inutilisees', label: 'Inutilisées' },
			]
}

export function dansVue(row: ListeValeur, vue: ValeurVue | UniteVue | undefined) {
	if (vue === 'proposees' || vue === 'actives') return row.actif
	if (vue === 'retirees') return !row.actif
	if (vue === 'utilisees') return row.usages > 0
	if (vue === 'inutilisees') return !row.usages
	return true
}

/** Filtre sans tenir compte des accents ni de la casse, puis selon la vue. */
export function filtrerValeurs(valeurs: ListeValeur[], recherche: string, vue?: ValeurVue | UniteVue): ListeValeur[] {
	const plain = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
	const mots = plain(recherche).split(/\s+/).filter(Boolean)
	return valeurs.filter((row) => dansVue(row, vue) && mots.every((mot) => plain(row.name).includes(mot)))
}

/** Singulier d'un nom de fiches : « clients » → « client », « lignes de recette » → « ligne de recette » ; « devis » et « prix » ne changent pas. */
export function singulier(mot: string) {
	const [premier, ...reste] = mot.split(' ')
	if (['devis', 'prix'].includes(premier) || !premier.endsWith('s')) return mot
	return [premier.slice(0, -1), ...reste].join(' ')
}

/** « 142 clients », « 1 fiche », « Inutilisée ». */
export function usagesLabel(usages: number, mot = 'fiches'): string {
	if (!usages) return 'Inutilisée'
	return `${usages} ${usages > 1 ? mot : singulier(mot)}`
}

/** « 64 articles · 120 prix · 18 lignes de recette » (les sources dans l'ordre reçu). */
export function detailLabel(detail?: Record<string, number>) {
	return Object.entries(detail ?? {})
		.filter(([, n]) => n > 0)
		.map(([source, n]) => usagesLabel(n, source))
		.join(' · ')
}

/** Lien vers la page qui liste les fiches d'une valeur, filtrée sur elle. */
export function lienFiches(liste: Pick<ListeResume, 'lien'>, valeur: string) {
	return { name: liste.lien.page, query: { filtres: JSON.stringify([[liste.lien.doctype, liste.lien.champ, '=', valeur]]) } }
}

/**
 * L'arbre à afficher, à plat dans l'ordre de lecture : dossiers d'abord, puis valeurs, par nom.
 * Une recherche ou une vue montre les valeurs qui y répondent avec leurs dossiers, ouverts d'office ; sans filtre,
 * seuls les dossiers de `ouverts` montrent leur contenu.
 */
export function construireArbre(valeurs: ListeValeur[], ouverts: Record<string, boolean>, recherche = '', vue?: ValeurVue): LigneArbre[] {
	const enfants = new Map<string | null, ListeValeur[]>()
	for (const row of valeurs) {
		const cle = row.parent ?? null
		enfants.set(cle, [...(enfants.get(cle) ?? []), row])
	}
	for (const liste of enfants.values()) liste.sort((a, b) => Number(Boolean(b.dossier)) - Number(Boolean(a.dossier)) || a.name.localeCompare(b.name, 'fr'))
	const filtre = Boolean(recherche.trim()) || (vue !== undefined && vue !== 'toutes')
	const retenues = new Set(filtrerValeurs(valeurs.filter((row) => !row.dossier), recherche, vue).map((row) => row.name))

	type Stat = { contenu: number; usages: number; visible: boolean }
	const stats = new Map<string, Stat>()
	function compter(nom: string): Stat {
		let contenu = 0
		let usages = 0
		let visible = false
		for (const enfant of enfants.get(nom) ?? []) {
			if (enfant.dossier) {
				const sous = compter(enfant.name)
				contenu += sous.contenu
				usages += sous.usages
				visible ||= sous.visible
			} else {
				contenu += 1
				usages += enfant.usages
				visible ||= retenues.has(enfant.name)
			}
		}
		const result: Stat = { contenu, usages, visible }
		stats.set(nom, result)
		return result
	}
	for (const row of enfants.get(null) ?? []) if (row.dossier) compter(row.name)

	const lignes: LigneArbre[] = []
	function parcourir(parent: string | null, niveau: number) {
		for (const row of enfants.get(parent) ?? []) {
			if (!row.dossier) {
				if (retenues.has(row.name)) lignes.push({ valeur: row, niveau, ouvert: false, contenu: 0, enfants: 0, usagesTotal: row.usages })
				continue
			}
			const stat = stats.get(row.name)!
			if (filtre && !stat.visible) continue
			const ouvert = filtre || Boolean(ouverts[row.name])
			lignes.push({ valeur: row, niveau, ouvert, contenu: stat.contenu, enfants: (enfants.get(row.name) ?? []).length, usagesTotal: stat.usages })
			if (ouvert) parcourir(row.name, niveau + 1)
		}
	}
	parcourir(null, 1)
	return lignes
}

/** Les dossiers où ranger `valeur`, avec leur profondeur : ni elle-même ni ses sous-dossiers. */
export function dossiersPossibles(valeurs: ListeValeur[], valeur?: ListeValeur | null): { name: string; niveau: number }[] {
	const exclus = new Set<string>()
	if (valeur?.dossier) {
		exclus.add(valeur.name)
		let ajoute = true
		while (ajoute) {
			ajoute = false
			for (const row of valeurs) if (row.dossier && row.parent && exclus.has(row.parent) && !exclus.has(row.name)) {
				exclus.add(row.name)
				ajoute = true
			}
		}
	}
	const result: { name: string; niveau: number }[] = []
	function parcourir(parent: string | null, niveau: number) {
		valeurs
			.filter((row) => row.dossier && (row.parent ?? null) === parent && !exclus.has(row.name))
			.sort((a, b) => a.name.localeCompare(b.name, 'fr'))
			.forEach((row) => {
				result.push({ name: row.name, niveau })
				parcourir(row.name, niveau + 1)
			})
	}
	parcourir(null, 1)
	return result
}

/** « Emballages › Étiquettes » : le chemin d'une valeur depuis la racine. */
export function chemin(valeurs: ListeValeur[], nom: string, parent: string | null | undefined = undefined) {
	const parts = [nom]
	let courant = parent === undefined ? valeurs.find((row) => row.name === nom)?.parent ?? null : parent
	const vus = new Set<string>()
	while (courant && !vus.has(courant)) {
		vus.add(courant)
		parts.unshift(courant)
		courant = valeurs.find((row) => row.name === courant)?.parent ?? null
	}
	return parts.join(' › ')
}
