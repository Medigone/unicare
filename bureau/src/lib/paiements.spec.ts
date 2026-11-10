import { describe, expect, it } from 'vitest'
import { capacity, DEFAULT_PAIEMENT_COLUMNS, proposeAllocation, validateAssistant, type PieceOuverte } from './paiements'

const piece = (name: string, reste: number, deja = 0): PieceOuverte => ({ doctype: 'Sales Invoice', name, date: '2026-10-01', echeance: '2026-10-31', total: reste, reste, avoir: 0, deja })
const values = { type: 'encaissement_client', tiers: 'CLI-1', montant: 1500, mode: 'Espèces', date: '2026-11-10', reference: '' }

describe('paiements', () => {
	it("répartit le montant dans l'ordre des pièces, sans dépasser leur reste dû", () => {
		expect(proposeAllocation(1500, [piece('F1', 1000), piece('F2', 2000)])).toEqual({ F1: 1000, F2: 500 })
		expect(proposeAllocation(5000, [piece('F1', 1000), piece('F2', 2000)])).toEqual({ F1: 1000, F2: 2000 })
		expect(proposeAllocation(0, [piece('F1', 1000)])).toEqual({ F1: 0 })
	})

	it('compte ce que le brouillon modifié affecte déjà', () => {
		expect(capacity(piece('F1', 600, 400))).toBe(1000)
		expect(proposeAllocation(900, [piece('F1', 600, 400)])).toEqual({ F1: 900 })
	})

	it('refuse une affectation au-delà du reste dû ou du montant', () => {
		const pieces = [piece('F1', 1000), piece('F2', 2000)]
		expect(validateAssistant(values, 'Cash', { F1: 1000, F2: 500 }, pieces, '2026-11-10')).toEqual({})
		expect(validateAssistant(values, 'Cash', { F1: 1200 }, pieces, '2026-11-10').piece).toEqual({ F1: 'Au-delà du reste dû.' })
		expect(validateAssistant(values, 'Cash', { F1: 1000, F2: 1000 }, pieces, '2026-11-10').affectations).toBe('Les montants affectés dépassent le montant du paiement.')
	})

	it('demande tiers, montant, mode, et la référence pour un mode bancaire', () => {
		expect(Object.keys(validateAssistant({ ...values, tiers: '', montant: 0, mode: '' }, undefined, {}, [], '2026-11-10'))).toEqual(['tiers', 'montant', 'mode'])
		expect(Object.keys(validateAssistant({ ...values, mode: 'Chèque' }, 'Bank', {}, [], '2026-11-10'))).toEqual(['reference'])
		expect(DEFAULT_PAIEMENT_COLUMNS).toEqual(['name', 'type_label', 'tiers_label', 'date', 'mode', 'montant', 'non_affecte', 'status', 'tags'])
	})
})
