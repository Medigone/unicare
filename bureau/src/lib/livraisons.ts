/** Règles de la page Bons de livraison : types, vues, colonnes et préparation des lignes (dépôt, lot, quantité). */
import type { CommentPart } from '@shared/activity'
import { statusDisplay } from '@shared/status'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'
import type { Versions } from './versions'

export type LivraisonView = 'all' | 'brouillons' | 'a_facturer' | 'facturees' | 'retours' | 'clos'

export const LIVRAISON_VIEWS: { key: LivraisonView; label: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'brouillons', label: 'À préparer' },
	{ key: 'a_facturer', label: 'À facturer' },
	{ key: 'facturees', label: 'Facturés' },
	{ key: 'retours', label: 'Retours' },
	{ key: 'clos', label: 'Annulés ou clôturés' },
]

export interface LivraisonRow {
	name: string
	modified: string
	creation: string
	client: string
	client_label: string
	date: string | null
	status: string
	retour: number
	retour_de: string | null
	total_ttc: number
	facture: number
	transport: string | null
	commandes: string | null
	lignes: number
	articles: string
	tags: string[]
	cloche: boolean
}

export interface LivraisonsResponse extends ListResponse {
	livraisons: LivraisonRow[]
	counts: Record<LivraisonView, number>
	page_length: number
}

export interface LotChoice {
	lot: string
	qty: number
	peremption: string | null
	/** Lot périmé : proposé seulement par les mouvements de stock (pour le sortir), après les autres. */
	perime?: boolean
}

export interface LivraisonLine {
	name: string
	article: string
	designation: string
	quantite: number
	unite: string | null
	depot: string | null
	lot: string | null
	avec_lot: number
	stock: number
	prix: number
	montant: number
	commande: string | null
	/** Brouillon seulement : stock par dépôt, et lots disponibles par dépôt (péremption la plus proche d'abord). */
	depots?: { depot: string; qty: number }[]
	lots?: Record<string, LotChoice[]>
}

export type LivraisonAction = 'preparer' | 'valider' | 'supprimer' | 'facture' | 'retour' | 'annuler' | 'nouvelle_version'

export interface LivraisonSuivante {
	name: string
	status: string
	date: string | null
	total: number
}

export interface LivraisonDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	status: string
	docstatus: number
	retour: number
	retour_de: string | null
	client: string
	client_label: string
	date: string | null
	adresse: string | null
	transport: string | null
	vehicule: string | null
	cree_par: string
	lignes: LivraisonLine[]
	total: number
	total_taxes: number
	total_ttc: number
	facture: number
	commandes: string[]
	factures: LivraisonSuivante[] | null
	retours: LivraisonSuivante[]
	/** La pièce annulée dont celle-ci est la nouvelle version. */
	version_de: string | null
	versions: Versions
	actions: LivraisonAction[]
	blocked: string[]
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export const LIVRAISON_COLUMNS: Column<LivraisonRow>[] = [
	{ key: 'name', label: 'Bon', width: 150, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'client_label', label: 'Client', width: 200, minWidth: 120, grow: 1.5, sortable: true, text: (row) => row.client_label },
	{ key: 'status', label: 'Statut', width: 130, minWidth: 96, sortable: true, text: (row) => statusDisplay(row.status) },
	{ key: 'date', label: 'Date', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.date) },
	{ key: 'commandes', label: 'Commande', width: 150, minWidth: 96, sortable: false, text: (row) => row.commandes || '' },
	{ key: 'facture', label: 'Facturé', width: 76, minWidth: 60, sortable: true, end: true, text: (row) => `${Math.round(row.facture)} %` },
	{ key: 'total_ttc', label: 'Total TTC (DA)', width: 120, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.total_ttc) },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'articles', label: 'Articles', width: 220, minWidth: 120, grow: 1, sortable: false, optional: true, text: (row) => row.articles },
	{ key: 'transport', label: 'Nº de transport', width: 120, minWidth: 80, sortable: false, optional: true, text: (row) => row.transport || '' },
	{ key: 'lignes', label: 'Lignes', width: 70, minWidth: 56, sortable: true, end: true, optional: true, text: (row) => row.lignes },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_LIVRAISON_COLUMNS = LIVRAISON_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function livraisonSortText(sort: Sort | null) {
	const column = sort && LIVRAISON_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récents'
}

/** Une ligne en préparation : la quantité reste du texte saisi. */
export interface PrepLine {
	name: string
	quantite: string
	depot: string
	lot: string
}

export function prepLines(livraison: LivraisonDetail): PrepLine[] {
	return livraison.lignes.map((line) => ({ name: line.name, quantite: String(line.quantite), depot: line.depot ?? '', lot: line.lot ?? '' }))
}

/** Lots proposés pour une ligne dans un dépôt ; le lot déjà choisi reste proposé même s'il n'y est plus. */
export function lotsFor(line: LivraisonLine, depot: string, current = '') {
	const lots = line.lots?.[depot] ?? []
	return current && !lots.some((entry) => entry.lot === current) ? [{ lot: current, qty: 0, peremption: null }, ...lots] : lots
}

/**
 * Propose dépôt et lot aux lignes qui n'en ont pas : le dépôt qui a des lots (ou du stock), puis le lot
 * le plus proche de sa péremption qui couvre la quantité, sinon le premier. Ne touche jamais un choix déjà fait.
 */
export function suggestLots(lines: LivraisonLine[], prep: PrepLine[]) {
	return prep.map((entry) => {
		const line = lines.find((item) => item.name === entry.name)
		if (!line || !line.stock) return entry
		let depot = entry.depot
		const hasLots = (name: string) => Boolean(line.lots?.[name]?.length)
		if (line.avec_lot && !hasLots(depot)) depot = Object.keys(line.lots ?? {}).find(hasLots) ?? depot
		if (!line.avec_lot && !line.depots?.some((item) => item.depot === depot)) depot = line.depots?.[0]?.depot ?? depot
		let lot = entry.lot
		if (line.avec_lot && !lot) {
			const quantite = Math.abs(Number(entry.quantite.replace(',', '.')))
			const lots = line.lots?.[depot] ?? []
			lot = (lots.find((item) => item.qty >= quantite) ?? lots[0])?.lot ?? ''
		}
		return { ...entry, depot, lot }
	})
}

/** Seules les lignes changées partent au serveur. */
export function changedPrep(initial: PrepLine[], current: PrepLine[]) {
	return current
		.map((entry) => {
			const before = initial.find((item) => item.name === entry.name)
			const change: { name: string; quantite?: number; depot?: string; lot?: string } = { name: entry.name }
			if (!before || before.quantite.trim() !== entry.quantite.trim()) change.quantite = Number(entry.quantite.replace(/\s/g, '').replace(',', '.'))
			if (!before || before.depot !== entry.depot) change.depot = entry.depot
			if (!before || before.lot !== entry.lot) change.lot = entry.lot
			return change
		})
		.filter((change) => Object.keys(change).length > 1)
}
