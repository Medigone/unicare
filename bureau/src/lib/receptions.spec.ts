import { describe, expect, it } from 'vitest'
import { changedReceptionPrep, DEFAULT_RECEPTION_COLUMNS, fillDepot, type ReceptionPrep } from './receptions'

const entry = (values: Partial<ReceptionPrep> = {}): ReceptionPrep => ({ name: 'L1', quantite: '10', depot: '', lot: '', peremption: '', ...values })

describe('réceptions', () => {
	it('affiche le BL du fournisseur et la commande par défaut', () => {
		expect(DEFAULT_RECEPTION_COLUMNS).toContain('bl_fournisseur')
		expect(DEFAULT_RECEPTION_COLUMNS).toContain('commandes')
	})

	it("n'envoie que les lignes changées, le lot avec sa péremption", () => {
		const initial = [entry(), entry({ name: 'L2' })]
		expect(changedReceptionPrep(initial, initial)).toEqual([])
		expect(changedReceptionPrep(initial, [entry({ quantite: '6,5' }), entry({ name: 'L2', peremption: '2027-05-01' })])).toEqual([
			{ name: 'L1', quantite: 6.5 },
			{ name: 'L2', lot: '', peremption: '2027-05-01' },
		])
	})

	it('pose le dépôt choisi sans toucher un choix déjà fait', () => {
		const result = fillDepot([entry(), entry({ name: 'L2', depot: 'Production - U' })], 'Magasins - U')
		expect(result.map((item) => item.depot)).toEqual(['Magasins - U', 'Production - U'])
	})
})
