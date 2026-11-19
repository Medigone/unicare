/** Réglages › Aide : la liste des articles, ses vues et ses colonnes. */
import { formatDay } from './display'
import type { FilterField } from './filters'
import { tagsText, type Column, type Sort } from './list'
import type { ListResponse } from './useServerList'

export type AideListeVue = 'all' | 'publies' | 'brouillons' | 'bureau'

export const AIDE_LISTE_VUES: { key: AideListeVue; label: string }[] = [
	{ key: 'all', label: 'Tous' },
	{ key: 'publies', label: 'Publiés' },
	{ key: 'brouillons', label: 'Brouillons' },
	{ key: 'bureau', label: 'Écrits dans le bureau' },
]

export interface AideLigne {
	name: string
	modified: string
	creation: string
	tags: string[]
	cloche: boolean
	titre: string
	resume: string
	categorie: string
	rubrique: string
	statut: 'Publié' | 'Brouillon'
	ecrans: string[]
	source: string
	date_revision: string | null
	duree_lecture: number | null
}

export interface AideListeResponse extends ListResponse {
	articles: AideLigne[]
	counts: Record<AideListeVue, number>
	page_length: number
}

export interface AideListeOptions {
	filter_fields?: FilterField[]
}

/** Le nom d'un écran du bureau, fourni par la page (il dépend du poste). */
export type NomEcran = (id: string) => string

export function aideColonnes(nomEcran: NomEcran): Column<AideLigne>[] {
	return [
		{ key: 'titre', label: 'Article', width: 300, minWidth: 180, grow: 3, sortable: true, text: (row) => row.titre },
		{ key: 'rubrique', label: 'Rubrique', width: 130, minWidth: 90, sortable: true, text: (row) => row.rubrique },
		{ key: 'statut', label: 'Statut', width: 96, minWidth: 80, sortable: true, text: (row) => row.statut },
		{ key: 'ecrans', label: 'Proposé dans', width: 220, minWidth: 110, grow: 1, sortable: true, text: (row) => row.ecrans.map(nomEcran).join(', ') },
		{ key: 'resume', label: 'Résumé', width: 320, minWidth: 140, grow: 2, sortable: false, optional: true, text: (row) => row.resume },
		{ key: 'source', label: 'Origine', width: 180, minWidth: 90, sortable: true, optional: true, text: (row) => row.source || 'Bureau' },
		{ key: 'date_revision', label: 'Revu le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.date_revision) },
		{ key: 'duree_lecture', label: 'Lecture', width: 80, minWidth: 64, sortable: true, optional: true, end: true, text: (row) => row.duree_lecture ?? '' },
		{ key: 'tags', label: 'Tags', width: 150, minWidth: 72, grow: 1, sortable: false, optional: true, text: (row) => tagsText(row) },
		{ key: 'name', label: 'Adresse', width: 200, minWidth: 96, sortable: true, optional: true, text: (row) => row.name },
		{ key: 'modified', label: 'Modifié le', width: 92, minWidth: 80, sortable: true, optional: true, text: (row) => formatDay(row.modified) },
	]
}
export const AIDE_COLONNES_DEFAUT = ['titre', 'rubrique', 'statut', 'ecrans']

export function aideTriTexte(sort: Sort | null) {
	const column = sort && aideColonnes((id) => id).find((item) => item.key === sort.key)
	return column ? `Tri : ${column.label.toLowerCase()}` : "Tri : ordre de l'aide"
}
