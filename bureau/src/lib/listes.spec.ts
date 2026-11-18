import { describe, expect, it } from 'vitest'
import { filtrerValeurs, usagesLabel, type ListeValeur } from './listes'

const v = (name: string, actif = true): ListeValeur => ({ name, modified: '', usages: 0, actif })

describe('listes', () => {
	it('filtre sans accents ni casse, et les unités actives', () => {
		const valeurs = [v('Matières Premières'), v('Électrique'), v('Box', false)]
		expect(filtrerValeurs(valeurs, 'matieres').map((r) => r.name)).toEqual(['Matières Premières'])
		expect(filtrerValeurs(valeurs, 'ELEC').map((r) => r.name)).toEqual(['Électrique'])
		expect(filtrerValeurs(valeurs, '', 'actives')).toHaveLength(2)
		expect(filtrerValeurs(valeurs, '', 'toutes')).toHaveLength(3)
	})

	it('dit combien de fiches utilisent la valeur', () => {
		expect(usagesLabel(0)).toBe('Inutilisée')
		expect(usagesLabel(1)).toBe('1 fiche')
		expect(usagesLabel(4)).toBe('4 fiches')
	})
})
