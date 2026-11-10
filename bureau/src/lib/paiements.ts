/** Règles de la page Paiements : types, vues, colonnes, et répartition d'un paiement sur les pièces ouvertes. */
import type { CommentPart } from '@shared/activity'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'

export type PaiementView = 'all' | 'brouillons' | 'encaissements' | 'decaissements' | 'non_affectes' | 'annules'
export type PaiementType = 'encaissement_client' | 'remboursement_client' | 'paiement_fournisseur' | 'remboursement_fournisseur'

export const PAIEMENT_VIEWS: { key: PaiementView; label: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'brouillons', label: 'Brouillons' },
	{ key: 'encaissements', label: 'Encaissements' },
	{ key: 'decaissements', label: 'Décaissements' },
	{ key: 'non_affectes', label: 'Avec avance non affectée' },
	{ key: 'annules', label: 'Annulés' },
]

/** Ce que l'assistant dit de chaque type : qui paie qui, et ce qu'on rapproche. */
export const TYPE_HELP: Record<PaiementType, { tiers: string; pieces: string; vide: string; avance: string }> = {
	encaissement_client: { tiers: 'Client', pieces: 'Factures impayées', vide: 'Aucune facture impayée pour ce client.', avance: 'Le non-affecté reste une avance du client, à rapprocher plus tard.' },
	remboursement_client: { tiers: 'Client', pieces: 'Avoirs à rembourser', vide: 'Aucun avoir à rembourser pour ce client.', avance: "Le non-affecté reste une avance versée au client." },
	paiement_fournisseur: { tiers: 'Fournisseur', pieces: "Factures d'achat impayées", vide: "Aucune facture d'achat impayée pour ce fournisseur.", avance: 'Le non-affecté reste une avance au fournisseur, à rapprocher plus tard.' },
	remboursement_fournisseur: { tiers: 'Fournisseur', pieces: 'Avoirs fournisseur à encaisser', vide: 'Aucun avoir à encaisser pour ce fournisseur.', avance: 'Le non-affecté reste une avance reçue du fournisseur.' },
}

export interface PaiementRow {
	name: string
	modified: string
	creation: string
	type: PaiementType | null
	type_label: string
	sens: 'Receive' | 'Pay' | string
	tiers_type: string
	tiers: string
	tiers_label: string
	date: string | null
	montant: number
	non_affecte: number
	mode: string | null
	reference: string | null
	status: 'Draft' | 'Submitted' | 'Cancelled'
	tags: string[]
	cloche: boolean
}

export interface PaiementsResponse extends ListResponse {
	paiements: PaiementRow[]
	counts: Record<PaiementView, number>
	page_length: number
}

export interface PieceOuverte {
	doctype: string
	name: string
	date: string | null
	echeance: string | null
	total: number
	reste: number
	avoir: number
	/** Déjà affecté par le paiement en cours de modification. */
	deja: number
}

export type PaiementAction = 'modifier' | 'valider' | 'supprimer' | 'annuler'

export interface PaiementDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	status: 'Draft' | 'Submitted' | 'Cancelled'
	docstatus: number
	type: PaiementType | null
	type_label: string
	sens: string
	tiers_type: string
	tiers: string
	tiers_label: string
	date: string | null
	montant: number
	affecte: number
	non_affecte: number
	mode: string | null
	reference: string | null
	date_reference: string | null
	remarque: string | null
	compte_depart: string
	compte_arrivee: string
	en_lettres: string | null
	affectations: { doctype: string; name: string; echeance: string | null; total: number; reste: number; montant: number }[]
	cree_par: string
	actions: PaiementAction[]
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface PaiementOptions {
	filter_fields?: FilterField[]
	types: { value: PaiementType; label: string; sens: string; tiers: string }[]
	modes: { value: string; type: string }[]
	can_create: boolean
}

/** Statut affiché : brouillon, validé ou annulé. */
export const PAIEMENT_STATUS: Record<string, string> = { Draft: 'Brouillon', Submitted: 'Validé', Cancelled: 'Annulé' }

