import { describe, expect, it } from 'vitest'
import { formatQty } from './articles'
import { seuilChange, seuilDraft, seuilErreur, arbreDepots, etatSeuil, jaugeSeuil } from './reglagesStock'

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

	it("dit ce qui manque pour revenir au seuil", () => {
		expect(etatSeuil({ stock: 120, seuil: 500 })).toEqual({ label: 'Manque 380', tone: 'red' })
		expect(etatSeuil({ stock: 3.5, seuil: 5 })).toEqual({ label: 'Manque 1,5', tone: 'red' })
		expect(etatSeuil({ stock: 600, seuil: 500 })).toEqual({ label: 'OK', tone: 'green' })
		expect(etatSeuil({ stock: 10, seuil: null })).toEqual({ label: 'Sans seuil', tone: null })
	})

	it('place le stock et le seuil sur la jauge', () => {
		expect(jaugeSeuil(120, 500)).toEqual({ stock: 21, seuil: 87 })
		expect(jaugeSeuil(0, 10)).toEqual({ stock: 0, seuil: 87 })
		expect(jaugeSeuil(2300, 1000).seuil).toBeLessThan(jaugeSeuil(2300, 1000).stock)
	})

	it("range les dépôts sous leurs dossiers", () => {
		const n = (name: string, parent: string | null, dossier = false) => ({ name, label: name, parent, dossier, modified: '' })
		const lignes = arbreDepots([n('Magasin', null), n('Usine', null, true), n('MP', 'Usine'), n('PF', 'Usine'), n('Vide', null, true), n('Orphelin', 'Groupe désactivé')])
		expect(lignes.map((l) => [l.name, l.niveau])).toEqual([['Usine', 1], ['MP', 2], ['PF', 2], ['Vide', 1], ['Magasin', 1], ['Orphelin', 1]])
		expect(lignes.find((l) => l.name === 'Usine')?.enfants).toBe(2)
		expect(lignes.find((l) => l.name === 'Vide')?.enfants).toBe(0)
	})
})
