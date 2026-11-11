import { describe, expect, it } from 'vitest'
import { changedCounts, INVENTAIRE_VIEWS, resumeSaisie, type InventaireLine } from './inventaires'

const line = (name: string, theorique: number, compte: number, taux = 10): InventaireLine => ({ name, article: name, designation: name, groupe: null, depot: 'M', lot: null, unite: 'U', theorique, compte, ecart: compte - theorique, taux, ecart_valeur: (compte - theorique) * taux })

describe('inventaires', () => {
	it("n'envoie que les comptages modifiés", () => {
		const lines = [line('A', 40, 40), line('B', 5, 5)]
		expect(changedCounts(lines, { A: '40', B: '5' })).toEqual([])
		expect(changedCounts(lines, { A: '37', B: '5' })).toEqual([{ name: 'A', quantite: 37 }])
		expect(changedCounts(lines, { A: '37,5' })).toEqual([{ name: 'A', quantite: 37.5 }])
	})

	it('résume les écarts de la saisie en cours', () => {
		const lines = [line('A', 40, 40), line('B', 5, 5, 100), line('C', 0, 0)]
		expect(resumeSaisie(lines, { A: '37', B: '7', C: 'illisible' })).toEqual({ lignes: 3, ecarts: 2, plus: 2, moins: -3, valeur: 170 })
		expect(resumeSaisie(lines, {}).ecarts).toBe(0)
	})

	it('a les mêmes vues que le serveur', () => {
		expect(INVENTAIRE_VIEWS.map((view) => view.key)).toEqual(['all', 'brouillons', 'valides', 'annules'])
	})
})
