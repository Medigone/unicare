/** Règles de la page Devis fournisseur : types, vues et colonnes. La saisie des lignes est celle des devis client. */
import type { CommentPart } from '@shared/activity'
import { statusDisplay } from '@shared/status'
import type { AchatOptions } from './achats'
import type { DevisLine } from './devis'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'
import type { Versions } from './versions'

export type DevisFournisseurView = 'all' | 'brouillons' | 'ouverts' | 'expirent' | 'commandes' | 'clos'

export const DEVIS_FOURNISSEUR_VIEWS: { key: DevisFournisseurView; label: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'brouillons', label: 'Brouillons' },
	{ key: 'ouverts', label: 'Ouverts' },
	{ key: 'expirent', label: 'Expirent sous 7 jours' },
	{ key: 'commandes', label: 'Commandés' },
	{ key: 'clos', label: 'Arrêtés, expirés ou annulés' },
]

export const devisFournisseurStatus = statusDisplay

export interface DevisFournisseurRow {
	name: string
	modified: string
	creation: string
	fournisseur: string
	fournisseur_label: string
	date: string | null
	valable: string | null
	reference: string | null
	status: string
	/** Repris par au moins une commande d'achat. */
	commande: boolean
	total: number
	total_ttc: number
	lignes: number
	articles: string
	tags: string[]
	cloche: boolean
}

export interface DevisFournisseurResponse extends ListResponse {
	devis: DevisFournisseurRow[]
	counts: Record<DevisFournisseurView, number>
	page_length: number
}

export type DevisFournisseurAction = 'modifier' | 'valider' | 'supprimer' | 'commande' | 'annuler' | 'nouvelle_version'

export interface DevisFournisseurDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	status: string
	docstatus: number
	fournisseur: string
	fournisseur_label: string
	date: string | null
	valable: string | null
	reference: string | null
	cree_par: string
	devise: string
	taxes_modele: string | null
	lignes: DevisLine[]
	/** Une ligne « TVA », et le droit de timbre à part s'il y en a un. */
	taxes: { description: string; montant: number }[]
	total: number
	total_taxes: number
	total_ttc: number
	arrondi: number | null
	en_lettres: string | null
	/** null : la personne ne lit pas les commandes d'achat. */
	commandes: { name: string; status: string; date: string | null; reception: string | null; total: number }[] | null
	/** La pièce annulée dont celle-ci est la nouvelle version. */
	version_de: string | null
	versions: Versions
	actions: DevisFournisseurAction[]
	blocked: string[]
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface DevisFournisseurOptions extends AchatOptions {
	filter_fields?: FilterField[]
	validite_jours: number
}

export const DEVIS_FOURNISSEUR_COLUMNS: Column<DevisFournisseurRow>[] = [
	{ key: 'name', label: 'Devis', width: 150, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'fournisseur_label', label: 'Fournisseur', width: 200, minWidth: 120, grow: 1.5, sortable: true, text: (row) => row.fournisseur_label },
	{ key: 'status', label: 'Statut', width: 140, minWidth: 96, sortable: true, text: (row) => devisFournisseurStatus(row.status) },
	{ key: 'date', label: 'Date', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.date) },
	{ key: 'valable', label: "Valable jusqu'au", width: 112, minWidth: 88, sortable: true, text: (row) => formatDay(row.valable) },
	{ key: 'reference', label: 'Réf. fournisseur', width: 130, minWidth: 88, sortable: true, text: (row) => row.reference || '' },
	{ key: 'total_ttc', label: 'Total TTC (DA)', width: 120, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.total_ttc) },
	{ key: 'tags', label: 'Tags', width: 140, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'articles', label: 'Articles', width: 220, minWidth: 120, grow: 1, sortable: false, optional: true, text: (row) => row.articles },
	{ key: 'lignes', label: 'Lignes', width: 70, minWidth: 56, sortable: true, end: true, optional: true, text: (row) => row.lignes },
	{ key: 'total', label: 'Total HT (DA)', width: 120, minWidth: 96, sortable: true, end: true, optional: true, text: (row) => Math.round(row.total) },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_DEVIS_FOURNISSEUR_COLUMNS = DEVIS_FOURNISSEUR_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function devisFournisseurSortText(sort: Sort | null) {
	const column = sort && DEVIS_FOURNISSEUR_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récents'
}
