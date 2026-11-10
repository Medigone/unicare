import { afterEach, describe, expect, it } from 'vitest'
import { allowedClientColumns, allowedClientViews, changedValues, CLIENT_COLUMNS, clientFormValues, clientSortText, DEFAULT_CLIENT_COLUMNS, formatAmount, normalizeName, validateClient, type ClientDetail, type ClientRow } from './clients'
import { rowsToCsv } from './list'
import { normalizeColumns, resolveColumns } from './listViews'

const visibleClientColumns = (keys: string[]) => resolveColumns(CLIENT_COLUMNS, normalizeColumns(keys.map((key) => ({ key })), 'client'))

afterEach(() => {
	delete window.droits
})

describe('clients', () => {
	it('écrit les montants avec une espace insécable pour les milliers', () => {
		expect(formatAmount(1240000)).toBe('1 240 000')
		expect(formatAmount(0)).toBe('0')
		expect(formatAmount(null)).toBe('0')
	})

	it('affiche statut, catégorie, wilaya, contact, téléphone et solde par défaut', () => {
		expect(DEFAULT_CLIENT_COLUMNS).toEqual(['client', 'status', 'categorie', 'wilaya', 'contact', 'telephone', 'solde', 'tags'])
	})

	it('garde toujours la colonne Client et ignore une colonne inconnue', () => {
		expect(visibleClientColumns(['status', 'inconnue']).map((column) => column.key)).toEqual(['client', 'status'])
		expect(clientSortText(null)).toBe('Tri : nom')
		expect(clientSortText({ key: 'solde', dir: 'desc' })).toBe('Tri : solde (da)')
	})

	it('réserve le solde à qui lit la comptabilité', () => {
		expect(allowedClientColumns().map((column) => column.key)).toContain('solde')
		expect(allowedClientViews().map((view) => view.key)).toContain('solde')
		window.droits = { 'GL Entry': { read: false, create: false } }
		expect(allowedClientColumns().map((column) => column.key)).not.toContain('solde')
		expect(allowedClientViews().map((view) => view.key)).not.toContain('solde')
	})

	it('exporte toutes les colonnes affichées', () => {
		const row = { client: 'ATLAS', solde: 1240000.4, wilaya: 'Sétif' } as ClientRow
		expect(rowsToCsv([row], visibleClientColumns(['wilaya', 'solde']))).toBe('﻿Client;Wilaya;Solde (DA)\r\nATLAS;Sétif;1240000')
	})

	it('demande raison sociale, forme juridique, catégorie et commune', () => {
		expect(Object.keys(validateClient({ customer_name: '  ' }))).toEqual(['customer_name', 'forme_juridique', 'categorie', 'commune'])
		expect(validateClient({ customer_name: 'A', forme_juridique: 'SARL', categorie: 'Commercial', commune: 'COM-0001' })).toEqual({})
		// En modification, le statut devient obligatoire.
		expect(Object.keys(validateClient({ customer_name: 'A', forme_juridique: 'SARL', categorie: 'Commercial', commune: 'COM-0001' }, true))).toEqual(['status'])
	})

	it('refuse un contact sans nom, un email ou un GPS illisible', () => {
		const base = { customer_name: 'A', forme_juridique: 'SARL', categorie: 'Commercial', commune: 'COM-0001' }
		expect(Object.keys(validateClient({ ...base, fonction: 'Gérant' }))).toEqual(['contact'])
		expect(Object.keys(validateClient({ ...base, email: 'pas-un-email', contact: 'K', contact_email: 'k@x' }))).toEqual(['email', 'contact_email'])
		expect(Object.keys(validateClient({ ...base, gps: '120, 3' }))).toEqual(['gps'])
		expect(validateClient({ ...base, gps: '36.75, 3.06' })).toEqual({})
	})

	it("n'envoie que les champs changés, jamais le contact", () => {
		const client = { client: 'ATLAS', status: 'Actif', forme_juridique: 'SARL', categorie: 'Commercial', commune: 'COM-0001', gps: null, telephone: null, email: null, pieces: [{ key: 'rc', label: 'Nº RC', numero: '19 B', fichier: null }] } as unknown as ClientDetail
		const initial = clientFormValues(client)
		expect(initial.rc).toBe('19 B')
		expect(changedValues(initial, { ...initial })).toEqual({})
		expect(changedValues(initial, { ...initial, status: 'Dormant', rc: '', contact: ' K. Hamdi ' })).toEqual({ status: 'Dormant', rc: '' })
	})

	it('repère un doublon sans accents ni casse', () => {
		expect(normalizeName('  Pharmacie   de SÉTIF ')).toBe('pharmacie de setif')
	})
})
