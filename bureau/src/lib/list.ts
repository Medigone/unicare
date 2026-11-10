/** Règles communes aux listes : colonnes, tri, export et actions groupées. */
import type { FilterField } from './filters'
import type { BulkResult } from '@/types'

export interface Sort {
	key: string
	dir: 'asc' | 'desc'
}

export interface Column<Row = unknown> {
	key: string
	label: string
	/** Largeur fixe en pixels, ou minimum d'une colonne qui partage la place restante. */
	width: number
	/** Largeur en dessous de laquelle la colonne devient illisible quand on la réduit. */
	minWidth?: number
	grow?: number
	sortable: boolean
	/** Absente de l'affichage par défaut : elle s'ajoute par le menu Colonnes. */
	optional?: boolean
	/** Nombres : alignés à droite. */
	end?: boolean
	/** Valeur de l'export. */
	text: (row: Row) => string | number
	/** Colonne ajoutée depuis un champ du doctype : sa valeur est lue à part et elle ne se trie pas. */
	field?: FilterField
}

const CHECK_WIDTH = 32
const COLUMN_GAP = 8
const MENU_WIDTH = 30
const BELL_WIDTH = 30
const TRAY_BORDER = 2

/** Tags d'une ligne, à l'écran comme à l'export. */
export const tagsText = (row: { tags?: string[] }) => (row.tags ?? []).join(', ')

export function gridTemplate<Row>(columns: Column<Row>[]) {
	return columns.map((column) => (column.grow ? `minmax(${column.width}px, ${column.grow}fr)` : `${column.width}px`)).join(' ')
}

export function minListWidth<Row>(columns: Column<Row>[]) {
	return CHECK_WIDTH + BELL_WIDTH + MENU_WIDTH + TRAY_BORDER + columns.reduce((sum, column) => sum + column.width, 0) + COLUMN_GAP * (columns.length - 1)
}

function csvCell(value: string | number) {
	const text = String(value)
	// Un tableur exécuterait une cellule qui commence par l'un de ces signes.
	const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text
	return /[;"\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe
}

/** CSV au format attendu par Excel en français : point-virgule, et marque d'encodage pour les accents. */
export function rowsToCsv<Row>(rows: Row[], columns: Column<Row>[]) {
	const lines = [columns.map((column) => csvCell(column.label)), ...rows.map((row) => columns.map((column) => csvCell(column.text(row))))]
	return `\ufeff${lines.map((line) => line.join(';')).join('\r\n')}`
}

/** Un clic trie, le deuxième inverse, le troisième revient à l'ordre du serveur. */
export function nextSort(sort: Sort | null, key: string): Sort | null {
	if (sort?.key !== key) return { key, dir: 'asc' }
	return sort.dir === 'asc' ? { key, dir: 'desc' } : null
}

/** « 3 clients modifiés · 1 non traité » */
export function bulkSummary(result: BulkResult, one: string, many: string) {
	const done = result.done.length
	const parts = done ? [`${done} ${done > 1 ? many : one}`] : []
	const skipped = result.skipped.length
	if (skipped) parts.push(`${skipped} non traité${skipped > 1 ? 's' : ''}`)
	return parts.join(' · ')
}
