import { afterEach, describe, expect, it } from 'vitest'
import { allowedFournisseurColumns, allowedFournisseurViews, changedFournisseurValues, DEFAULT_FOURNISSEUR_COLUMNS, fournisseurFormValues, fournisseurSortText, validateFournisseur, type FournisseurDetail } from './fournisseurs'

afterEach(() => {
	delete window.droits
})

describe('fournisseurs', () => {
	it('affiche statut, catégorie, wilaya, contact, téléphone et reste à payer par défaut', () => {
		expect(DEFAULT_FOURNISSEUR_COLUMNS).toEqual(['fournisseur', 'status', 'categorie', 'wilaya', 'contact', 'telephone', 'solde', 'tags'])
		expect(fournisseurSortText(null)).toBe('Tri : nom')
	})

	it('réserve le solde à qui lit la comptabilité', () => {
		expect(allowedFournisseurViews().map((view) => view.key)).toContain('solde')
		window.droits = { 'GL Entry': { read: false, create: false } }
		expect(allowedFournisseurColumns().map((column) => column.key)).not.toContain('solde')
		expect(allowedFournisseurViews().map((view) => view.key)).not.toContain('solde')
	})

	it('dit les refus du serveur avant l’envoi', () => {
		expect(Object.keys(validateFournisseur({}))).toEqual(['supplier_name', 'categorie'])
		expect(validateFournisseur({ supplier_name: 'A', categorie: 'B', fonction: 'Commercial' }).contact).toBeTruthy()
		expect(validateFournisseur({ supplier_name: 'A', categorie: 'B', contact: 'X', contact_email: 'pas-un-email' }).contact_email).toBeTruthy()
		expect(validateFournisseur({ supplier_name: 'A', categorie: 'B' }, true).status).toBeTruthy()
	})

	it("n'envoie que les champs modifiés", () => {
		const fournisseur = { fournisseur: 'AURES', status: 'Actif', categorie: 'Locale', commune: null, pieces: [{ key: 'nif', label: 'Nº NIF', numero: '1', fichier: null }] } as unknown as FournisseurDetail
		const initial = fournisseurFormValues(fournisseur)
		expect(changedFournisseurValues(initial, { ...initial, status: 'Exclu', nif: '1 ' })).toEqual({ status: 'Exclu' })
	})
})
