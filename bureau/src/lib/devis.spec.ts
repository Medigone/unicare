import { describe, expect, it } from 'vitest'
import { applyTarifs, dayFromToday, prixManuels, DEFAULT_DEVIS_COLUMNS, devisStatus, draftTotal, linesForServer, parseNumber, validateDevis, type DraftLine } from './devis'

const line = (values: Partial<DraftLine>): DraftLine => ({ key: 1, article: 'PF-000001', designation: 'Lotion', unite: 'Unité', quantite: '1', prix: '', ...values })

describe('devis', () => {
	it('lit les nombres saisis à la française', () => {
		expect(parseNumber('1 250,5')).toBe(1250.5)
		expect(parseNumber('')).toBeNaN()
		expect(parseNumber('abc')).toBeNaN()
	})

	it('calcule le total HT avec le tarif quand le prix est vide', () => {
		const lines = [line({ quantite: '10' }), line({ key: 2, article: 'PF-000002', quantite: '2', prix: '100' }), line({ key: 3, article: '' })]
		expect(draftTotal(lines, { 'PF-000001': 450 })).toBe(4700)
		expect(linesForServer(lines)).toEqual([
			{ article: 'PF-000001', quantite: 10, prix: null },
			{ article: 'PF-000002', quantite: 2, prix: 100 },
		])
	})

	it('demande client, validité et au moins une ligne lisible', () => {
		const today = '2026-11-10'
		expect(Object.keys(validateDevis({ client: '', valable: '', lignes: [line({ article: '' })] }, today))).toEqual(['client', 'valable', 'lignes'])
		expect(validateDevis({ client: 'CLI-1', valable: '2026-11-09', lignes: [line({})] }, today).valable).toBe('La date de validité ne peut pas être passée.')
		expect(validateDevis({ client: 'CLI-1', valable: '2026-12-10', lignes: [line({ quantite: '0' }), line({ key: 2, prix: '-3' })] }, today).ligne).toEqual({ 1: 'Quantité positive attendue.', 2: 'Prix illisible.' })
		expect(validateDevis({ client: 'CLI-1', valable: '2026-12-10', lignes: [line({})] }, today)).toEqual({})
	})

	it('date du jour décalée et statuts en français', () => {
		expect(dayFromToday(30, new Date(2026, 10, 10))).toBe('2026-12-10')
		expect(devisStatus('Open')).toBe('Ouvert')
		expect(devisStatus('Draft')).toBe('Brouillon')
		expect(DEFAULT_DEVIS_COLUMNS).toEqual(['name', 'client_label', 'status', 'date', 'valable', 'total_ttc', 'tags'])
	})
})

describe("ajout d'un article à la pièce", () => {
	it('augmente la quantité au lieu de créer une deuxième ligne', async () => {
		const { addArticle } = await import('./devis')
		let key = 0
		const make = (values: Record<string, string>) => ({ key: ++key, article: '', designation: '', unite: '', quantite: '1', prix: '', ...values })
		const lines: ReturnType<typeof make>[] = []
		addArticle(lines, { name: 'PF-1', label: 'Bouteille', uom: 'U' }, 200, make)
		addArticle(lines, { name: 'PF-2', label: 'Gel', uom: 'U' }, 1.5, make)
		const again = addArticle(lines, { name: 'PF-1', label: 'Bouteille', uom: 'U' }, 50, make)
		expect(lines.map((line) => [line.article, line.quantite])).toEqual([
			['PF-1', '250'],
			['PF-2', '1,5'],
		])
		expect(again.key).toBe(1)
	})
})

describe('changement de liste de prix', () => {
	it('les lignes qui suivaient le tarif suivent le nouveau ; un prix saisi ne bouge pas', () => {
		const lines = [line({ key: 1, article: 'A', prix: '' }), line({ key: 2, article: 'B', prix: '450' }), line({ key: 3, article: 'C', prix: '99' })]
		const tarifs: Record<string, number | null> = { A: 100, B: 450, C: 120 }
		applyTarifs(lines, tarifs, { A: 90, B: 400 })
		expect(lines.map((item) => item.prix)).toEqual(['', '', '99'])
		expect(tarifs).toEqual({ A: 90, B: 400, C: null })
	})
})

describe('prix saisis à reporter dans la liste', () => {
	it('absent de la liste : ajouté ; différent : à choisir ; inchangé depuis l’ouverture ou égal : ignoré', () => {
		const lines = [
			line({ key: 1, article: 'A', prix: '90' }),
			line({ key: 2, article: 'B', prix: '400', designation: 'Crème' }),
			line({ key: 3, article: 'C', prix: '120' }),
			line({ key: 4, article: 'D', prix: '75' }),
			line({ key: 5, article: 'E', prix: '' }),
		]
		const tarifs = { A: null, B: 450, C: 120, D: 80, E: null }
		expect(prixManuels(lines, tarifs, { 4: '75' })).toEqual({ nouveaux: ['A'], differents: [{ article: 'B', designation: 'Crème', saisi: 400, tarif: 450 }] })
	})
})
