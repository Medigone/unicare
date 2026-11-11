import { describe, expect, it } from 'vitest'
import { quandText, resumeJournee } from './accueil'
import { CREER_ITEMS, creerItems, itemForLetter } from './creer'

describe('accueil', () => {
	it('résume la journée en une phrase', () => {
		expect(resumeJournee({ retard: 3, aujourdhui: 4, a_valider: 3 })).toBe("3 choses en retard, 4 pour aujourd'hui et 3 brouillons à valider.")
		expect(resumeJournee({ retard: 1, aujourdhui: 0, a_valider: 0 })).toBe('1 chose en retard.')
		expect(resumeJournee({ retard: 0, aujourdhui: 0, a_valider: 0 })).toBe('Rien en attente : tout est à jour.')
	})

	it('écrit les moments récents en court', () => {
		const now = new Date(2026, 10, 11, 15, 0)
		expect(quandText('2026-11-11 10:42:00', now)).toBe('10:42')
		expect(quandText('2026-11-10 09:00:00', now)).toBe('hier')
		expect(quandText('2026-10-01 09:00:00', now)).toBe('1 oct.')
	})

	it('trouve la création d’un raccourci, selon les droits', () => {
		expect(itemForLetter('D')?.key).toBe('devis')
		expect(itemForLetter('z')).toBeUndefined()
		expect(itemForLetter('e')?.key).toBe('recette')
		// Chaque entrée a sa lettre, et aucune lettre ne sert deux fois.
		const lettres = CREER_ITEMS.map((item) => item.lettre)
		expect(lettres.every(Boolean)).toBe(true)
		expect(new Set(lettres).size).toBe(lettres.length)
		window.droits = { Quotation: { read: true, create: false } }
		expect(creerItems().some((item) => item.key === 'devis')).toBe(false)
		expect(itemForLetter('d', creerItems())).toBeUndefined()
		delete window.droits
	})
})
