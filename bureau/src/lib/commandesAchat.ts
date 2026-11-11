/** Règles de la page Commandes d'achat : types, vues et colonnes. La saisie des lignes est celle du devis (`devis.ts`). */
import type { CommentPart } from '@shared/activity'
import { statusDisplay } from '@shared/status'
import type { AchatOptions } from './achats'
import { formatPercent, type StatusAction, type Suivante } from './commandes'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'
import type { Versions } from './versions'

export { formatPercent } from './commandes'
export type { StatusAction, Suivante } from './commandes'

export type CommandeAchatView = 'all' | 'brouillons' | 'a_recevoir' | 'a_facturer' | 'en_retard' | 'en_attente' | 'clos'

export const COMMANDE_ACHAT_VIEWS: { key: CommandeAchatView; label: string }[] = [
	{ key: 'all', label: 'Toutes' },
	{ key: 'brouillons', label: 'Brouillons' },
	{ key: 'a_recevoir', label: 'À recevoir' },
	{ key: 'a_facturer', label: 'À facturer' },
	{ key: 'en_retard', label: 'Réception en retard' },
	{ key: 'en_attente', label: 'En attente' },
	{ key: 'clos', label: 'Terminées, clôturées ou annulées' },
]

/** Statuts d'une commande qui attend encore sa réception. */
export const A_RECEVOIR = ['To Receive and Bill', 'To Receive']

export interface CommandeAchatRow {
	name: string
	modified: string
	creation: string
	fournisseur: string
	fournisseur_label: string
	date: string | null
	reception: string | null
	status: string
	total: number
	total_ttc: number
	recu: number
	facture: number
	devis: string | null
	lignes: number
	articles: string
	tags: string[]
	cloche: boolean
}

export interface CommandesAchatResponse extends ListResponse {
	commandes: CommandeAchatRow[]
	counts: Record<CommandeAchatView, number>
	page_length: number
}

export interface CommandeAchatLine {
	name: string
	article: string
	designation: string
	description: string | null
	quantite: number
	recu: number
	unite: string | null
	prix: number
	prix_tarif: number
	montant: number
	facture: number
	reception: string | null
	depot: string | null
	devis: string | null
}

export type CommandeAchatAction = 'modifier' | 'valider' | 'supprimer' | 'reception' | 'facture' | StatusAction | 'annuler' | 'nouvelle_version'

export interface CommandeAchatDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	status: string
	docstatus: number
	fournisseur: string
	fournisseur_label: string
	date: string | null
	reception: string | null
	depot: string | null
	cree_par: string
	devise: string
	taxes_modele: string | null
	lignes: CommandeAchatLine[]
	/** Une ligne « TVA », et le droit de timbre à part s'il y en a un. */
	taxes: { description: string; montant: number }[]
	total: number
	total_taxes: number
	total_ttc: number
	arrondi: number | null
	en_lettres: string | null
	recu: number
	facture: number
	devis: string[]
	/** null : la personne ne lit pas ces pièces. */
	receptions: Suivante[] | null
	factures: Suivante[] | null
	/** La pièce annulée dont celle-ci est la nouvelle version. */
	version_de: string | null
	versions: Versions
	actions: CommandeAchatAction[]
	blocked: string[]
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface CommandeAchatOptions extends AchatOptions {
	filter_fields?: FilterField[]
}

export const COMMANDE_ACHAT_COLUMNS: Column<CommandeAchatRow>[] = [
	{ key: 'name', label: 'Commande', width: 160, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'fournisseur_label', label: 'Fournisseur', width: 200, minWidth: 120, grow: 1.5, sortable: true, text: (row) => row.fournisseur_label },
	{ key: 'status', label: 'Statut', width: 160, minWidth: 96, sortable: true, text: (row) => statusDisplay(row.status) },
	{ key: 'date', label: 'Date', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.date) },
	{ key: 'reception', label: 'Réception', width: 96, minWidth: 80, sortable: true, text: (row) => formatDay(row.reception) },
	{ key: 'recu', label: 'Reçu', width: 72, minWidth: 60, sortable: true, end: true, text: (row) => formatPercent(row.recu) },
	{ key: 'facture', label: 'Facturé', width: 76, minWidth: 60, sortable: true, end: true, text: (row) => formatPercent(row.facture) },
	{ key: 'total_ttc', label: 'Total TTC (DA)', width: 120, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.total_ttc) },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'devis', label: 'Devis fournisseur', width: 150, minWidth: 96, sortable: false, optional: true, text: (row) => row.devis || '' },
	{ key: 'articles', label: 'Articles', width: 220, minWidth: 120, grow: 1, sortable: false, optional: true, text: (row) => row.articles },
	{ key: 'total', label: 'Total HT (DA)', width: 120, minWidth: 96, sortable: true, end: true, optional: true, text: (row) => Math.round(row.total) },
	{ key: 'creation', label: 'Créée le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifiée le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_COMMANDE_ACHAT_COLUMNS = COMMANDE_ACHAT_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function commandeAchatSortText(sort: Sort | null) {
	const column = sort && COMMANDE_ACHAT_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récentes'
}
