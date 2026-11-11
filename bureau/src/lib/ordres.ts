/** Règles de la page Ordres de production : types, vues, colonnes, étapes et contrôle de la clôture. */
import type { CommentPart } from '@shared/activity'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'
import type { LotChoice } from './livraisons'

export type OrdreView = 'all' | 'en_cours' | 'a_planifier' | 'prets' | 'en_production' | 'en_retard' | 'termines' | 'annules'

/** La vue ouverte par défaut : ce qui reste à faire. */
export const DEFAULT_ORDRE_VIEW: OrdreView = 'en_cours'

export const ORDRE_VIEWS: { key: OrdreView; label: string }[] = [
	{ key: 'en_cours', label: 'En cours' },
	{ key: 'a_planifier', label: 'À planifier' },
	{ key: 'prets', label: 'Prêts à démarrer' },
	{ key: 'en_production', label: 'En production' },
	{ key: 'en_retard', label: 'En retard' },
	{ key: 'termines', label: 'Terminés' },
	{ key: 'annules', label: 'Annulés' },
	{ key: 'all', label: 'Tous' },
]

export type OrdreState = 'Brouillon' | 'Préparé' | 'En production' | 'Terminé' | 'Annulé'

export interface OrdreRow {
	name: string
	modified: string
	creation: string
	state: OrdreState
	/** Nom d'étape montré à l'utilisateur (« À planifier », « Prêt à démarrer »…). */
	etape: string
	produit: string
	designation: string
	recette: string | null
	date_prevue: string | null
	retard: boolean
	qty_prevue: number
	qty_reelle: number | null
	rendement: number | null
	unite: string | null
	lot_pf: string | null
	tags: string[]
	cloche: boolean
}

export interface OrdresResponse extends ListResponse {
	ordres: OrdreRow[]
	counts: Record<OrdreView, number>
	page_length: number
}

export interface OrdreMatiere {
	name: string
	article: string
	designation: string
	type: string | null
	avec_lot: boolean
	lot: string | null
	/** À planifier : les lots en stock au dépôt de départ, la péremption la plus proche d'abord. */
	lots: LotChoice[]
	depot: string | null
	prevu: number
	complement: number
	utilise: number
	unite: string | null
	/** À planifier : au dépôt de départ ; préparé ou en production : à l'atelier ; ensuite : null. */
	disponible: number | null
}

export interface OrdreControle {
	name: string
	controle: string
	obligatoire: boolean
	conforme: boolean
	par: string | null
	quand: string | null
	observation: string | null
}

export interface OrdreRebut {
	name: string
	article: string
	designation: string
	lot: string | null
	quantite: number
	unite: string | null
}

export interface OrdreComplement extends OrdreRebut {
	depot: string
	mouvement: string | null
	par: string
	quand: string
}

export interface OrdreEtape {
	key: 'planifier' | 'preparer' | 'produire' | 'cloturer'
	label: string
	statut: 'fait' | 'en_cours' | 'a_venir' | 'annule'
	quand: string | null
	duree: number | null
}

export type OrdreAction = 'preparer' | 'demarrer' | 'cloturer' | 'modifier' | 'controler' | 'saisir' | 'complement' | 'generer_lot' | 'dupliquer' | 'annuler' | 'supprimer'

export interface OrdreManque {
	texte: string
	/** Où corriger : `planning`, `matieres`, `checklist` ou le nom d'une ligne de matière. */
	cible: string | null
}

export interface OrdreDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	state: OrdreState
	etape: string
	produit: string
	designation: string
	produit_avec_lot: boolean
	recette: string | null
	modele_checklist: string | null
	date_prevue: string | null
	retard: boolean
	qty_prevue: number
	qty_reelle: number
	qty_rebut: number
	rendement: number
	rendement_vise: number
	tolerance: number
	unite: string | null
	lot_pf: string | null
	depots: { mp: string | null; conditionnement: string | null; atelier: string | null; pf: string | null; rebuts: string | null }
	etapes: OrdreEtape[]
	duree_totale: number
	matieres: OrdreMatiere[]
	checklist: OrdreControle[]
	rebuts: OrdreRebut[]
	complements: OrdreComplement[]
	mouvements: { name: string; role: string; label: string; date: string | null }[]
	tracabilite: { article: string; designation: string; lot: string; lot_fournisseur: string | null }[]
	manques: OrdreManque[]
	actions: OrdreAction[]
	cree_par: string
	can_print: boolean
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface OrdreOptions {
	filter_fields?: FilterField[]
	produits: { value: string; label: string }[]
	recettes: { value: string; produit: string; label: string }[]
	checklists: string[]
	depots: string[]
}

export interface Besoin {
	article: string
	designation: string
	type: string | null
	quantite: number
	unite: string | null
	depot: string
	disponible: number
	avec_lot: boolean
}

export interface OrdreValues {
	recette?: string
	quantite?: number
	date_prevue?: string
	checklist?: string
	lignes?: { name: string; quantite?: number; depot?: string; lot?: string | null }[]
	ajouts?: { article: string; quantite: number; depot?: string; lot?: string }[]
	retirer?: string[]
}

