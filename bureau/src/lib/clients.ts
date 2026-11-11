/** Règles de la page Clients : types, vues, colonnes, et validation de la fenêtre du client. */
import type { CommentPart } from '@shared/activity'
import type { FilterField } from './filters'
import { canRead } from './droits'
import { formatDay } from './display'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'

export type ClientView = 'all' | 'actif' | 'dormant' | 'perdu' | 'solde'

/** Le solde vient de la comptabilité : colonne et vue réservées à qui lit les écritures. */
export const SOLDE_DOCTYPE = 'GL Entry'

export const CLIENT_VIEWS: { key: ClientView; label: string; doctype?: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'actif', label: 'Actifs' },
	{ key: 'dormant', label: 'Dormants' },
	{ key: 'perdu', label: 'Perdus ou exclus' },
	{ key: 'solde', label: 'Avec solde', doctype: SOLDE_DOCTYPE },
]

export interface ClientRow {
	name: string
	modified: string
	creation: string
	client: string
	status: string | null
	categorie: string | null
	wilaya: string | null
	contact: string | null
	telephone: string | null
	/** null : la personne ne lit pas la comptabilité. */
	solde: number | null
	tags: string[]
	cloche: boolean
}

export interface ClientsResponse extends ListResponse {
	clients: ClientRow[]
	counts: Record<ClientView, number>
	page_length: number
}

export interface ClientContact {
	nom: string | null
	fonction: string | null
	telephone: string | null
	email: string | null
	principal: number
}

/** Une pièce de vente : devis, commande, livraison ou facture. `reste` : le restant dû d'une facture. */
export interface ClientVente {
	name: string
	date: string
	total: number
	status: string
	currency: string | null
	reste?: number
}
export type VenteKey = 'devis' | 'commandes' | 'livraisons' | 'factures'

export interface ClientEcriture {
	voucher_type: string
	voucher_no: string
	date: string
	debit: number
	credit: number
}

