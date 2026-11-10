/** Règles de la page Factures : types, vues, colonnes, et saisie d'un encaissement. */
import type { CommentPart } from '@shared/activity'
import { statusDisplay } from '@shared/status'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'

export type FactureView = 'all' | 'brouillons' | 'impayees' | 'en_retard' | 'payees' | 'avoirs' | 'clos'

export const FACTURE_VIEWS: { key: FactureView; label: string }[] = [
	{ key: 'all', label: 'Toutes' },
	{ key: 'brouillons', label: 'Brouillons' },
	{ key: 'impayees', label: 'Impayées' },
	{ key: 'en_retard', label: 'En retard' },
	{ key: 'payees', label: 'Payées' },
	{ key: 'avoirs', label: 'Avoirs' },
	{ key: 'clos', label: 'Annulées ou créditées' },
]

/** Statuts de facture ERPNext absents de la règle commune, en français. */
const FACTURE_STATUS: Record<string, string> = {
	Unpaid: 'Impayée',
	'Partly Paid': 'Partiellement payée',
	Paid: 'Payée',
	Overdue: 'En retard',
	Return: 'Avoir',
	'Credit Note Issued': 'Avoir émis',
	'Unpaid and Discounted': 'Impayée, escomptée',
	'Partly Paid and Discounted': 'Partiellement payée, escomptée',
	'Overdue and Discounted': 'En retard, escomptée',
}
export function factureStatus(status?: string | null) {
	return status ? (FACTURE_STATUS[status] ?? statusDisplay(status)) : ''
}
/** Teinte de la pastille : la règle commune ne connaît pas ces libellés. */
export function factureTone(status?: string | null): 'red' | 'amber' | 'green' | 'blue' | 'gray' | undefined {
	if (!status) return undefined
	if (status.startsWith('Overdue')) return 'red'
	if (status.startsWith('Partly Paid')) return 'amber'
	if (status.startsWith('Unpaid')) return 'blue'
	if (status === 'Paid') return 'green'
	if (status === 'Return' || status === 'Credit Note Issued') return 'gray'
	return undefined
}

export interface FactureRow {
	name: string
	modified: string
	creation: string
	client: string
	client_label: string
	date: string | null
	echeance: string | null
	status: string
	avoir: number
	avoir_de: string | null
	total_ttc: number
	reste: number
	commandes: string | null
	livraisons: string | null
	tags: string[]
	cloche: boolean
}

export interface FacturesResponse extends ListResponse {
	factures: FactureRow[]
	counts: Record<FactureView, number>
	reste_du: number
	page_length: number
}

export interface FactureLine {
	name: string
	article: string
	designation: string
	quantite: number
	unite: string | null
	prix: number
	montant: number
	commande: string | null
	livraison: string | null
}

export type FactureAction = 'modifier' | 'valider' | 'supprimer' | 'encaisser' | 'avoir' | 'annuler'

export interface Paiement {
	name: string
	date: string | null
	mode: string | null
	reference: string | null
	montant: number
	brouillon: boolean
}

export interface FactureDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	status: string
	docstatus: number
	avoir: number
	avoir_de: string | null
	avoir_autonome: number
	client: string
	client_label: string
	date: string | null
	echeance: string | null
	cree_par: string
	taxes_modele: string | null
	lignes: FactureLine[]
	taxes: { description: string; taux: number; montant: number }[]
	total: number
	total_taxes: number
	total_ttc: number
	en_lettres: string | null
	reste: number
	paye: number
	commandes: string[]
	livraisons: string[]
	/** null : la personne ne lit pas les paiements. */
	paiements: Paiement[] | null
	avoirs: { name: string; status: string; date: string | null; total: number }[]
	actions: FactureAction[]
	blocked: string[]
	modes: { value: string; type: string }[]
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface FactureOptions {
	filter_fields?: FilterField[]
	taxes: { value: string; label: string }[]
}

export const FACTURE_COLUMNS: Column<FactureRow>[] = [
	{ key: 'name', label: 'Facture', width: 150, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'client_label', label: 'Client', width: 200, minWidth: 120, grow: 1.5, sortable: true, text: (row) => row.client_label },
	{ key: 'status', label: 'Statut', width: 150, minWidth: 96, sortable: true, text: (row) => factureStatus(row.status) },
	{ key: 'date', label: 'Date', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.date) },
	{ key: 'echeance', label: 'Échéance', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.echeance) },
	{ key: 'total_ttc', label: 'Total TTC (DA)', width: 120, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.total_ttc) },
	{ key: 'reste', label: 'Reste dû (DA)', width: 116, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.reste) },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'commandes', label: 'Commande', width: 140, minWidth: 96, sortable: false, optional: true, text: (row) => row.commandes || '' },
	{ key: 'livraisons', label: 'Bon de livraison', width: 140, minWidth: 96, sortable: false, optional: true, text: (row) => row.livraisons || '' },
	{ key: 'creation', label: 'Créée le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifiée le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_FACTURE_COLUMNS = FACTURE_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function factureSortText(sort: Sort | null) {
	const column = sort && FACTURE_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récentes'
}

export interface EncaissementValues {
	montant: string
	mode: string
	date: string
	reference: string
	date_reference: string
}

/** Mêmes refus que le serveur : montant positif et au plus le reste dû, référence obligatoire pour un mode bancaire. */
export function validateEncaissement(values: EncaissementValues, reste: number, modeType: string | undefined, today: string) {
	const errors: Partial<Record<keyof EncaissementValues, string>> = {}
	const montant = Number(values.montant.replace(/[\s ]/g, '').replace(',', '.'))
	if (!(montant > 0)) errors.montant = 'Saisissez un montant positif.'
	else if (montant > reste + 0.005) errors.montant = 'Le montant dépasse le reste dû.'
	if (!values.mode) errors.mode = 'Choisissez le mode de paiement.'
	if (!values.date) errors.date = 'Choisissez la date.'
	else if (values.date > today) errors.date = "La date ne peut pas être dans le futur."
	if (modeType === 'Bank' && !values.reference.trim()) errors.reference = 'Saisissez le nº de chèque, de virement ou de traite.'
	return errors
}
