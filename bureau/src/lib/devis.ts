/** Règles de la page Devis : types, vues, colonnes, et saisie des lignes. */
import type { CommentPart } from '@shared/activity'
import { statusDisplay } from '@shared/status'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'
import type { Versions } from './versions'

export type DevisView = 'all' | 'brouillons' | 'ouverts' | 'expirent' | 'commandes' | 'clos'

export const DEVIS_VIEWS: { key: DevisView; label: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'brouillons', label: 'Brouillons' },
	{ key: 'ouverts', label: 'Ouverts' },
	{ key: 'expirent', label: 'Expirent sous 7 jours' },
	{ key: 'commandes', label: 'Commandés' },
	{ key: 'clos', label: 'Perdus, expirés ou annulés' },
]

/** Statut affiché en français, comme dans la pastille (règle commune de `@shared/status`). */
export const devisStatus = statusDisplay

export interface DevisRow {
	name: string
	modified: string
	creation: string
	client: string
	client_label: string
	date: string | null
	valable: string | null
	status: string
	total: number
	total_ttc: number
	lignes: number
	articles: string
	tags: string[]
	cloche: boolean
}

export interface DevisResponse extends ListResponse {
	devis: DevisRow[]
	counts: Record<DevisView, number>
	page_length: number
}

export interface DevisLine {
	name: string
	article: string
	designation: string
	description: string | null
	quantite: number
	unite: string | null
	prix: number
	prix_tarif: number
	remise: number
	montant: number
}

export type DevisAction = 'modifier' | 'valider' | 'supprimer' | 'commande' | 'perdu' | 'annuler' | 'nouvelle_version'

export interface DevisDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	status: string
	docstatus: number
	client: string
	client_label: string
	date: string | null
	valable: string | null
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
	/** null : la personne ne lit pas les commandes. */
	commandes: { name: string; status: string; date: string | null; livraison: string | null; total: number }[] | null
	/** La pièce annulée dont celle-ci est la nouvelle version. */
	version_de: string | null
	versions: Versions
	actions: DevisAction[]
	blocked: string[]
	raisons_perte: string[]
	perte: { raisons: string[]; precisions: string | null } | null
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface DevisOptions {
	filter_fields?: FilterField[]
	taxes: { value: string; label: string }[]
	taxes_defaut: string | null
	validite_jours: number
	liste_prix: string | null
}

export interface DevisArticleChoice {
	name: string
	label: string
	uom: string | null
	/** Prix du tarif de vente ; null : pas de prix au tarif. */
	prix: number | null
}

/** Une ligne en cours de saisie. Le prix reste du texte : vide, il reprend le tarif. */
export interface DraftLine {
	key: number
	article: string
	designation: string
	unite: string
	quantite: string
	prix: string
}

export const DEVIS_COLUMNS: Column<DevisRow>[] = [
	{ key: 'name', label: 'Devis', width: 150, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'client_label', label: 'Client', width: 200, minWidth: 120, grow: 1.5, sortable: true, text: (row) => row.client_label },
	{ key: 'status', label: 'Statut', width: 140, minWidth: 96, sortable: true, text: (row) => devisStatus(row.status) },
	{ key: 'date', label: 'Date', width: 92, minWidth: 80, sortable: true, text: (row) => formatDay(row.date) },
	{ key: 'valable', label: "Valable jusqu'au", width: 112, minWidth: 88, sortable: true, text: (row) => formatDay(row.valable) },
	{ key: 'total_ttc', label: 'Total TTC (DA)', width: 120, minWidth: 96, sortable: true, end: true, text: (row) => Math.round(row.total_ttc) },
	{ key: 'tags', label: 'Tags', width: 140, minWidth: 72, grow: 1, sortable: false, text: (row) => tagsText(row) },
	{ key: 'articles', label: 'Articles', width: 220, minWidth: 120, grow: 1, sortable: false, optional: true, text: (row) => row.articles },
	{ key: 'lignes', label: 'Lignes', width: 70, minWidth: 56, sortable: true, end: true, optional: true, text: (row) => row.lignes },
	{ key: 'total', label: 'Total HT (DA)', width: 120, minWidth: 96, sortable: true, end: true, optional: true, text: (row) => Math.round(row.total) },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_DEVIS_COLUMNS = DEVIS_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function devisSortText(sort: Sort | null) {
	const column = sort && DEVIS_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récents'
}

/** Date du jour décalée, au format AAAA-MM-JJ, dans le fuseau du navigateur. */
export function dayFromToday(days: number, from = new Date()) {
	const date = new Date(from.getFullYear(), from.getMonth(), from.getDate() + days)
	return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

/** Nombre saisi à la française (virgule, espaces) ; NaN si illisible. */
export function parseNumber(value: string) {
	const text = value.replace(/[\s ]/g, '').replace(',', '.')
	return text === '' ? NaN : Number(text)
}

/** Total HT de la saisie : une ligne sans prix compte le tarif s'il est connu, sinon zéro. */
export function draftTotal(lines: DraftLine[], tarifs: Record<string, number | null>) {
	return lines.reduce((total, line) => {
		const quantite = parseNumber(line.quantite)
		const prix = line.prix.trim() ? parseNumber(line.prix) : (tarifs[line.article] ?? 0)
		return total + (Number.isFinite(quantite) && Number.isFinite(prix) ? quantite * prix : 0)
	}, 0)
}

export interface DevisFormErrors {
	client?: string
	valable?: string
	lignes?: string
	/** Par clé de ligne. */
	ligne?: Record<number, string>
}

/** Mêmes refus que le serveur, dits avant l'envoi. `valable` est la date du devis, ou la livraison d'une commande. */
export function validateDevis(values: { client: string; valable: string; lignes: DraftLine[] }, today = dayFromToday(0), dateLabel = 'la date de validité') {
	const errors: DevisFormErrors = {}
	if (!values.client) errors.client = 'Choisissez le client.'
	if (!values.valable) errors.valable = `Choisissez ${dateLabel}.`
	else if (values.valable < today) errors.valable = `${dateLabel.charAt(0).toUpperCase()}${dateLabel.slice(1)} ne peut pas être passée.`
	const filled = values.lignes.filter((line) => line.article)
	if (!filled.length) errors.lignes = 'Ajoutez au moins une ligne.'
	const ligne: Record<number, string> = {}
	for (const line of filled) {
		const quantite = parseNumber(line.quantite)
		if (!(quantite > 0)) ligne[line.key] = 'Quantité positive attendue.'
		else if (line.prix.trim() && !(parseNumber(line.prix) >= 0)) ligne[line.key] = 'Prix illisible.'
	}
	if (Object.keys(ligne).length) errors.ligne = ligne
	return errors
}

/** Lignes envoyées au serveur : un prix vide part vide, le serveur reprend le tarif. */
export function linesForServer(lines: DraftLine[]) {
	return lines.filter((line) => line.article).map((line) => ({ article: line.article, quantite: parseNumber(line.quantite), prix: line.prix.trim() ? parseNumber(line.prix) : null }))
}
