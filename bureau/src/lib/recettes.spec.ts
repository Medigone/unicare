import { describe, expect, it } from 'vitest'
import { besoinsPour, recetteErrors } from './recettes'

describe('recettes', () => {
	it('calcule les besoins pour une quantité', () => {
		const recette = { quantite_base: 1, ingredients: [{ designation: 'Vrac', unite: 'Kg', quantite: 0.1 }, { designation: 'Bouteille', unite: 'U', quantite: 1 }] } as never
		expect(besoinsPour(recette, 1000)).toEqual([
			{ designation: 'Vrac', unite: 'Kg', quantite: 100 },
			{ designation: 'Bouteille', unite: 'U', quantite: 1000 },
		])
		expect(besoinsPour(recette, 0)[0].quantite).toBe(0)
	})

	it('dit ce qui ne va pas dans la saisie', () => {
		const base = { produit: 'PF-1', quantite_base: 1, rendement: 100 }
		expect(recetteErrors({ ...base, ingredients: [{ article: 'CO-1', quantite: 1, type: 'Conditionnement' }] })).toEqual(['Il faut au moins une matière de type Fût (le vrac).'])
		expect(recetteErrors({ ...base, ingredients: [{ article: 'FU-1', quantite: 0.1, type: 'Fût' }, { article: 'FU-1', quantite: 1, type: 'Fût' }] })).toEqual(['Une matière figure deux fois : regroupez les quantités.'])
		expect(recetteErrors({ ...base, produit: '', rendement: 120, ingredients: [] })).toHaveLength(3)
		expect(recetteErrors({ ...base, ingredients: [{ article: 'FU-1', quantite: 0.1, type: 'Fût' }] })).toEqual([])
	})
})
