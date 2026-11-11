/** Règles de la page Mouvements de stock : natures, vues, colonnes et saisie des lignes. */
import type { CommentPart } from '@shared/activity'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { Versions } from './versions'
import type { ListResponse } from './useServerList'

export type MouvementView = 'all' | 'brouillons' | 'transferts' | 'entrees' | 'sorties' | 'ordres' | 'annules'
export type Nature = 'transfert' | 'entree' | 'sortie'

export const MOUVEMENT_VIEWS: { key: MouvementView; label: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'brouillons', label: 'Brouillons' },
	{ key: 'transferts', label: 'Transferts' },
	{ key: 'entrees', label: 'Entrées' },
	{ key: 'sorties', label: 'Sorties' },
	{ key: 'ordres', label: 'Issus des ordres' },
	{ key: 'annules', label: 'Annulés' },
]

/** Les natures saisies dans le bureau, et les dépôts que chacune demande. */
export const NATURES: { key: Nature; label: string; aide: string; source: boolean; cible: boolean }[] = [
	{ key: 'transfert', label: 'Transfert', aide: "D'un dépôt à un autre.", source: true, cible: true },
	{ key: 'entree', label: 'Entrée', aide: 'Stock qui arrive sans réception (stock initial, retour interne…).', source: false, cible: true },
	{ key: 'sortie', label: 'Sortie', aide: 'Consommation, casse, rebut : le stock quitte le dépôt.', source: true, cible: false },
]

const NATURE_LABELS: Record<string, string> = { transfert: 'Transfert', entree: 'Entrée', sortie: 'Sortie', production: 'Production' }
export function natureLabel(nature: string) {
	return NATURE_LABELS[nature] ?? nature
}

export interface MouvementRow {
	name: string
	modified: string
	creation: string
	nature: Nature | 'production'
	type: string
	status: string
	date: string | null
	source: string | null
	cible: string | null
	valeur: number
	/** L'ordre de conditionnement qui a créé ce mouvement : il est alors en lecture seule. */
	ordre: string | null
	remarque: string | null
	lignes: number
	articles: string
	tags: string[]
	cloche: boolean
}

export interface MouvementsResponse extends ListResponse {
	mouvements: MouvementRow[]
	counts: Record<MouvementView, number>
	page_length: number
}

export interface MouvementLine {
	name: string
	article: string
	designation: string
	quantite: number
	unite: string | null
	source: string | null
	cible: string | null
	lots: string[]
	avec_lot: number
	taux: number
	valeur: number
}

export type MouvementAction = 'modifier' | 'valider' | 'supprimer' | 'annuler' | 'nouvelle_version'

export interface MouvementDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	status: string
	docstatus: number
	nature: Nature | 'production'
	type: string
	date: string | null
	source: string | null
	cible: string | null
	remarque: string | null
	ordre: string | null
	/** Piloté par un ordre de conditionnement (ou d'une nature que le bureau ne saisit pas) : lecture seule. */
	depuis_ordre: boolean
	cree_par: string
	lignes: MouvementLine[]
	valeur_sortie: number
	valeur_entree: number
	version_de: string | null
	versions: Versions
	actions: MouvementAction[]
	blocked: string[]
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface MouvementOptions {
	filter_fields?: FilterField[]
	depots: string[]
}

export interface StockArticleChoice {
	name: string
	label: string
	uom: string | null
	avec_lot: number
	/** Stock dans le dépôt de départ ; null : pas de dépôt choisi. */
	stock: number | null
}

/** Une ligne en cours de saisie. La quantité reste du texte ; le lot est choisi (sortie, transfert) ou saisi (entrée). */
export interface MouvementDraftLine {
	key: number
	article: string
	designation: string
	unite: string
	avec_lot: boolean
	quantite: string
	lot: string
	peremption: string
}

export interface MouvementValues {
	nature?: Nature
	source?: string
	cible?: string
	remarque?: string
	lignes?: { article: string; quantite: number; lot: string | null; peremption: string | null }[]
}

export const MOUVEMENT_COLUMNS: Column<MouvementRow>[] = [
	{ key: 'name', label: 'Mouvement', width: 160, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'nature', label: 'Nature', width: 110, minWidth: 80, sortable: true, text: (row) => natureLabel(row.nature) },
	{ key: 'status', label: 'Statut', width: 110, minWidth: 88, sortable: false, text: (row) => row.status },
	{ key: 'date', label: 'Date', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.date) },
	{ key: 'source', label: 'Départ', width: 150, minWidth: 88, sortable: true, text: (row) => row.source || '' },
	{ key: 'cible', label: 'Arrivée', width: 150, minWidth: 88, sortable: true, text: (row) => row.cible || '' },
	{ key: 'articles', label: 'Articles', width: 220, minWidth: 120, grow: 1, sortable: false, text: (row) => row.articles },
	{ key: 'valeur', label: 'Valeur (DA)', width: 120, minWidth: 88, sortable: true, end: true, text: (row) => Math.round(row.valeur) },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'remarque', label: 'Remarque', width: 200, minWidth: 96, sortable: false, optional: true, text: (row) => row.remarque || '' },
	{ key: 'lignes', label: 'Lignes', width: 70, minWidth: 56, sortable: true, end: true, optional: true, text: (row) => row.lignes },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_MOUVEMENT_COLUMNS = MOUVEMENT_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function mouvementSortText(sort: Sort | null) {
	const column = sort && MOUVEMENT_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récents'
}

export interface MouvementErrors {
	nature?: string
	source?: string
	cible?: string
	lignes?: string
	ligne?: Record<number, string>
}

/** Mêmes refus que le serveur à l'enregistrement. Le lot manquant ne bloque que la validation (le brouillon le dit). */
export function validateMouvement(values: { nature: Nature | ''; source: string; cible: string; lignes: MouvementDraftLine[] }) {
	const errors: MouvementErrors = {}
	const nature = NATURES.find((item) => item.key === values.nature)
	if (!nature) errors.nature = 'Choisissez la nature du mouvement.'
	if (nature?.source && !values.source) errors.source = 'Choisissez le dépôt de départ.'
	if (nature?.cible && !values.cible) errors.cible = "Choisissez le dépôt d'arrivée."
	if (nature?.source && nature.cible && values.source && values.source === values.cible) errors.cible = 'Le dépôt d\'arrivée doit être différent du départ.'
	const filled = values.lignes.filter((line) => line.article)
	if (!filled.length) errors.lignes = 'Ajoutez au moins une ligne.'
	const ligne: Record<number, string> = {}
	for (const line of filled) {
		const quantite = Number(line.quantite.replace(/[\s ]/g, '').replace(',', '.'))
		if (!(quantite > 0)) ligne[line.key] = 'Quantité positive attendue.'
	}
	if (Object.keys(ligne).length) errors.ligne = ligne
	return errors
}

export function mouvementLinesForServer(lines: MouvementDraftLine[], nature: Nature) {
	return lines
		.filter((line) => line.article)
		.map((line) => ({
			article: line.article,
			quantite: Number(line.quantite.replace(/[\s ]/g, '').replace(',', '.')),
			lot: line.avec_lot ? line.lot.trim() || null : null,
			peremption: nature === 'entree' && line.avec_lot ? line.peremption || null : null,
		}))
}
