/** Règles de la page Réceptions : types, vues, colonnes et préparation des lignes (quantité, dépôt, lot fournisseur). */
import type { CommentPart } from '@shared/activity'
import { statusDisplay } from '@shared/status'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { LivraisonSuivante } from './livraisons'
import type { ListResponse } from './useServerList'

export type ReceptionView = 'all' | 'brouillons' | 'a_facturer' | 'facturees' | 'retours' | 'clos'

export const RECEPTION_VIEWS: { key: ReceptionView; label: string }[] = [
	{ key: 'all', label: 'Toutes' },
	{ key: 'brouillons', label: 'À préparer' },
	{ key: 'a_facturer', label: 'À facturer' },
	{ key: 'facturees', label: 'Facturées' },
	{ key: 'retours', label: 'Retours fournisseur' },
	{ key: 'clos', label: 'Annulées ou clôturées' },
]

export interface ReceptionRow {
	name: string
	modified: string
	creation: string
	fournisseur: string
	fournisseur_label: string
	date: string | null
	status: string
	retour: number
	retour_de: string | null
	bl_fournisseur: string | null
	total_ttc: number
	facture: number
	commandes: string | null
	lignes: number
	articles: string
	tags: string[]
	cloche: boolean
}

export interface ReceptionsResponse extends ListResponse {
	receptions: ReceptionRow[]
	counts: Record<ReceptionView, number>
	page_length: number
}

export interface ReceptionLine {
	name: string
	article: string
	designation: string
	quantite: number
	unite: string | null
	depot: string | null
	lot: string | null
	peremption: string | null
	avec_lot: number
	/** Fût ou conditionnement : le lot du fournisseur est exigé à la validation. */
	lot_obligatoire: number
	stock: number
	prix: number
	montant: number
	commande: string | null
}

export type ReceptionAction = 'preparer' | 'valider' | 'supprimer' | 'facture' | 'retour' | 'annuler'

export interface ReceptionDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	status: string
	docstatus: number
	retour: number
	retour_de: string | null
	fournisseur: string
	fournisseur_label: string
	date: string | null
	bl_fournisseur: string | null
	transport: string | null
	transporteur: string | null
	depot: string | null
	/** Brouillon seulement : les dépôts où recevoir. */
	depots: string[]
	cree_par: string
	lignes: ReceptionLine[]
	total: number
	total_taxes: number
	total_ttc: number
	facture: number
	commandes: string[]
	factures: LivraisonSuivante[] | null
	retours: LivraisonSuivante[]
	actions: ReceptionAction[]
	blocked: string[]
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export const RECEPTION_COLUMNS: Column<ReceptionRow>[] = [
	{ key: 'name', label: 'Réception', width: 160, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'fournisseur_label', label: 'Fournisseur', width: 200, minWidth: 120, grow: 1.5, sortable: true, text: (row) => row.fournisseur_label },
	{ key: 'status', label: 'Statut', width: 130, minWidth: 96, sortable: true, text: (row) => statusDisplay(row.status) },
	{ key: 'date', label: 'Date', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.date) },
	{ key: 'bl_fournisseur', label: 'BL fournisseur', width: 120, minWidth: 80, sortable: true, text: (row) => row.bl_fournisseur || '' },
	{ key: 'commandes', label: 'Commande', width: 160, minWidth: 96, sortable: false, text: (row) => row.commandes || '' },
	{ key: 'facture', label: 'Facturé', width: 76, minWidth: 60, sortable: true, end: true, text: (row) => `${Math.round(row.facture)} %` },
	{ key: 'total_ttc', label: 'Total TTC (DA)', width: 120, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.total_ttc) },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'articles', label: 'Articles', width: 220, minWidth: 120, grow: 1, sortable: false, optional: true, text: (row) => row.articles },
	{ key: 'lignes', label: 'Lignes', width: 70, minWidth: 56, sortable: true, end: true, optional: true, text: (row) => row.lignes },
	{ key: 'creation', label: 'Créée le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifiée le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_RECEPTION_COLUMNS = RECEPTION_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function receptionSortText(sort: Sort | null) {
	const column = sort && RECEPTION_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récentes'
}

/** Une ligne en préparation : la quantité reste du texte saisi. */
export interface ReceptionPrep {
	name: string
	quantite: string
	depot: string
	lot: string
	peremption: string
}

export function receptionPrepLines(reception: ReceptionDetail): ReceptionPrep[] {
	return reception.lignes.map((line) => ({ name: line.name, quantite: String(line.quantite), depot: line.depot ?? '', lot: line.lot ?? '', peremption: line.peremption ?? '' }))
}

export interface ReceptionPrepChange {
	name: string
	quantite?: number
	depot?: string
	lot?: string
	peremption?: string
}

/** Seules les lignes changées partent au serveur ; un lot et sa péremption partent ensemble. */
export function changedReceptionPrep(initial: ReceptionPrep[], current: ReceptionPrep[]) {
	return current
		.map((entry) => {
			const before = initial.find((item) => item.name === entry.name)
			const change: ReceptionPrepChange = { name: entry.name }
			if (!before || before.quantite.trim() !== entry.quantite.trim()) change.quantite = Number(entry.quantite.replace(/\s/g, '').replace(',', '.'))
			if (!before || before.depot !== entry.depot) change.depot = entry.depot
			if (!before || before.lot.trim() !== entry.lot.trim() || before.peremption !== entry.peremption) {
				change.lot = entry.lot.trim()
				change.peremption = entry.peremption
			}
			return change
		})
		.filter((change) => Object.keys(change).length > 1)
}

/** Le dépôt de la réception, posé sur les lignes qui n'en ont pas. Ne touche jamais un choix déjà fait. */
export function fillDepot(prep: ReceptionPrep[], depot: string) {
	return prep.map((entry) => (entry.depot || !depot ? entry : { ...entry, depot }))
}
