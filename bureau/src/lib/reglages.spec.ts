import { describe, expect, it } from 'vitest'
import { moveLine } from './reglages'

describe('réglages de la production', () => {
	it("déplace un contrôle d'un cran, sans sortir de la liste", () => {
		expect(moveLine(['a', 'b', 'c'], 1, -1)).toEqual(['b', 'a', 'c'])
		expect(moveLine(['a', 'b', 'c'], 1, 1)).toEqual(['a', 'c', 'b'])
		expect(moveLine(['a', 'b'], 0, -1)).toEqual(['a', 'b'])
	})
})
