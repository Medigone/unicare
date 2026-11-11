/** Règles de la page Articles : types, vues, colonnes, et validation de la fenêtre de l'article. */
import type { CommentPart } from '@shared/activity'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'

export type ArticleView = 'all' | 'fut' | 'conditionnement' | 'produit_fini' | 'autre' | 'desactive'

export const ARTICLE_VIEWS: { key: ArticleView; label: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'fut', label: 'Fûts' },
	{ key: 'conditionnement', label: 'Conditionnements' },
	{ key: 'produit_fini', label: 'Produits finis' },
	{ key: 'autre', label: 'Autres' },
	{ key: 'desactive', label: 'Désactivés' },
]

/** Le stock vient des quantités par dépôt (Bin) : colonne réservée à qui les lit. */
export const STOCK_DOCTYPE = 'Bin'

export interface ArticleRow {
	name: string
	modified: string
	creation: string
	designation: string
	type: string | null
	groupe: string | null
	uom: string | null
	lots: number
	disabled: number
	/** null : article hors stock, ou personne qui ne lit pas le stock. */
	stock: number | null
	tags: string[]
	cloche: boolean
}

export interface ArticlesResponse extends ListResponse {
	articles: ArticleRow[]
	counts: Record<ArticleView, number>
	page_length: number
}

export interface ArticleBin {
	warehouse: string
	actual_qty: number
	reserved_qty: number
	ordered_qty: number
	projected_qty: number
}

export interface ArticleLot {
	name: string
	batch_qty: number
	manufacturing_date: string | null
	expiry_date: string | null
	disabled: number
	lot_fournisseur: string | null
	origine: string | null
	ordre: string | null
}

export interface ArticleRecette {
	name: string
	produit_fini?: string
	nom_produit: string | null
	actif: number
	quantite_base?: number
	qty?: number
	uom: string | null
	rendement_theorique?: number
}

export interface ArticleOrdre {
	name: string
	produit_fini: string
	nom_produit: string | null
	date_prevue: string | null
	workflow_state: string | null
	docstatus: number
	qty_prevue: number | null
	qty_reelle_pf: number | null
	uom: string | null
}

export interface ArticleMouvement {
	name: string
	date: string
	tiers: string | null
	status: string | null
	qty: number
	uom: string | null
	montant: number
}
export type MouvementKey = 'commandes_achat' | 'receptions' | 'commandes_vente' | 'factures'