export const PAIEMENT_COLUMNS: Column<PaiementRow>[] = [
	{ key: 'name', label: 'Paiement', width: 160, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'type_label', label: 'Type', width: 170, minWidth: 110, sortable: false, text: (row) => row.type_label },
	{ key: 'tiers_label', label: 'Tiers', width: 200, minWidth: 120, grow: 1.5, sortable: true, text: (row) => row.tiers_label },
	{ key: 'date', label: 'Date', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.date) },
	{ key: 'mode', label: 'Mode', width: 110, minWidth: 80, sortable: true, text: (row) => row.mode || '' },
	{ key: 'montant', label: 'Montant (DA)', width: 120, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.montant) },
	{ key: 'non_affecte', label: 'Non affecté (DA)', width: 124, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.non_affecte) },
	{ key: 'status', label: 'Statut', width: 104, minWidth: 88, sortable: true, text: (row) => PAIEMENT_STATUS[row.status] ?? row.status },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'reference', label: 'Référence', width: 130, minWidth: 88, sortable: false, optional: true, text: (row) => row.reference || '' },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_PAIEMENT_COLUMNS = PAIEMENT_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function paiementSortText(sort: Sort | null) {
	const column = sort && PAIEMENT_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récents'
}

/** Ce qu'une pièce peut encore recevoir : son reste dû, plus ce que le paiement modifié lui affecte déjà. */
export function capacity(piece: PieceOuverte) {
	return Math.round((piece.reste + piece.deja) * 100) / 100
}

/**
 * Répartit le montant sur les pièces, dans l'ordre reçu (échéance la plus ancienne d'abord), sans dépasser ce que
 * chaque pièce peut recevoir. Rend un montant par pièce ; ce qui reste devient une avance.
 */
export function proposeAllocation(montant: number, pieces: PieceOuverte[]) {
	let left = Math.max(0, Math.round(montant * 100) / 100)
	const result: Record<string, number> = {}
	for (const piece of pieces) {
		const amount = Math.min(left, capacity(piece))
		result[piece.name] = Math.round(amount * 100) / 100
		left = Math.round((left - amount) * 100) / 100
	}
	return result
}

export interface AssistantErrors {
	type?: string
	tiers?: string
	montant?: string
	mode?: string
	date?: string
	reference?: string
	affectations?: string
	/** Par pièce. */
	piece?: Record<string, string>
}

/** Mêmes refus que le serveur, dits avant l'envoi. */
export function validateAssistant(
	values: { type: string; tiers: string; montant: number; mode: string; date: string; reference: string },
	modeType: string | undefined,
	allocations: Record<string, number>,
	pieces: PieceOuverte[],
	today: string,
) {
	const errors: AssistantErrors = {}
	if (!values.type) errors.type = 'Choisissez le type de paiement.'
	if (!values.tiers) errors.tiers = 'Choisissez le tiers.'
	if (!(values.montant > 0)) errors.montant = 'Saisissez un montant positif.'
	if (!values.mode) errors.mode = 'Choisissez le mode de paiement.'
	if (!values.date) errors.date = 'Choisissez la date.'
	else if (values.date > today) errors.date = 'La date ne peut pas être dans le futur.'
	if (modeType === 'Bank' && !values.reference.trim()) errors.reference = 'Saisissez le nº de chèque, de virement ou de traite.'
	const piece: Record<string, string> = {}
	let total = 0
	for (const item of pieces) {
		const amount = allocations[item.name] ?? 0
		if (amount < 0 || !Number.isFinite(amount)) piece[item.name] = 'Montant illisible.'
		else if (amount > capacity(item) + 0.005) piece[item.name] = 'Au-delà du reste dû.'
		total += Number.isFinite(amount) ? amount : 0
	}
	if (Object.keys(piece).length) errors.piece = piece
	if (total > values.montant + 0.005) errors.affectations = 'Les montants affectés dépassent le montant du paiement.'
	return errors
}