export interface ClientDetail {
	name: string
	modified: string
	tags: string[]
	client: string
	status: string | null
	forme_juridique: string | null
	categorie: string | null
	/** Identifiant de la commune ; `commune_label` est son nom. */
	commune: string | null
	commune_label: string | null
	wilaya: string | null
	region: string | null
	adresse: string | null
	gps: string | null
	map_url: string | null
	/** Date de création de la fiche, AAAA-MM-JJ. */
	depuis: string
	contact: string | null
	telephone: string | null
	email: string | null
	solde: number | null
	pieces: { key: string; label: string; numero: string | null; fichier: string | null }[]
	contacts: ClientContact[]
	can_edit: boolean
	/** Droit de supprimer la fiche ; Frappe refuse encore si une pièce y est liée. */
	can_delete: boolean
	/** Fiche seulement. Une nature à `null` : la personne ne lit pas ce document. */
	ventes?: Record<VenteKey, ClientVente[] | null>
	/** Fiche seulement. `null` : la personne ne lit pas la comptabilité. */
	comptabilite?: { debit: number; credit: number; solde: number; ecritures: ClientEcriture[] } | null
	comments?: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface ClientOptions {
	filter_fields?: FilterField[]
	statuses: string[]
	formes: string[]
	categories: string[]
	wilayas: string[]
}

/** Montant en dinars, avec une espace insécable pour les milliers : « 1 240 000 ». */
export function formatAmount(value?: number | null) {
	return Math.round(value ?? 0)
		.toString()
		.replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0')
}

export const CLIENT_COLUMNS: Column<ClientRow>[] = [
	{ key: 'client', label: 'Client', width: 220, minWidth: 140, grow: 2, sortable: true, text: (row) => row.client },
	{ key: 'status', label: 'Statut', width: 104, minWidth: 96, sortable: true, text: (row) => row.status || '' },
	{ key: 'categorie', label: 'Catégorie', width: 120, minWidth: 72, grow: 0.6, sortable: true, text: (row) => row.categorie || '' },
	{ key: 'wilaya', label: 'Wilaya', width: 110, minWidth: 72, grow: 0.6, sortable: true, text: (row) => row.wilaya || '' },
	{ key: 'contact', label: 'Contact principal', width: 150, minWidth: 88, grow: 0.8, sortable: true, text: (row) => row.contact || '' },
	{ key: 'telephone', label: 'Téléphone', width: 120, minWidth: 88, sortable: true, text: (row) => row.telephone || '' },
	{ key: 'solde', label: 'Solde (DA)', width: 112, minWidth: 80, sortable: true, end: true, text: (row) => Math.round(row.solde ?? 0) },
	{ key: 'tags', label: 'Tags', width: 170, minWidth: 88, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'name', label: 'Code', width: 100, minWidth: 72, sortable: true, optional: true, text: (row) => row.name },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_CLIENT_COLUMNS = CLIENT_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

/** Le solde n'apparaît que pour un rôle qui lit la comptabilité. */
export function allowedClientViews() {
	return CLIENT_VIEWS.filter((view) => canRead(view.doctype))
}
export function allowedClientColumns() {
	return canRead(SOLDE_DOCTYPE) ? CLIENT_COLUMNS : CLIENT_COLUMNS.filter((column) => column.key !== 'solde')
}

export function clientSortText(sort: Sort | null) {
	const column = sort && CLIENT_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : nom'
}

/** Client proposé pendant la saisie de la raison sociale, pour repérer un doublon. */
export interface ClientChoice {
	name: string
	label: string
	wilaya: string | null
	disabled: number
}

export interface CommuneChoice {
	name: string
	commune: string | null
	wilaya: string | null
}

/** Champs de la fenêtre. Le contact (nom, fonction, téléphone, email) ne sert qu'à la création : il devient un document Contact. */
export const CLIENT_FIELDS = ['customer_name', 'status', 'forme_juridique', 'categorie', 'commune', 'gps', 'telephone', 'email', 'contact', 'fonction', 'contact_telephone', 'contact_email', 'rc', 'nif', 'nis', 'ai'] as const
export type ClientField = (typeof CLIENT_FIELDS)[number]
export type ClientValues = Partial<Record<ClientField, string>>
/** Ce qu'une modification peut changer : le contact principal se modifie sur son propre document. */
export const EDIT_FIELDS: readonly ClientField[] = ['customer_name', 'status', 'forme_juridique', 'categorie', 'commune', 'gps', 'telephone', 'email', 'rc', 'nif', 'nis', 'ai']

const REQUIRED: { field: ClientField; message: string }[] = [
	{ field: 'customer_name', message: 'Saisissez la raison sociale.' },
	{ field: 'forme_juridique', message: 'Choisissez la forme juridique.' },
	{ field: 'categorie', message: 'Choisissez la catégorie.' },
	{ field: 'commune', message: 'Choisissez la commune.' },
]
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const GPS = /^\s*-?\d{1,2}(\.\d+)?\s*[,;]\s*-?\d{1,3}(\.\d+)?\s*$/

/** Mêmes refus que le serveur, dits avant l'envoi. `editing` : le statut devient obligatoire, le contact disparaît. */
export function validateClient(values: ClientValues, editing = false) {
	const errors: Partial<Record<ClientField, string>> = {}
	const value = (field: ClientField) => values[field]?.trim() ?? ''
	for (const { field, message } of REQUIRED) if (!value(field)) errors[field] = message
	if (editing && !value('status')) errors.status = 'Choisissez le statut du client.'
	if (!editing && !value('contact') && (value('fonction') || value('contact_telephone') || value('contact_email'))) errors.contact = 'Saisissez le nom du contact.'
	for (const field of ['email', 'contact_email'] as const) if (value(field) && !EMAIL.test(value(field))) errors[field] = 'Saisissez une adresse email valide.'
	if (value('gps')) {
		const [lat, lon] = value('gps').split(/[,;]/).map(Number)
		if (!GPS.test(value('gps')) || Math.abs(lat) > 90 || Math.abs(lon) > 180) errors.gps = 'Saisissez « latitude, longitude », par exemple 36.75, 3.06.'
	}
	return errors
}

/** Valeurs de la fenêtre pour un client existant. */
export function clientFormValues(client: ClientDetail): ClientValues {
	const number = (key: string) => client.pieces.find((piece) => piece.key === key)?.numero ?? ''
	return {
		customer_name: client.client,
		status: client.status ?? '',
		forme_juridique: client.forme_juridique ?? '',
		categorie: client.categorie ?? '',
		commune: client.commune ?? '',
		gps: client.gps ?? '',
		telephone: client.telephone ?? '',
		email: client.email ?? '',
		rc: number('rc'),
		nif: number('nif'),
		nis: number('nis'),
		ai: number('ai'),
	}
}

/** Seuls les champs changés partent au serveur : une fiche ouverte ne réécrit pas ce qu'elle n'a pas touché. */
export function changedValues(initial: ClientValues, current: ClientValues) {
	const changes: ClientValues = {}
	for (const field of EDIT_FIELDS) {
		if ((current[field] ?? '').trim() !== (initial[field] ?? '').trim()) changes[field] = (current[field] ?? '').trim()
	}
	return changes
}

/** Recherche sans accents ni casse, pour repérer un doublon pendant la saisie. */
export function normalizeName(value: string) {
	return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim()
}