export interface ArticleDetail {
	name: string
	modified: string
	tags: string[]
	designation: string
	type: string | null
	groupe: string | null
	uom: string | null
	is_stock_item: number
	has_batch_no: number
	is_purchase_item: number
	is_sales_item: number
	disabled: number
	description: string | null
	shelf_life_in_days: number | null
	barcodes: string[]
	image: string | null
	depuis: string
	/** null : article hors stock, ou personne qui ne lit pas le stock. */
	stock: number | null
	can_edit: boolean
	/** Droit de supprimer la fiche ; Frappe refuse encore si une pièce y est liée. */
	can_delete: boolean
	/** Fiche seulement. Chaque bloc vaut `null` quand la personne ne lit pas le document, ou qu'il ne s'applique pas. */
	bins?: ArticleBin[] | null
	lots?: ArticleLot[] | null
	recettes?: { produit: ArticleRecette[]; ingredient: ArticleRecette[] } | null
	ordres?: { produit: ArticleOrdre[]; matiere: ArticleOrdre[] } | null
	mouvements?: Record<MouvementKey, ArticleMouvement[] | null>
	comments?: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface ArticleOptions {
	filter_fields?: FilterField[]
	types: string[]
	types_avec_lot: string[]
	groupes: string[]
	uoms: string[]
}

export interface ArticleChoice {
	name: string
	label: string
	type: string | null
	disabled: number
}

/** Quantité : jusqu'à trois décimales, espace insécable pour les milliers, virgule décimale. */
export function formatQty(value?: number | null) {
	const rounded = Math.round((value ?? 0) * 1000) / 1000
	const [whole, decimals] = Math.abs(rounded).toString().split('.')
	const text = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + (decimals ? `,${decimals}` : '')
	return rounded < 0 ? `−${text}` : text
}

export const ARTICLE_COLUMNS: Column<ArticleRow>[] = [
	{ key: 'designation', label: 'Article', width: 240, minWidth: 140, grow: 2, sortable: true, text: (row) => row.designation },
	{ key: 'name', label: 'Code', width: 110, minWidth: 88, sortable: true, text: (row) => row.name },
	{ key: 'type', label: 'Type', width: 128, minWidth: 88, sortable: true, text: (row) => row.type || '' },
	{ key: 'groupe', label: 'Groupe', width: 140, minWidth: 80, grow: 0.8, sortable: true, text: (row) => row.groupe || '' },
	{ key: 'stock', label: 'Stock', width: 100, minWidth: 72, sortable: true, end: true, text: (row) => (row.stock === null ? '' : row.stock) },
	{ key: 'uom', label: 'Unité', width: 80, minWidth: 64, sortable: true, text: (row) => row.uom || '' },
	{ key: 'tags', label: 'Tags', width: 150, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'lots', label: 'Lots', width: 70, minWidth: 56, sortable: false, optional: true, text: (row) => (row.lots ? 'Oui' : 'Non') },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_ARTICLE_COLUMNS = ARTICLE_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function allowedArticleColumns(canReadStock: boolean) {
	return canReadStock ? ARTICLE_COLUMNS : ARTICLE_COLUMNS.filter((column) => column.key !== 'stock')
}

export function articleSortText(sort: Sort | null) {
	const column = sort && ARTICLE_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : désignation'
}

/** Champs de la fenêtre. Le type et le code-barres ne se saisissent qu'à la création. */
export const ARTICLE_FIELDS = ['type', 'designation', 'groupe', 'uom', 'is_stock_item', 'has_batch_no', 'description', 'shelf_life_in_days', 'barcode', 'is_purchase_item', 'is_sales_item', 'disabled'] as const
export type ArticleField = (typeof ARTICLE_FIELDS)[number]
export type ArticleValues = Partial<Record<ArticleField, string>>
export const ARTICLE_EDIT_FIELDS: readonly ArticleField[] = ['designation', 'groupe', 'uom', 'is_stock_item', 'has_batch_no', 'description', 'shelf_life_in_days', 'is_purchase_item', 'is_sales_item', 'disabled']

const REQUIRED: { field: ArticleField; message: string; create?: boolean }[] = [
	{ field: 'type', message: "Choisissez le type d'article.", create: true },
	{ field: 'designation', message: 'Saisissez la désignation.' },
	{ field: 'groupe', message: "Choisissez le groupe d'articles." },
	{ field: 'uom', message: "Choisissez l'unité de stock." },
]

/** Mêmes refus que le serveur, dits avant l'envoi. */
export function validateArticle(values: ArticleValues, editing = false) {
	const errors: Partial<Record<ArticleField, string>> = {}
	const value = (field: ArticleField) => values[field]?.trim() ?? ''
	for (const { field, message, create } of REQUIRED) if (!(editing && create) && !value(field)) errors[field] = message
	const shelf = value('shelf_life_in_days')
	if (shelf && !/^\d+$/.test(shelf)) errors.shelf_life_in_days = 'Saisissez un nombre de jours entier.'
	if (value('has_batch_no') === '1' && value('is_stock_item') !== '1') errors.has_batch_no = 'Un article géré par lots doit être un article de stock.'
	return errors
}

/** Une case cochée vaut « 1 », comme sur le Desk. */
const check = (value: number | null | undefined) => (value ? '1' : '0')

export function articleFormValues(article: ArticleDetail): ArticleValues {
	return {
		type: article.type ?? '',
		designation: article.designation,
		groupe: article.groupe ?? '',
		uom: article.uom ?? '',
		is_stock_item: check(article.is_stock_item),
		has_batch_no: check(article.has_batch_no),
		description: article.description ?? '',
		shelf_life_in_days: article.shelf_life_in_days ? String(article.shelf_life_in_days) : '',
		barcode: article.barcodes[0] ?? '',
		is_purchase_item: check(article.is_purchase_item),
		is_sales_item: check(article.is_sales_item),
		disabled: check(article.disabled),
	}
}

/** Seuls les champs changés partent au serveur. */
export function changedArticleValues(initial: ArticleValues, current: ArticleValues) {
	const changes: ArticleValues = {}
	for (const field of ARTICLE_EDIT_FIELDS) {
		if ((current[field] ?? '').trim() !== (initial[field] ?? '').trim()) changes[field] = (current[field] ?? '').trim()
	}
	return changes
}
