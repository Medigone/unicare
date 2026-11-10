import { describe, expect, it } from 'vitest'
import { changedPrep, DEFAULT_LIVRAISON_COLUMNS, lotsFor, suggestLots, type LivraisonLine, type PrepLine } from './livraisons'

const line = (values: Partial<LivraisonLine> = {}): LivraisonLine => ({
	name: 'L1',
	article: 'PF-000001',
	designation: 'Lotion',
	quantite: 5,
	unite: 'Unité',
	depot: 'Magasins - U',
	lot: null,
	avec_lot: 1,
	stock: 1,
	prix: 100,
	montant: 500,
	commande: 'SO-1',
	depots: [{ depot: 'Produits finis - U', qty: 309 }],
	lots: { 'Produits finis - U': [{ lot: 'LOT-A', qty: 3, peremption: '2027-01-01' }, { lot: 'LOT-B', qty: 100, peremption: '2027-06-01' }] },
	...values,
})
const prep = (values: Partial<PrepLine> = {}): PrepLine => ({ name: 'L1', quantite: '5', depot: 'Magasins - U', lot: '', ...values })

describe('livraisons', () => {
	it('propose le dépôt qui a des lots, puis le premier lot qui couvre la quantité', () => {
		expect(suggestLots([line()], [prep()])).toEqual([prep({ depot: 'Produits finis - U', lot: 'LOT-B' })])
		expect(suggestLots([line()], [prep({ quantite: '2' })])[0].lot).toBe('LOT-A')
	})

	it('ne touche jamais un lot déjà choisi', () => {
		expect(suggestLots([line()], [prep({ depot: 'Produits finis - U', lot: 'LOT-A' })])[0].lot).toBe('LOT-A')
	})

	it('garde le lot choisi dans la liste même s’il n’est plus disponible', () => {
		expect(lotsFor(line(), 'Produits finis - U', 'LOT-Z').map((item) => item.lot)).toEqual(['LOT-Z', 'LOT-A', 'LOT-B'])
		expect(lotsFor(line(), 'Magasins - U')).toEqual([])
	})

	it("n'envoie que les lignes changées", () => {
		const initial = [prep()]
		expect(changedPrep(initial, [prep()])).toEqual([])
		expect(changedPrep(initial, [prep({ depot: 'Produits finis - U', lot: 'LOT-B', quantite: '4,5' })])).toEqual([{ name: 'L1', quantite: 4.5, depot: 'Produits finis - U', lot: 'LOT-B' }])
		expect(DEFAULT_LIVRAISON_COLUMNS).toEqual(['name', 'client_label', 'status', 'date', 'commandes', 'facture', 'total_ttc', 'tags'])
	})
})
