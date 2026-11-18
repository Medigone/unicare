import { describe, expect, it } from 'vitest'
import { formatPrix, parsePrix, prixChange } from './tarifs'

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
})
