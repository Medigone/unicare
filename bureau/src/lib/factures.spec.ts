import { describe, expect, it } from 'vitest'
import { DEFAULT_FACTURE_COLUMNS, factureStatus, factureTone, validateEncaissement } from './factures'

const values = { montant: '500', mode: 'Espèces', date: '2026-11-10', reference: '', date_reference: '' }

describe('factures', () => {
	it('traduit et teinte les statuts de facture', () => {
		expect(factureStatus('Partly Paid')).toBe('Partiellement payée')
		expect(factureStatus('Draft')).toBe('Brouillon')
		expect([factureTone('Overdue'), factureTone('Paid'), factureTone('Unpaid'), factureTone('Draft')]).toEqual(['red', 'green', 'blue', undefined])
		expect(DEFAULT_FACTURE_COLUMNS).toEqual(['name', 'client_label', 'status', 'date', 'echeance', 'total_ttc', 'reste', 'tags'])
	})

	it('refuse un encaissement nul, au-delà du reste dû ou daté du futur', () => {
		expect(validateEncaissement(values, 2000, 'Cash', '2026-11-10')).toEqual({})
		expect(Object.keys(validateEncaissement({ ...values, montant: '0' }, 2000, 'Cash', '2026-11-10'))).toEqual(['montant'])
		expect(validateEncaissement({ ...values, montant: '2 000,01' }, 2000, 'Cash', '2026-11-10').montant).toBe('Le montant dépasse le reste dû.')
		expect(Object.keys(validateEncaissement({ ...values, date: '2026-11-11' }, 2000, 'Cash', '2026-11-10'))).toEqual(['date'])
	})

	it('demande la référence pour un mode bancaire', () => {
		expect(Object.keys(validateEncaissement({ ...values, mode: 'Chèque' }, 2000, 'Bank', '2026-11-10'))).toEqual(['reference'])
		expect(validateEncaissement({ ...values, mode: 'Chèque', reference: 'CHQ-1' }, 2000, 'Bank', '2026-11-10')).toEqual({})
	})
})
