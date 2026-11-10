import { describe, expect, it } from 'vitest'
import { bulkSummary, gridTemplate, minListWidth, nextSort, rowsToCsv, tagsText, type Column } from './list'

interface Row {
	name: string
	label: string
	total: number
	tags?: string[]
}

const COLUMNS: Column<Row>[] = [
	{ key: 'label', label: 'Libellé', width: 140, grow: 1.5, sortable: true, text: (row) => row.label },
	{ key: 'total', label: 'Total', width: 80, sortable: true, end: true, text: (row) => row.total },
	{ key: 'tags', label: 'Tags', width: 100, sortable: false, text: (row) => tagsText(row) },
]

describe('listes', () => {
	it('calcule la grille et la largeur minimale des colonnes affichées', () => {
		expect(gridTemplate(COLUMNS)).toBe('minmax(140px, 1.5fr) 80px 100px')
		// Case, cloche, menu et bordure du plateau, puis les colonnes et leurs écarts.
		expect(minListWidth(COLUMNS)).toBe(32 + 30 + 30 + 2 + 320 + 8 * 2)
	})

	it('exporte un CSV lisible par Excel, sans formule exécutable', () => {
		const csv = rowsToCsv(
			[
				{ name: '1', label: '=SOMME(A1)', total: 2, tags: ['a', 'b'] },
				{ name: '2', label: 'A;B', total: 0 },
			],
			COLUMNS,
		)
		expect(csv.startsWith('﻿Libellé;Total;Tags')).toBe(true)
		expect(csv).toContain("'=SOMME(A1);2;a, b")
		expect(csv).toContain('"A;B";0;')
	})

	it('passe par croissant, décroissant, puis ordre du serveur', () => {
		const asc = nextSort(null, 'label')
		const desc = nextSort(asc, 'label')
		expect(asc).toEqual({ key: 'label', dir: 'asc' })
		expect(desc).toEqual({ key: 'label', dir: 'desc' })
		expect(nextSort(desc, 'label')).toBeNull()
		expect(nextSort(desc, 'total')).toEqual({ key: 'total', dir: 'asc' })
	})

	it('résume une action groupée', () => {
		const skipped = { name: 'CLI-3', reason: 'Refusé.' }
		expect(bulkSummary({ done: ['CLI-1'], skipped: [] }, 'client modifié', 'clients modifiés')).toBe('1 client modifié')
		expect(bulkSummary({ done: ['CLI-1', 'CLI-2'], skipped: [skipped] }, 'client modifié', 'clients modifiés')).toBe('2 clients modifiés · 1 non traité')
		expect(bulkSummary({ done: [], skipped: [skipped, skipped] }, 'client modifié', 'clients modifiés')).toBe('2 non traités')
	})
})
