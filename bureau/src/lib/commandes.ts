/** Règles de la page Commandes : types, vues et colonnes. La saisie des lignes est celle du devis (`devis.ts`). */
import type { CommentPart } from '@shared/activity'
import { statusDisplay } from '@shared/status'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'

export type CommandeView = 'all' | 'brouillons' | 'a_livrer' | 'a_facturer' | 'en_retard' | 'en_attente' | 'clos'

export const COMMANDE_VIEWS: { key: CommandeView; label: string }[] = [
	{ key: 'all', label: 'Toutes' },
	{ key: 'brouillons', label: 'Brouillons' },
	{ key: 'a_livrer', label: 'À livrer' },
	{ key: 'a_facturer', label: 'À facturer' },
	{ key: 'en_retard', label: 'Livraison en retard' },
	{ key: 'en_attente', label: 'En attente' },
	{ key: 'clos', label: 'Terminées, clôturées ou annulées' },
]

export interface CommandeRow {
	name: string
	modified: string
	creation: string
	client: string
	client_label: string
	date: string | null
	livraison: string | null
	status: string
	total: number
	total_ttc: number
	livre: number
	facture: number
	reference: string | null
	devis: string | null
	lignes: number
	articles: string
	tags: string[]
	cloche: boolean
}

export interface CommandesResponse extends ListResponse {
	commandes: CommandeRow[]
	counts: Record<CommandeView, number>
	page_length: number
}

export interface CommandeLine {
	name: string
	article: string
	designation: string
	description: string | null
	quantite: number
	livre: number
	unite: string | null
	prix: number
	prix_tarif: number
	montant: number
	facture: number
	livraison: string | null
	depot: string | null
	devis: string | null
}

export type CommandeAction = 'modifier' | 'valider' | 'supprimer' | 'livraison' | 'facture' | 'attente' | 'reprendre' | 'cloturer' | 'rouvrir' | 'annuler'
export type StatusAction = 'attente' | 'reprendre' | 'cloturer' | 'rouvrir'

export interface Suivante {
	name: string
	status: string
	date: string | null
	total: number
}

export interface CommandeDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	status: string
	docstatus: number
	client: string
	client_label: string
	date: string | null
	livraison: string | null
	reference: string | null
	commune: string | null
	wilaya: string | null
	depot: string | null
	cree_par: string
	devise: string
	taxes_modele: string | null
	lignes: CommandeLine[]
	/** Une ligne « TVA », et le droit de timbre à part s'il y en a un. */
	taxes: { description: string; montant: number }[]
	total: number
	total_taxes: number
	total_ttc: number
	arrondi: number | null
	en_lettres: string | null
	livre: number
	facture: number
	devis: string[]
	/** null : la personne ne lit pas ces pièces. */
	livraisons: Suivante[] | null
	factures: Suivante[] | null
	actions: CommandeAction[]
	blocked: string[]
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface CommandeOptions {
	filter_fields?: FilterField[]
	taxes: { value: string; label: string }[]
	taxes_defaut: string | null
	liste_prix: string | null
}

/** Libellés des changements de statut, comme les boutons du Desk. */
export const STATUS_ACTIONS: { key: StatusAction; label: string; done: string }[] = [
	{ key: 'attente', label: 'Mettre en attente', done: 'Commande mise en attente.' },
	{ key: 'reprendre', label: 'Reprendre', done: 'Commande reprise.' },
	{ key: 'cloturer', label: 'Clôturer', done: 'Commande clôturée.' },
	{ key: 'rouvrir', label: 'Rouvrir', done: 'Commande rouverte.' },
]

/** Pourcentage livré ou facturé : « 40 % », sans décimale inutile. */
export function formatPercent(value?: number | null) {
	const rounded = Math.round((value ?? 0) * 10) / 10
	return `${String(rounded).replace('.', ',')} %`
}

export const COMMANDE_COLUMNS: Column<CommandeRow>[] = [
	{ key: 'name', label: 'Commande', width: 150, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'client_label', label: 'Client', width: 200, minWidth: 120, grow: 1.5, sortable: true, text: (row) => row.client_label },
	{ key: 'status', label: 'Statut', width: 150, minWidth: 96, sortable: true, text: (row) => statusDisplay(row.status) },
	{ key: 'date', label: 'Date', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.date) },
	{ key: 'livraison', label: 'Livraison', width: 96, minWidth: 80, sortable: true, text: (row) => formatDay(row.livraison) },
	{ key: 'livre', label: 'Livré', width: 72, minWidth: 60, sortable: true, end: true, text: (row) => formatPercent(row.livre) },
	{ key: 'facture', label: 'Facturé', width: 76, minWidth: 60, sortable: true, end: true, text: (row) => formatPercent(row.facture) },
	{ key: 'total_ttc', label: 'Total TTC (DA)', width: 120, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.total_ttc) },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'reference', label: 'Réf. client', width: 110, minWidth: 80, sortable: false, optional: true, text: (row) => row.reference || '' },
	{ key: 'devis', label: 'Devis', width: 140, minWidth: 96, sortable: false, optional: true, text: (row) => row.devis || '' },
	{ key: 'articles', label: 'Articles', width: 220, minWidth: 120, grow: 1, sortable: false, optional: true, text: (row) => row.articles },
	{ key: 'total', label: 'Total HT (DA)', width: 120, minWidth: 96, sortable: true, end: true, optional: true, text: (row) => Math.round(row.total) },
	{ key: 'creation', label: 'Créée le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifiée le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_COMMANDE_COLUMNS = COMMANDE_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function commandeSortText(sort: Sort | null) {
	const column = sort && COMMANDE_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récentes'
}
