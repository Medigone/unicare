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
