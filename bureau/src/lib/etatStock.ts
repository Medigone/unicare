/** Règles de la page État du stock : une ligne par article et par dépôt (Bin), vues et colonnes. */
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { LedgerRow } from './stock'
import type { LotChoice } from './livraisons'
import type { ListResponse } from './useServerList'

export type EtatStockView = 'all' | 'en_stock' | 'rupture' | 'sous_seuil' | 'negatif' | 'reserve'

export const ETAT_STOCK_VIEWS: { key: EtatStockView; label: string }[] = [
	{ key: 'all', label: 'Tout' },
	{ key: 'en_stock', label: 'En stock' },
	{ key: 'rupture', label: 'En rupture' },
	{ key: 'sous_seuil', label: 'Sous le seuil' },
	{ key: 'negatif', label: 'Stock négatif' },
	{ key: 'reserve', label: 'Avec réservations' },
]

export interface LigneStock {
	name: string
	modified: string
	creation: string
	article: string
	designation: string
	groupe: string | null
	type: string | null
	avec_lot: number
	depot: string
	quantite: number
	reserve: number
	commande: number
	projete: number
	valeur: number
	taux: number
	unite: string | null
	/** Seuil de réapprovisionnement de l'article pour ce dépôt ; null : aucun. */
	seuil: number | null
	tags: string[]
	cloche: boolean
}

export interface EtatStockResponse extends ListResponse {
	lignes: LigneStock[]
	counts: Record<EtatStockView, number>
	/** Valeur du stock de la vue affichée. */
	valeur: number
	page_length: number
}

export interface LigneStockDetail extends LigneStock {
	/** Fiche seulement. null : la personne ne lit pas le grand livre ; l'article n'est pas suivi par lots. */
	mouvements?: LedgerRow[] | null
	lots?: LotChoice[] | null
}

export interface EtatStockOptions {
	filter_fields?: FilterField[]
	depots: string[]
}

export const ETAT_STOCK_COLUMNS: Column<LigneStock>[] = [
	{ key: 'designation', label: 'Article', width: 220, minWidth: 140, grow: 2, sortable: true, text: (row) => row.designation },
	{ key: 'depot', label: 'Dépôt', width: 170, minWidth: 96, grow: 1, sortable: true, text: (row) => row.depot },
	{ key: 'quantite', label: 'En stock', width: 110, minWidth: 80, sortable: true, end: true, text: (row) => row.quantite },
	{ key: 'reserve', label: 'Réservé', width: 96, minWidth: 72, sortable: true, end: true, text: (row) => row.reserve },
	{ key: 'projete', label: 'Projeté', width: 96, minWidth: 72, sortable: true, end: true, text: (row) => row.projete },
	{ key: 'seuil', label: 'Seuil', width: 88, minWidth: 64, sortable: true, end: true, text: (row) => row.seuil ?? '' },
	{ key: 'valeur', label: 'Valeur (DA)', width: 120, minWidth: 88, sortable: true, end: true, text: (row) => Math.round(row.valeur) },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'article', label: 'Code article', width: 120, minWidth: 80, sortable: true, optional: true, text: (row) => row.article },
	{ key: 'groupe', label: 'Groupe', width: 150, minWidth: 80, sortable: true, optional: true, text: (row) => row.groupe || '' },
	{ key: 'commande', label: 'Commandé', width: 100, minWidth: 72, sortable: true, end: true, optional: true, text: (row) => row.commande },
	{ key: 'modified', label: 'Dernier mouvement', width: 130, minWidth: 96, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_ETAT_STOCK_COLUMNS = ETAT_STOCK_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function etatStockSortText(sort: Sort | null) {
	const column = sort && ETAT_STOCK_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : article'
}

/** Niveau d'une ligne, pour sa teinte : négatif, en rupture, sous le seuil, ou normal. */
export function niveauStock(row: Pick<LigneStock, 'quantite' | 'seuil'>): 'negatif' | 'rupture' | 'bas' | null {
	if (row.quantite < 0) return 'negatif'
	if (row.quantite === 0) return 'rupture'
	if (row.seuil !== null && row.quantite < row.seuil) return 'bas'
	return null
}
