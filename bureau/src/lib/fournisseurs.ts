/** Règles de la page Fournisseurs : types, vues, colonnes, et validation de la fenêtre du fournisseur. */
import type { CommentPart } from '@shared/activity'
import type { FilterField } from './filters'
import { canRead } from './droits'
import { formatDay } from './display'
import { tagsText, type Column, type Sort } from './list'
import type { ClientContact, ClientEcriture } from './clients'
import type { ListResponse } from './useServerList'

export { formatAmount, normalizeName } from './clients'

export type FournisseurView = 'all' | 'actif' | 'exclu' | 'solde'

/** Le solde vient de la comptabilité : colonne et vue réservées à qui lit les écritures. */
export const SOLDE_DOCTYPE = 'GL Entry'

export const FOURNISSEUR_VIEWS: { key: FournisseurView; label: string; doctype?: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'actif', label: 'Actifs' },
	{ key: 'exclu', label: 'Exclus' },
	{ key: 'solde', label: 'À payer', doctype: SOLDE_DOCTYPE },
]

export interface FournisseurRow {
	name: string
	modified: string
	creation: string
	fournisseur: string
	status: string | null
	categorie: string | null
	wilaya: string | null
	contact: string | null
	telephone: string | null
	/** Ce que la société doit au fournisseur. null : la personne ne lit pas la comptabilité. */
	solde: number | null
	tags: string[]
	cloche: boolean
}

export interface FournisseursResponse extends ListResponse {
	fournisseurs: FournisseurRow[]
	counts: Record<FournisseurView, number>
	page_length: number
}

/** Une pièce d'achat : devis fournisseur, commande, réception ou facture. `reste` : le restant dû d'une facture. */
export interface FournisseurAchat {
	name: string
	date: string
	total: number
	status: string
	currency: string | null
	reste?: number
}
export type AchatKey = 'devis' | 'commandes' | 'receptions' | 'factures'

