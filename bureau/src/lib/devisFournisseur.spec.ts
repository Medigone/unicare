import { describe, expect, it } from 'vitest'
import { statusDisplay } from '@shared/status'
import { DEFAULT_DEVIS_FOURNISSEUR_COLUMNS, DEVIS_FOURNISSEUR_VIEWS, devisFournisseurSortText } from './devisFournisseur'

describe('devis fournisseur', () => {
	it('affiche le fournisseur, la référence et le total TTC par défaut', () => {
		expect(DEFAULT_DEVIS_FOURNISSEUR_COLUMNS).toEqual(['name', 'fournisseur_label', 'status', 'date', 'valable', 'reference', 'total_ttc', 'tags'])
		expect(devisFournisseurSortText(null)).toBe('Tri : plus récents')
	})

	it('a les mêmes vues que le serveur', () => {
		expect(DEVIS_FOURNISSEUR_VIEWS.map((view) => view.key)).toEqual(['all', 'brouillons', 'ouverts', 'expirent', 'commandes', 'clos'])
	})

	it('traduit les statuts d’achat', () => {
		expect(statusDisplay('Submitted')).toBe('Validé')
		expect(statusDisplay('To Receive and Bill')).toBe('À recevoir et facturer')
	})
})

describe('statuts des factures partout', () => {
	it('traduit les statuts de facture dans la pastille commune', () => {
		expect(statusDisplay('Partly Paid')).toBe('Partiellement payée')
		expect(statusDisplay('Debit Note Issued')).toBe('Avoir reçu')
		expect(statusDisplay('Return Issued')).toBe('Retour émis')
	})
})
