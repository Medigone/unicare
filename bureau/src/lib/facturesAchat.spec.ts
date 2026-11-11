import { describe, expect, it } from 'vitest'
import { DEFAULT_FACTURE_ACHAT_COLUMNS, FACTURE_ACHAT_VIEWS, factureAchatStatus, factureAchatTone } from './facturesAchat'

describe("factures d'achat", () => {
	it('affiche le nº du fournisseur et le reste à payer par défaut', () => {
		expect(DEFAULT_FACTURE_ACHAT_COLUMNS).toContain('numero_fournisseur')
		expect(DEFAULT_FACTURE_ACHAT_COLUMNS).toContain('reste')
	})

	it('a les mêmes vues que le serveur', () => {
		expect(FACTURE_ACHAT_VIEWS.map((view) => view.key)).toEqual(['all', 'brouillons', 'a_payer', 'en_retard', 'payees', 'avoirs', 'clos'])
	})

	it('traduit les statuts propres aux achats', () => {
		expect(factureAchatStatus('Debit Note Issued')).toBe('Avoir reçu')
		expect(factureAchatTone('Debit Note Issued')).toBe('gray')
		expect(factureAchatStatus('Unpaid')).toBe('Impayée')
		expect(factureAchatTone('Overdue')).toBe('red')
	})
})
