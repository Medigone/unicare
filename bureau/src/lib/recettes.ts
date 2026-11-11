/** Règles de la page Recettes : types, vues, colonnes, saisie des matières et calcul des besoins. */
import type { CommentPart } from '@shared/activity'
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { OrdreState } from './ordres'
import type { ListResponse } from './useServerList'

export type RecetteView = 'all' | 'actives' | 'inactives'
export const DEFAULT_RECETTE_VIEW: RecetteView = 'actives'

export const RECETTE_VIEWS: { key: RecetteView; label: string }[] = [
	{ key: 'actives', label: 'Actives' },
	{ key: 'inactives', label: 'Inactives' },
	{ key: 'all', label: 'Toutes' },
]

export interface RecetteRow {
	name: string
	modified: string
	creation: string
	produit: string
	designation: string
	actif: boolean
	quantite_base: number
	unite: string | null
	rendement: number
	matieres: number
	ordres: number
	tags: string[]
	cloche: boolean
}

export interface RecettesResponse extends ListResponse {
	recettes: RecetteRow[]
	counts: Record<RecetteView, number>
	page_length: number
}

export interface RecetteIngredient {
	name: string
	article: string
	designation: string
	type: string
	quantite: number
	unite: string | null
	obligatoire: boolean
}

export type RecetteAction = 'modifier' | 'activer' | 'desactiver' | 'dupliquer' | 'nouvel_ordre' | 'supprimer'

export interface RecetteDetail {
	name: string
	modified: string
	creation: string
	tags: string[]
	produit: string
	designation: string
	actif: boolean
	quantite_base: number
	unite: string | null
	rendement: number
	rendement_moyen: number | null
	ordres_termines: number
	ingredients: RecetteIngredient[]
	ordres: { name: string; state: OrdreState; etape: string; date_prevue: string | null; qty_prevue: number; qty_reelle: number | null; rendement: number | null }[]
	nb_ordres: number
	actions: RecetteAction[]
	cree_par: string
	comments: { count: number; last: { who: string; at: string; parts: CommentPart[] } | null }
}

export interface RecetteChoice {
	value: string
	label: string
	type: string
	unite: string | null
}

export interface RecetteOptions {
	filter_fields?: FilterField[]
	produits: RecetteChoice[]
	matieres: RecetteChoice[]
	unites: string[]
}

export interface RecetteValues {
	produit: string
	quantite_base: number
	unite?: string
	rendement: number
	ingredients: { article: string; quantite: number; unite?: string; obligatoire: boolean }[]
}

export const RECETTE_COLUMNS: Column<RecetteRow>[] = [
	{ key: 'designation', label: 'Produit', width: 240, minWidth: 140, grow: 1, sortable: true, text: (row) => row.designation },
	{ key: 'name', label: 'Recette', width: 190, minWidth: 120, sortable: true, text: (row) => row.name },
	{ key: 'actif', label: 'État', width: 100, minWidth: 80, sortable: false, text: (row) => (row.actif ? 'Active' : 'Inactive') },
	{ key: 'base', label: 'Pour', width: 110, minWidth: 80, sortable: false, end: true, text: (row) => `${row.quantite_base} ${row.unite ?? ''}` },
	{ key: 'matieres', label: 'Matières', width: 90, minWidth: 70, sortable: true, end: true, text: (row) => row.matieres },
	{ key: 'rendement', label: 'Rendement visé', width: 130, minWidth: 90, sortable: true, end: true, text: (row) => `${row.rendement} %` },
	{ key: 'ordres', label: 'Ordres', width: 90, minWidth: 70, sortable: true, end: true, text: (row) => row.ordres },
	{ key: 'tags', label: 'Tags', width: 130, minWidth: 72, grow: 1, sortable: false, optional: true, text: (row) => tagsText(row) },
	{ key: 'modified', label: 'Modifiée le', width: 100, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
]
export const DEFAULT_RECETTE_COLUMNS = RECETTE_COLUMNS.filter((column) => !column.optional).map((column) => column.key)

export function recetteSortText(sort: Sort | null) {
	const column = sort && RECETTE_COLUMNS.find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : 'Tri : produit'
}

/** Ce qu'il faut de chaque matière pour une quantité de produit, d'après la quantité de base de la recette. */
export function besoinsPour(recette: Pick<RecetteDetail, 'quantite_base' | 'ingredients'>, quantite: number) {
	const factor = recette.quantite_base > 0 && quantite > 0 ? quantite / recette.quantite_base : 0
	return recette.ingredients.map((row) => ({ designation: row.designation, unite: row.unite, quantite: Math.round(row.quantite * factor * 1000) / 1000 }))
}

/** Une ligne de la fenêtre : au moins un fût, des quantités positives, pas deux fois la même matière. */
export function recetteErrors(values: { produit: string; quantite_base: number; rendement: number; ingredients: { article: string; quantite: number; type?: string }[] }) {
	const errors: string[] = []
	if (!values.produit) errors.push('Choisissez le produit fini.')
	if (!(values.quantite_base > 0)) errors.push('La quantité de base doit être supérieure à zéro.')
	if (!(values.rendement > 0 && values.rendement <= 100)) errors.push('Le rendement visé est un pourcentage entre 1 et 100.')
	const lignes = values.ingredients.filter((row) => row.article)
	if (!lignes.length) errors.push('Ajoutez au moins une matière.')
	else if (!lignes.some((row) => row.type === 'Fût')) errors.push('Il faut au moins une matière de type Fût (le vrac).')
	if (lignes.some((row) => !(row.quantite > 0))) errors.push('Chaque matière doit avoir une quantité supérieure à zéro.')
	if (new Set(lignes.map((row) => row.article)).size < lignes.length) errors.push('Une matière figure deux fois : regroupez les quantités.')
	return errors
}
