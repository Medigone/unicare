import { describe, expect, it } from 'vitest'
import { allowedDepotColumns, allowedDepotViews, DEFAULT_DEPOT_COLUMNS } from './depots'
import { pieceLabel, signedQty } from './stock'

describe('stock', () => {
	it('signe les quantités du grand livre', () => {
		expect(signedQty(10)).toBe('+10')
		expect(signedQty(-2.5)).toBe('−2,5')
		expect(signedQty(0)).toBe('0')
	})

	it('nomme les pièces en français', () => {
		expect(pieceLabel('Stock Reconciliation')).toBe('Inventaire')
		expect(pieceLabel('Purchase Receipt')).toBe('Réception')
	})

	it('réserve la valeur des dépôts à qui lit le stock', () => {
		expect(DEFAULT_DEPOT_COLUMNS).toEqual(['depot', 'parent', 'type', 'articles', 'valeur', 'tags'])
		window.droits = { Bin: { read: false, create: false } }
		expect(allowedDepotColumns().map((column) => column.key)).not.toContain('valeur')
		expect(allowedDepotViews().map((view) => view.key)).not.toContain('avec_stock')
		delete window.droits
	})
})

describe('état du stock', async () => {
	const { ETAT_STOCK_VIEWS, niveauStock } = await import('./etatStock')
	it('teinte chaque ligne selon son niveau', () => {
		expect(niveauStock({ quantite: -1, seuil: null })).toBe('negatif')
		expect(niveauStock({ quantite: 0, seuil: 5 })).toBe('rupture')
		expect(niveauStock({ quantite: 3, seuil: 5 })).toBe('bas')
		expect(niveauStock({ quantite: 8, seuil: 5 })).toBeNull()
	})
	it('a les mêmes vues que le serveur', () => {
		expect(ETAT_STOCK_VIEWS.map((view) => view.key)).toEqual(['all', 'en_stock', 'rupture', 'sous_seuil', 'negatif', 'reserve'])
	})
})