/** Teinte de la pastille d'étape : même sens que le reste du bureau. */
export const ETAPE_TONES: Record<OrdreState, 'gray' | 'blue' | 'amber' | 'green' | 'red'> = {
	Brouillon: 'gray',
	Préparé: 'blue',
	'En production': 'amber',
	Terminé: 'green',
	Annulé: 'red',
}

export const ORDRE_COLUMNS: Column<OrdreRow>[] = [
	{ key: 'name', label: 'Ordre', width: 140, minWidth: 110, sortable: true, text: (row) => row.name },
	{ key: 'designation', label: 'Produit', width: 220, minWidth: 120, grow: 1, sortable: true, text: (row) => row.designation },
	{ key: 'etape', label: 'Étape', width: 140, minWidth: 100, sortable: true, text: (row) => row.etape },
	{ key: 'date_prevue', label: 'Prévu pour', width: 150, minWidth: 90, sortable: true, text: (row) => formatDay(row.date_prevue) },
	{ key: 'qty_prevue', label: 'Prévu', width: 100, minWidth: 72, sortable: true, end: true, text: (row) => row.qty_prevue },
	{ key: 'qty_reelle', label: 'Produit', width: 100, minWidth: 72, sortable: true, end: true, text: (row) => row.qty_reelle ?? '' },
	{ key: 'rendement', label: 'Rendement', width: 120, minWidth: 90, sortable: true, text: (row) => (row.rendement === null ? '' : `${row.rendement} %`) },
	{ key: 'lot_pf', label: 'Lot produit fini', width: 190, minWidth: 110, sortable: true, text: (row) => row.lot_pf ?? '' },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, optional: true, text: (row) => tagsText(row) },
	{ key: 'creation', label: 'Créé le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.creation) },
	{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_ORDRE_COLUMNS = ORDRE_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function ordreSortText(sort: Sort | null) {
	const column = sort && ORDRE_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : plus récents'
}

/** Nombre saisi à la française ; NaN si illisible. */
export function parseQty(value: string | number) {
	const text = String(value).replace(/[\s ]/g, '').replace(',', '.')
	return text === '' ? NaN : Number(text)
}

/** Retard ou échéance d'un ordre, en clair. */
export function echeanceText(date: string | null, retard: boolean, today = new Date()) {
	if (!date) return '—'
	const day = new Date(`${date}T00:00:00`)
	const start = new Date(today.getFullYear(), today.getMonth(), today.getDate())
	const diff = Math.round((day.getTime() - start.getTime()) / 86_400_000)
	const label = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' }).format(day)
	if (retard && diff < 0) return `${label} · en retard de ${-diff} j`
	if (diff === 0) return `${label} · aujourd'hui`
	if (diff === 1) return `${label} · demain`
	return label
}

/** Durée en minutes, lisible : « 35 min », « 2 h 12 », « 3 j 4 h ». */
export function dureeText(minutes?: number | null) {
	if (!minutes) return '—'
	if (minutes < 60) return `${minutes} min`
	const hours = Math.floor(minutes / 60)
	if (hours < 48) return `${hours} h ${String(minutes % 60).padStart(2, '0')}`
	return `${Math.floor(hours / 24)} j ${hours % 24} h`
}

export interface ClotureLigne {
	name: string
	designation: string
	utilise: number
	rebut: number
	/** Préparé plus compléments : ce qui est arrivé à l'atelier. */
	atelier: number
	ok: boolean
	reste: number
}

/** Contrôle de la clôture : pour chaque matière, utilisé + rebut ne dépasse pas ce qui est arrivé à l'atelier. */
export function clotureLignes(ordre: Pick<OrdreDetail, 'matieres' | 'rebuts'>, utilises: Record<string, string>): ClotureLigne[] {
	return ordre.matieres.map((line) => {
		const utilise = parseQty(utilises[line.name] ?? line.utilise)
		const rebut = ordre.rebuts.filter((row) => row.article === line.article && (row.lot ?? null) === (line.lot ?? null)).reduce((sum, row) => sum + row.quantite, 0)
		const atelier = line.prevu + line.complement
		const reste = Math.round((atelier - (Number.isFinite(utilise) ? utilise : 0) - rebut) * 1000) / 1000
		return { name: line.name, designation: line.designation, utilise, rebut, atelier, ok: Number.isFinite(utilise) && utilise >= 0 && reste >= -0.0001, reste }
	})
}

/** Rendement de la clôture et son écart à l'objectif de la recette. */
export function rendementCloture(produit: number, ordre: Pick<OrdreDetail, 'qty_prevue' | 'rendement_vise' | 'tolerance'>) {
	const rendement = ordre.qty_prevue > 0 && Number.isFinite(produit) ? Math.round((produit / ordre.qty_prevue) * 1000) / 10 : 0
	return { rendement, horsTolerance: Math.abs(rendement - ordre.rendement_vise) > ordre.tolerance }
}
