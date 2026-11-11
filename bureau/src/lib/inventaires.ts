/** Règles de la page Inventaires : types, vues, colonnes et saisie du comptage. */
import type { CommentPart } from '@shared/activity'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { Versions } from './versions'
import type { ListResponse } from './useServerList'

export type InventaireView = 'all' | 'brouillons' | 'valides' | 'annules'

export const INVENTAIRE_VIEWS: { key: InventaireView; label: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'brouillons', label: 'En cours de comptage' },
	{ key: 'valides', label: 'Validés' },
	{ key: 'annules', label: 'Annulés' },
]

export interface InventaireRow {
	name: string
	modified: string
	creation: string
	status: string
	date: string | null
	depot: string | null
	lignes: number
	/** Écart de valeur, connu une fois l'inventaire validé ; null pour un brouillon. */
	ecart: number | null
	tags: string[]
	cloche: boolean
}

export interface InventairesResponse extends ListResponse {
	inventaires: InventaireRow[]
	counts: Record<InventaireView, number>
	page_length: number
}

export interface InventaireLine {
	name: string
	article: string
	designation: string
	groupe: string | null
	depot: string
	lot: string | null
	unite: string | null
	/** Brouillon : le stock d'aujourd'hui ; validé : celui qu'ERPNext a figé à la validation. */
	theorique: number
	compte: number
	ecart: number
	taux: number
	ecart_valeur: number
}

export interface InventaireResume {
	lignes: number
	ecarts: number
	plus: number
	moins: number
	valeur: number
}

export type InventaireAction = 'compter' | 'valider' | 'supprimer' | 'annuler' | 'nouvelle_version'

export interface InventaireDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	status: string
	docstatus: number
	date: string | null
	depot: string | null
	cree_par: string
	lignes: InventaireLine[]
	resume: InventaireResume
	version_de: string | null
	versions: Versions
	actions: InventaireAction[]
	blocked: string[]
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface InventaireOptions {
	filter_fields?: FilterField[]
	depots: string[]
	groupes: string[]
}

export const INVENTAIRE_COLUMNS: Column<InventaireRow>[] = [
	{ key: 'name', label: 'Inventaire', width: 170, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'status', label: 'Statut', width: 110, minWidth: 88, sortable: false, text: (row) => row.status },
	{ key: 'date', label: 'Date', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.date) },
	{ key: 'depot', label: 'Dépôt', width: 180, minWidth: 96, grow: 1, sortable: true, text: (row) => row.depot || '' },
	{ key: 'lignes', label: 'Lignes', width: 80, minWidth: 56, sortable: true, end: true, text: (row) => row.lignes },
	{ key: 'ecart', label: 'Écart (DA)', width: 120, minWidth: 88, sortable: true, end: true, text: (row) => (row.ecart === null ? '' : Math.round(row.ecart)) },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_INVENTAIRE_COLUMNS = INVENTAIRE_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function inventaireSortText(sort: Sort | null) {
	const column = sort && INVENTAIRE_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récents'
}

/** Nombre saisi à la française ; NaN si illisible. */
export function parseCount(value: string) {
	const text = value.replace(/[\s ]/g, '').replace(',', '.')
	return text === '' ? NaN : Number(text)
}

/** Lignes dont le comptage saisi diffère de la dernière version enregistrée. */
export function changedCounts(lines: InventaireLine[], counts: Record<string, string>) {
	return lines
		.filter((line) => counts[line.name] !== undefined && parseCount(counts[line.name]) !== line.compte)
		.map((line) => ({ name: line.name, quantite: parseCount(counts[line.name]) }))
}

/** Résumé des écarts de la saisie en cours : lignes, plus, moins et valeur. */
export function resumeSaisie(lines: InventaireLine[], counts: Record<string, string>): InventaireResume {
	let ecarts = 0
	let plus = 0
	let moins = 0
	let valeur = 0
	for (const line of lines) {
		const compte = counts[line.name] !== undefined ? parseCount(counts[line.name]) : line.compte
		if (!Number.isFinite(compte)) continue
		const ecart = Math.round((compte - line.theorique) * 1000) / 1000
		if (!ecart) continue
		ecarts += 1
		if (ecart > 0) plus += ecart
		else moins += ecart
		valeur += ecart * line.taux
	}
	return { lignes: lines.length, ecarts, plus: Math.round(plus * 1000) / 1000, moins: Math.round(moins * 1000) / 1000, valeur: Math.round(valeur * 100) / 100 }
}
