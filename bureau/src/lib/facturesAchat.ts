/** Règles de la page Factures d'achat : types, vues et colonnes. Le paiement se saisit comme un encaissement. */
import type { CommentPart } from '@shared/activity'
import { formatDay } from './display'
import { factureStatus, factureTone, type Paiement } from './factures'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'

export { validateEncaissement as validatePaiementFournisseur, type EncaissementValues as PaiementFournisseurValues } from './factures'

export type FactureAchatView = 'all' | 'brouillons' | 'a_payer' | 'en_retard' | 'payees' | 'avoirs' | 'clos'

export const FACTURE_ACHAT_VIEWS: { key: FactureAchatView; label: string }[] = [
	{ key: 'all', label: 'Toutes' },
	{ key: 'brouillons', label: 'Brouillons' },
	{ key: 'a_payer', label: 'À payer' },
	{ key: 'en_retard', label: 'En retard' },
	{ key: 'payees', label: 'Payées' },
	{ key: 'avoirs', label: 'Avoirs fournisseur' },
	{ key: 'clos', label: 'Annulées ou créditées' },
]

/** Statut en français : celui des factures client, plus l'avoir reçu du fournisseur. */
export function factureAchatStatus(status?: string | null) {
	return status === 'Debit Note Issued' ? 'Avoir reçu' : factureStatus(status)
}
export function factureAchatTone(status?: string | null) {
	return status === 'Debit Note Issued' ? 'gray' : factureTone(status)
}

export interface FactureAchatRow {
	name: string
	modified: string
	creation: string
	fournisseur: string
	fournisseur_label: string
	date: string | null
	echeance: string | null
	numero_fournisseur: string | null
	status: string
	avoir: number
	avoir_de: string | null
	total_ttc: number
	reste: number
	commandes: string | null
	receptions: string | null
	tags: string[]
	cloche: boolean
}

export interface FacturesAchatResponse extends ListResponse {
	factures: FactureAchatRow[]
	counts: Record<FactureAchatView, number>
	reste_du: number
	page_length: number
}

export interface FactureAchatLine {
	name: string
	article: string
	designation: string
	quantite: number
	unite: string | null
	prix: number
	montant: number
	commande: string | null
	reception: string | null
}

export type FactureAchatAction = 'modifier' | 'valider' | 'supprimer' | 'payer' | 'avoir' | 'annuler'

export interface FactureAchatDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	status: string
	docstatus: number
	avoir: number
	avoir_de: string | null
	avoir_autonome: number
	fournisseur: string
	fournisseur_label: string
	date: string | null
	echeance: string | null
	numero_fournisseur: string | null
	date_fournisseur: string | null
	cree_par: string
	taxes_modele: string | null
	lignes: FactureAchatLine[]
	/** Une ligne « TVA », et le droit de timbre à part s'il y en a un. */
	taxes: { description: string; montant: number }[]
	total: number
	total_taxes: number
	total_ttc: number
	en_lettres: string | null
	reste: number
	paye: number
	commandes: string[]
	receptions: string[]
	/** null : la personne ne lit pas les paiements. */
	paiements: Paiement[] | null
	avoirs: { name: string; status: string; date: string | null; total: number }[]
	actions: FactureAchatAction[]
	blocked: string[]
	modes: { value: string; type: string }[]
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface FactureAchatOptions {
	filter_fields?: FilterField[]
	taxes: { value: string; label: string }[]
}

export interface FactureAchatValues {
	numero_fournisseur?: string
	date_fournisseur?: string
	echeance?: string
	taxes?: string
	lignes?: { name: string; quantite: number }[]
}

export const FACTURE_ACHAT_COLUMNS: Column<FactureAchatRow>[] = [
	{ key: 'name', label: 'Facture', width: 160, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'fournisseur_label', label: 'Fournisseur', width: 200, minWidth: 120, grow: 1.5, sortable: true, text: (row) => row.fournisseur_label },
	{ key: 'numero_fournisseur', label: 'Nº fournisseur', width: 130, minWidth: 88, sortable: true, text: (row) => row.numero_fournisseur || '' },
	{ key: 'status', label: 'Statut', width: 150, minWidth: 96, sortable: true, text: (row) => factureAchatStatus(row.status) },
	{ key: 'date', label: 'Date', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.date) },
	{ key: 'echeance', label: 'Échéance', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.echeance) },
	{ key: 'total_ttc', label: 'Total TTC (DA)', width: 120, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.total_ttc) },
	{ key: 'reste', label: 'Reste à payer (DA)', width: 130, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.reste) },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'commandes', label: "Commande d'achat", width: 150, minWidth: 96, sortable: false, optional: true, text: (row) => row.commandes || '' },
	{ key: 'receptions', label: 'Réception', width: 150, minWidth: 96, sortable: false, optional: true, text: (row) => row.receptions || '' },
	{ key: 'creation', label: 'Créée le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifiée le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_FACTURE_ACHAT_COLUMNS = FACTURE_ACHAT_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function factureAchatSortText(sort: Sort | null) {
	const column = sort && FACTURE_ACHAT_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récentes'
}
