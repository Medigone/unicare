import { describe, expect, it } from 'vitest'
import { COMMANDE_COLUMNS, commandeSortText, DEFAULT_COMMANDE_COLUMNS, formatPercent, STATUS_ACTIONS, type CommandeRow } from './commandes'
import { validateDevis } from './devis'

describe('commandes', () => {
	it('écrit les pourcentages à la française', () => {
		expect(formatPercent(40)).toBe('40 %')
		expect(formatPercent(33.333)).toBe('33,3 %')
		expect(formatPercent(null)).toBe('0 %')
	})

	it('affiche livraison, livré et facturé par défaut, avec le statut en français à l\'export', () => {
		expect(DEFAULT_COMMANDE_COLUMNS).toEqual(['name', 'client_label', 'status', 'date', 'livraison', 'livre', 'facture', 'total_ttc', 'tags'])
		const status = COMMANDE_COLUMNS.find((column) => column.key === 'status')!
		expect(status.text({ status: 'To Deliver and Bill' } as CommandeRow)).toBe('À livrer et facturer')
		expect(commandeSortText(null)).toBe('Tri : plus récentes')
	})

	it('nomme la date de livraison dans les refus', () => {
		const errors = validateDevis({ client: 'CLI-1', valable: '2026-11-01', lignes: [] }, '2026-11-10', 'la date de livraison')
		expect(errors.valable).toBe('La date de livraison ne peut pas être passée.')
		expect(STATUS_ACTIONS.map((item) => item.key)).toEqual(['attente', 'reprendre', 'cloturer', 'rouvrir'])
	})
})
