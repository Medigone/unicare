import { describe, expect, it } from 'vitest'
import { formatDate, formatTaux, libelleCompte } from './compta'

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
})
