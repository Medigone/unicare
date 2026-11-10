import { describe, expect, it } from 'vitest'
import { allowedArticleColumns, articleFormValues, articleSortText, changedArticleValues, DEFAULT_ARTICLE_COLUMNS, formatQty, validateArticle, type ArticleDetail } from './articles'

const base = { type: 'Conditionnement', designation: 'Flacon 250 ml', groupe: 'Produits', uom: 'Unité' }

describe('articles', () => {
	it('écrit les quantités à la française', () => {
		expect(formatQty(1240.5)).toBe('1 240,5')
		expect(formatQty(0.12345)).toBe('0,123')
		expect(formatQty(-3)).toBe('−3')
		expect(formatQty(null)).toBe('0')
	})

	it('affiche désignation, code, type, groupe, stock, unité et tags par défaut', () => {
		expect(DEFAULT_ARTICLE_COLUMNS).toEqual(['designation', 'name', 'type', 'groupe', 'stock', 'uom', 'tags'])
		expect(allowedArticleColumns(false).map((column) => column.key)).not.toContain('stock')
		expect(articleSortText(null)).toBe('Tri : désignation')
	})

	it('demande type, désignation, groupe et unité ; le type seulement à la création', () => {
		expect(Object.keys(validateArticle({}))).toEqual(['type', 'designation', 'groupe', 'uom'])
		expect(Object.keys(validateArticle({ ...base, type: '' }, true))).toEqual([])
		expect(validateArticle({ ...base, shelf_life_in_days: '730' })).toEqual({})
	})

	it('refuse une durée illisible et des lots hors stock', () => {
		expect(Object.keys(validateArticle({ ...base, shelf_life_in_days: '2 ans' }))).toEqual(['shelf_life_in_days'])
		expect(Object.keys(validateArticle({ ...base, has_batch_no: '1', is_stock_item: '0' }))).toEqual(['has_batch_no'])
	})

	it("n'envoie que les champs changés, jamais le type ni le code-barres", () => {
		const article = { ...base, is_stock_item: 1, has_batch_no: 0, is_purchase_item: 1, is_sales_item: 0, disabled: 0, description: null, shelf_life_in_days: null, barcodes: ['613'] } as unknown as ArticleDetail
		const initial = articleFormValues(article)
		expect(initial.barcode).toBe('613')
		expect(changedArticleValues(initial, { ...initial })).toEqual({})
		expect(changedArticleValues(initial, { ...initial, type: 'Fût', barcode: '1', disabled: '1', designation: ' Flacon 500 ml ' })).toEqual({ designation: 'Flacon 500 ml', disabled: '1' })
	})
})
