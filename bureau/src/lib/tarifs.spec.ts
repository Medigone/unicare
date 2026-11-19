import { describe, expect, it } from 'vitest'
import { calculerPrix, formatDate, formatEcart, formatPeriode, formatPrix, joursAvant, parsePrix, prixChange, regleTexte, validite, veille } from './tarifs'

describe('tarifs', () => {
	it('affiche un prix lisible', () => {
		expect(formatPrix(1250.5)).toBe('1 250,50')
		expect(formatPrix(1000)).toBe('1 000')
		expect(formatPrix(null)).toBe('')
	})

	it('lit la saisie du prix', () => {
		expect(parsePrix('1 250,50')).toEqual({ value: 1250.5 })
		expect(parsePrix('  ')).toEqual({ value: null })
		expect(parsePrix('0')).toHaveProperty('error')
		expect(parsePrix('-3')).toHaveProperty('error')
		expect(parsePrix('abc')).toHaveProperty('error')
	})

	it("ne réenregistre pas un prix qui n'a pas changé", () => {
		expect(prixChange('1 250,5', 1250.5)).toBe(false)
		expect(prixChange('', null)).toBe(false)
		expect(prixChange('', 10)).toBe(true)
		expect(prixChange('12', 10)).toBe(true)
	})

	it('affiche dates et périodes', () => {
		expect(formatDate('2026-11-01')).toBe('1 nov. 2026')
		expect(formatDate('2026-11-01', true)).toBe('1 nov.')
		expect(formatPeriode('2026-10-01', null)).toBe('1 oct. 2026 → sans fin')
		expect(veille('2027-01-01')).toBe('2026-12-31')
		expect(joursAvant('2026-12-31', '2026-11-19')).toBe(42)
	})

	it('décrit la validité du prix en vigueur', () => {
		const base = { prix: 10, debut: null, fin: null, nb_lignes: 1, dernier_expire: null }
		expect(validite({ ...base, debut: '2026-11-03' })).toBe('depuis le 3 nov. 2026')
		expect(validite({ ...base, debut: '2026-10-01', fin: '2026-12-31' })).toBe('1 oct. → 31 déc. 2026')
		expect(validite({ ...base, prix: null, nb_lignes: 0 })).toBe('jamais chiffré')
		expect(validite({ ...base, prix: null })).toBe('aucun prix en vigueur')
	})

	it("affiche l'écart avec le dernier prix payé", () => {
		expect(formatEcart(0.082)).toBe('+8,2 %')
		expect(formatEcart(-0.03)).toBe('−3 %')
		expect(formatEcart(0)).toBe('=')
		expect(formatEcart(null)).toBe('—')
	})

	it('calcule un tarif comme le serveur', () => {
		expect(calculerPrix(1450, 'remise', 10, 1)).toBe(1305)
		expect(calculerPrix(95, 'remise', 10, 1)).toBe(86)
		expect(calculerPrix(95, 'remise', 10, 0)).toBe(85.5)
		expect(calculerPrix(640, 'majoration', 15, 10)).toBe(740)
		expect(calculerPrix(180, 'aucun', 0, 0)).toBe(180)
	})

	it('décrit la règle', () => {
		expect(regleTexte({ ajustement: 'remise', pourcentage: 10, arrondi: 1 })).toBe('remise 10 % · arrondi au dinar')
		expect(regleTexte({ ajustement: 'majoration', pourcentage: 2.5, arrondi: 0 })).toBe('majoration 2,5 %')
		expect(regleTexte({ ajustement: 'aucun', pourcentage: 0, arrondi: 10 })).toBe('mêmes prix · arrondi à la dizaine')
	})
})
