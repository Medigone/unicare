import { describe, expect, it } from 'vitest'
import { amount, compactAmount, ficheRoute, indicateurValue, lienRoute, niceScale } from './tableaux'

describe('tableaux de bord', () => {
	it("arrondit le haut de l'axe et le découpe en graduations rondes", () => {
		expect(niceScale(3_800_000)).toEqual({ top: 4_000_000, ticks: [0, 1_000_000, 2_000_000, 3_000_000, 4_000_000] })
		expect(niceScale(228_400).ticks).toEqual([0, 100_000, 200_000, 300_000])
		expect(niceScale(0)).toEqual({ top: 1, ticks: [0, 1] })
	})

	it('écrit les graduations en court et les montants en DA', () => {
		expect(compactAmount(2_500_000)).toBe('2,5 M')
		expect(compactAmount(300_000)).toBe('300 k')
		expect(compactAmount(40)).toBe('40')
		expect(amount(428400).replace(/\s/g, ' ')).toBe('428 400 DA')
		expect(amount(null)).toBe('—')
		expect(indicateurValue({ key: 'n', label: '', valeur: 7, format: 'nombre', details: [], lien: { page: 'Commandes' } })).toBe('7')
	})

	it('mène à la liste filtrée et à la fiche', () => {
		expect(lienRoute({ page: 'Factures', vue: 'en_retard' })).toEqual({ name: 'Factures', query: { vue: 'en_retard' } })
		expect(lienRoute({ page: 'Factures' })).toEqual({ name: 'Factures', query: {} })
		expect(ficheRoute('Lot', 'FS-0001')).toEqual({ name: 'Lot', params: { id: 'FS-0001' } })
	})
})
