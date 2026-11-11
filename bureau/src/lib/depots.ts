/** Règles de la page Dépôts : types, vues et colonnes. */
import type { CommentPart } from '@shared/activity'
import { formatDay } from './display'
import { canRead } from './droits'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { LedgerRow } from './stock'
import type { ListResponse } from './useServerList'

export type DepotView = 'all' | 'actifs' | 'desactives' | 'avec_stock'

/** La valeur et le nombre d'articles viennent du stock : réservés à qui lit les quantités par dépôt. */
export const STOCK_DOCTYPE = 'Bin'

export const DEPOT_VIEWS: { key: DepotView; label: string; doctype?: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'actifs', label: 'Actifs' },
	{ key: 'avec_stock', label: 'Avec stock', doctype: STOCK_DOCTYPE },
	{ key: 'desactives', label: 'Désactivés' },
]

export interface DepotRow {
	name: string
	modified: string
	creation: string
	depot: string
	parent: string | null
	type: string | null
	desactive: number
	/** null : la personne ne lit pas le stock. */
	articles: number | null
	valeur: number | null
	tags: string[]
	cloche: boolean
}

export interface DepotsResponse extends ListResponse {
	depots: DepotRow[]
	counts: Record<DepotView, number>
	page_length: number
}

export interface DepotStockRow {
	article: string
	designation: string
	quantite: number
	reserve: number
	projete: number
	unite: string | null
	valeur: number
}

export interface DepotDetail {
	name: string
	modified: string
	tags: string[]
	depot: string
	parent: string | null
	type: string | null
	desactive: number
	groupe: number
	compte: string | null
	articles: number | null
	valeur: number | null
	can_edit: boolean
	can_delete: boolean
	/** Fiche seulement. null : la personne ne lit pas le stock ou le grand livre. */
	stock?: DepotStockRow[] | null
	mouvements?: LedgerRow[] | null
	comments?: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface DepotOptions {
	filter_fields?: FilterField[]
	groupes: string[]
	types: string[]
}

export interface DepotValues {
	depot?: string
	parent?: string
	type?: string
	desactive?: number
}

export const DEPOT_COLUMNS: Column<DepotRow>[] = [
	{ key: 'depot', label: 'Dépôt', width: 220, minWidth: 140, grow: 2, sortable: true, text: (row) => row.depot },
	{ key: 'parent', label: 'Groupe', width: 180, minWidth: 96, grow: 1, sortable: true, text: (row) => row.parent || '' },
	{ key: 'type', label: 'Type', width: 110, minWidth: 72, sortable: true, text: (row) => row.type || '' },
	{ key: 'articles', label: 'Articles en stock', width: 130, minWidth: 80, sortable: true, end: true, text: (row) => row.articles ?? '' },
	{ key: 'valeur', label: 'Valeur (DA)', width: 130, minWidth: 88, sortable: true, end: true, text: (row) => Math.round(row.valeur ?? 0) },
	{ key: 'tags', label: 'Tags', width: 150, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'name', label: 'Code', width: 200, minWidth: 96, sortable: true, optional: true, text: (row) => row.name },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_DEPOT_COLUMNS = DEPOT_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function allowedDepotViews() {
	return DEPOT_VIEWS.filter((view) => canRead(view.doctype))
}
export function allowedDepotColumns() {
	return canRead(STOCK_DOCTYPE) ? DEPOT_COLUMNS : DEPOT_COLUMNS.filter((column) => column.key !== 'articles' && column.key !== 'valeur')
}

export function depotSortText(sort: Sort | null) {
	const column = sort && DEPOT_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : nom'
}
