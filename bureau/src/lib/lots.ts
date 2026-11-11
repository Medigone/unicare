/** Règles de la page Lots : types, vues, colonnes et état de péremption. */
import type { CommentPart } from '@shared/activity'
import { dayFromToday } from './devis'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { LedgerRow } from './stock'
import type { ListResponse } from './useServerList'

export type LotView = 'all' | 'avec_stock' | 'expirent' | 'perimes' | 'vides' | 'desactives'

export const LOT_VIEWS: { key: LotView; label: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'avec_stock', label: 'En stock' },
	{ key: 'expirent', label: 'Périment sous 30 jours' },
	{ key: 'perimes', label: 'Périmés en stock' },
	{ key: 'vides', label: 'Épuisés' },
	{ key: 'desactives', label: 'Désactivés' },
]

export interface LotRow {
	name: string
	modified: string
	creation: string
	article: string
	designation: string
	quantite: number
	unite: string | null
	peremption: string | null
	fabrication: string | null
	lot_fournisseur: string | null
	origine: string | null
	ordre: string | null
	fournisseur: string | null
	desactive: number
	tags: string[]
	cloche: boolean
}

export interface LotsResponse extends ListResponse {
	lots: LotRow[]
	counts: Record<LotView, number>
	page_length: number
}

export interface TracabiliteRow {
	sens: string
	ordre: string
	statut: string | null
	produit: string | null
	lot_pf: string | null
	lot_mp: string | null
	article: string | null
	quantite: number
	quantite_pf: number
	date: string | null
}

export interface LotDetail extends LotRow {
	description: string | null
	can_edit: boolean
	can_delete: boolean
	/** Stock du lot par dépôt, périmé compris. */
	depots: { depot: string; qty: number }[]
	/** Fiche seulement. null : la personne ne lit pas ces documents. */
	mouvements?: LedgerRow[] | null
	tracabilite?: TracabiliteRow[] | null
	comments?: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface LotOptions {
	filter_fields?: FilterField[]
	expire_sous: number
}

export interface LotValues {
	peremption?: string
	fabrication?: string
	lot_fournisseur?: string
	desactive?: number
}

/** État de péremption d'un lot encore en stock : périmé, à surveiller (sous `jours`), ou rien. */
export function etatPeremption(lot: Pick<LotRow, 'peremption' | 'quantite'>, jours = 30, today = dayFromToday(0)): 'perime' | 'proche' | null {
	if (!lot.peremption || lot.quantite <= 0) return null
	if (lot.peremption < today) return 'perime'
	return lot.peremption <= dayFromToday(jours, new Date(`${today}T00:00:00`)) ? 'proche' : null
}

export const LOT_COLUMNS: Column<LotRow>[] = [
	{ key: 'name', label: 'Lot', width: 200, minWidth: 120, sortable: true, text: (row) => row.name },
	{ key: 'designation', label: 'Article', width: 200, minWidth: 120, grow: 1.5, sortable: true, text: (row) => row.designation },
	{ key: 'quantite', label: 'En stock', width: 110, minWidth: 80, sortable: true, end: true, text: (row) => row.quantite },
	{ key: 'peremption', label: 'Péremption', width: 110, minWidth: 88, sortable: true, text: (row) => formatDay(row.peremption) },
	{ key: 'origine', label: 'Origine', width: 110, minWidth: 80, sortable: true, text: (row) => row.origine || '' },
	{ key: 'lot_fournisseur', label: 'Lot fournisseur', width: 130, minWidth: 88, sortable: true, text: (row) => row.lot_fournisseur || '' },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'fabrication', label: 'Fabrication', width: 110, minWidth: 88, sortable: true, optional: true, text: (row) => formatDay(row.fabrication) },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_LOT_COLUMNS = LOT_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function lotSortText(sort: Sort | null) {
	const column = sort && LOT_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récents'
}
