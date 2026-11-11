import { describe, expect, it } from 'vitest'
import { clotureLignes, dureeText, echeanceText, parseQty, rendementCloture } from './ordres'

describe('ordres de conditionnement', () => {
	it('lit les nombres à la française', () => {
		expect(parseQty('1 250,5')).toBe(1250.5)
		expect(parseQty('')).toBeNaN()
	})

	it("écrit l'échéance et les durées en clair", () => {
		const today = new Date(2026, 10, 11)
		expect(echeanceText('2026-08-14', true, today)).toBe('14 août · en retard de 89 j')
		expect(echeanceText('2026-11-11', false, today)).toBe("11 nov. · aujourd'hui")
		expect(echeanceText('2026-11-12', false, today)).toBe('12 nov. · demain')
		expect(echeanceText(null, false, today)).toBe('—')
		expect(dureeText(35)).toBe('35 min')
		expect(dureeText(132)).toBe('2 h 12')
		expect(dureeText(3000)).toBe('2 j 2 h')
		expect(dureeText(0)).toBe('—')
	})

	it('contrôle la clôture : utilisé + rebut ne dépasse pas ce qui est arrivé à l’atelier', () => {
		const ordre = {
			matieres: [
				{ name: 'a', article: 'BOUT', lot: null, designation: 'Bouteille', prevu: 300, complement: 0, utilise: 300 },
				{ name: 'b', article: 'ETIQ', lot: null, designation: 'Etiquette', prevu: 300, complement: 20, utilise: 300 },
			],
			rebuts: [{ name: 'r', article: 'BOUT', lot: null, designation: 'Bouteille', quantite: 12, unite: 'U' }],
		} as never
		const lignes = clotureLignes(ordre, { a: '288', b: '292' })
		expect(lignes.map((line) => [line.ok, line.reste])).toEqual([
			[true, 0],
			[true, 28],
		])
		expect(clotureLignes(ordre, { a: '295' })[0].ok).toBe(false)
	})

	it('calcule le rendement et la tolérance', () => {
		const ordre = { qty_prevue: 300, rendement_vise: 100, tolerance: 10 }
		expect(rendementCloture(288, ordre)).toEqual({ rendement: 96, horsTolerance: false })
		expect(rendementCloture(250, ordre)).toEqual({ rendement: 83.3, horsTolerance: true })
	})
})
