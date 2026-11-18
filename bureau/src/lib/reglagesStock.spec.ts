import { describe, expect, it } from 'vitest'
import { formatQty } from './articles'
import { seuilChange, seuilDraft, seuilErreur } from './reglagesStock'

describe('seuils', () => {
	it('prépare la saisie depuis la ligne enregistrée', () => {
		expect(seuilDraft({ seuil: 1250.5, quantite: 3000 })).toEqual({ seuil: formatQty(1250.5), quantite: formatQty(3000) })
		expect(seuilDraft({ seuil: null, quantite: null })).toEqual({ seuil: '', quantite: '' })
	})

	it('refuse une saisie illisible ou négative', () => {
		expect(seuilErreur({ seuil: '12,5', quantite: '' })).toBeNull()
		expect(seuilErreur({ seuil: 'abc', quantite: '' })).toBe('Le seuil est illisible.')
		expect(seuilErreur({ seuil: '5', quantite: '-2' })).toBe('La quantité à commander ne peut pas être négative.')
	})

	it("ne réenregistre que ce qui a changé", () => {
		const ligne = { seuil: 10, quantite: 10 }
		expect(seuilChange({ seuil: '10', quantite: '10' }, ligne)).toBe(false)
		expect(seuilChange({ seuil: '10', quantite: '' }, ligne)).toBe(false)
		expect(seuilChange({ seuil: '12', quantite: '10' }, ligne)).toBe(true)
		expect(seuilChange({ seuil: '10', quantite: '40' }, ligne)).toBe(true)
		expect(seuilChange({ seuil: '', quantite: '' }, ligne)).toBe(true)
		expect(seuilChange({ seuil: '', quantite: '' }, { seuil: null, quantite: null })).toBe(false)
	})
})
