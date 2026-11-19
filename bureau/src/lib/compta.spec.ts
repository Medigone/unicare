import { describe, expect, it } from 'vitest'
import { formatDate, formatTaux, libelleCompte, pireEtat, SECTIONS } from './compta'

describe('compta', () => {
	it('retire le suffixe de la société du nom du compte', () => {
		expect(libelleCompte('5121 - Banque - compte principal - U')).toBe('5121 - Banque - compte principal')
		expect(libelleCompte('411 - Clients - UD')).toBe('411 - Clients')
		expect(libelleCompte(null)).toBe('')
	})

	it('affiche les dates et les taux à la française', () => {
		expect(formatDate('2027-01-01')).toBe('01/01/2027')
		expect(formatTaux(13.5)).toBe('13,5 %')
		expect(formatTaux(19)).toBe('19 %')
	})

	it("donne à une section l'état de son pire point", () => {
		expect(pireEtat(['ok', 'attention', 'ok'])).toBe('attention')
		expect(pireEtat(['attention', 'manque'])).toBe('manque')
		expect(pireEtat([])).toBe('ok')
	})

	it('couvre chaque point du bilan par une section', () => {
		const points = SECTIONS.flatMap((s) => s.points)
		for (const code of ['exercice', 'plan', 'comptes', 'tva_vente', 'tva_achat', 'modes', 'timbre']) expect(points).toContain(code)
	})
})