export interface FournisseurDetail {
	name: string
	modified: string
	tags: string[]
	fournisseur: string
	status: string | null
	categorie: string | null
	type: string | null
	pays: string | null
	commune: string | null
	commune_label: string | null
	wilaya: string | null
	adresse: string | null
	depuis: string
	telephone: string | null
	email: string | null
	solde: number | null
	pieces: { key: string; label: string; numero: string | null; fichier: string | null }[]
	contacts: ClientContact[]
	can_edit: boolean
	/** Droit de supprimer la fiche ; Frappe refuse encore si une pièce y est liée. */
	can_delete: boolean
	/** Fiche seulement. Une nature à `null` : la personne ne lit pas ce document. */
	achats?: Record<AchatKey, FournisseurAchat[] | null>
	/** Fiche seulement. `null` : la personne ne lit pas la comptabilité. */
	comptabilite?: { debit: number; credit: number; solde: number; ecritures: ClientEcriture[] } | null
	comments?: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface FournisseurOptions {
	filter_fields?: FilterField[]
	statuses: string[]
	categories: string[]
	wilayas: string[]
}

export const FOURNISSEUR_COLUMNS: Column<FournisseurRow>[] = [
	{ key: 'fournisseur', label: 'Fournisseur', width: 220, minWidth: 140, grow: 2, sortable: true, text: (row) => row.fournisseur },
	{ key: 'status', label: 'Statut', width: 104, minWidth: 96, sortable: true, text: (row) => row.status || '' },
	{ key: 'categorie', label: 'Catégorie', width: 140, minWidth: 72, grow: 0.6, sortable: true, text: (row) => row.categorie || '' },
	{ key: 'wilaya', label: 'Wilaya', width: 110, minWidth: 72, grow: 0.6, sortable: true, text: (row) => row.wilaya || '' },
	{ key: 'contact', label: 'Contact principal', width: 150, minWidth: 88, grow: 0.8, sortable: true, text: (row) => row.contact || '' },
	{ key: 'telephone', label: 'Téléphone', width: 120, minWidth: 88, sortable: true, text: (row) => row.telephone || '' },
	{ key: 'solde', label: 'À payer (DA)', width: 112, minWidth: 80, sortable: true, end: true, text: (row) => Math.round(row.solde ?? 0) },
	{ key: 'tags', label: 'Tags', width: 170, minWidth: 88, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'name', label: 'Code', width: 100, minWidth: 72, sortable: true, optional: true, text: (row) => row.name },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_FOURNISSEUR_COLUMNS = FOURNISSEUR_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function allowedFournisseurViews() {
	return FOURNISSEUR_VIEWS.filter((view) => canRead(view.doctype))
}
export function allowedFournisseurColumns() {
	return canRead(SOLDE_DOCTYPE) ? FOURNISSEUR_COLUMNS : FOURNISSEUR_COLUMNS.filter((column) => column.key !== 'solde')
}

export function fournisseurSortText(sort: Sort | null) {
	const column = sort && FOURNISSEUR_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : nom'
}

/** Fournisseur proposé pendant la saisie : doublon à la création, ou choix du fournisseur d'une pièce. */
export interface FournisseurChoice {
	name: string
	label: string
	wilaya: string | null
	disabled: number
}

export const FOURNISSEUR_FIELDS = ['supplier_name', 'status', 'categorie', 'commune', 'contact', 'fonction', 'contact_telephone', 'contact_email', 'rc', 'nif', 'nis', 'ai'] as const
export type FournisseurField = (typeof FOURNISSEUR_FIELDS)[number]
export type FournisseurValues = Partial<Record<FournisseurField, string>>
/** Ce qu'une modification peut changer : les contacts se modifient sur leur propre document. */
export const EDIT_FIELDS: readonly FournisseurField[] = ['supplier_name', 'status', 'categorie', 'commune', 'rc', 'nif', 'nis', 'ai']

const REQUIRED: { field: FournisseurField; message: string }[] = [
	{ field: 'supplier_name', message: 'Saisissez la raison sociale.' },
	{ field: 'categorie', message: 'Choisissez la catégorie.' },
]
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Mêmes refus que le serveur, dits avant l'envoi. `editing` : le statut devient obligatoire, le contact disparaît. */
export function validateFournisseur(values: FournisseurValues, editing = false) {
	const errors: Partial<Record<FournisseurField, string>> = {}
	const value = (field: FournisseurField) => values[field]?.trim() ?? ''
	for (const { field, message } of REQUIRED) if (!value(field)) errors[field] = message
	if (editing && !value('status')) errors.status = 'Choisissez le statut du fournisseur.'
	if (!editing && !value('contact') && (value('fonction') || value('contact_telephone') || value('contact_email'))) errors.contact = 'Saisissez le nom du contact.'
	if (value('contact_email') && !EMAIL.test(value('contact_email'))) errors.contact_email = 'Saisissez une adresse email valide.'
	return errors
}

export function fournisseurFormValues(fournisseur: FournisseurDetail): FournisseurValues {
	const number = (key: string) => fournisseur.pieces.find((piece) => piece.key === key)?.numero ?? ''
	return {
		supplier_name: fournisseur.fournisseur,
		status: fournisseur.status ?? '',
		categorie: fournisseur.categorie ?? '',
		commune: fournisseur.commune ?? '',
		rc: number('rc'),
		nif: number('nif'),
		nis: number('nis'),
		ai: number('ai'),
	}
}

/** Seuls les champs changés partent au serveur. */
export function changedFournisseurValues(initial: FournisseurValues, current: FournisseurValues) {
	const changes: FournisseurValues = {}
	for (const field of EDIT_FIELDS) {
		if ((current[field] ?? '').trim() !== (initial[field] ?? '').trim()) changes[field] = (current[field] ?? '').trim()
	}
	return changes
}
