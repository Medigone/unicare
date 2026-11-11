/** Réglages de la production : checklists avant production et paramètres (unicare/api/bureau_reglages_production.py). */

export interface ChecklistLigne {
	controle: string
	obligatoire: boolean
}

export interface ChecklistModele {
	name: string
	modified: string
	actif: boolean
	lignes: ChecklistLigne[]
	/** Ordres qui en ont reçu une copie : une checklist utilisée ne se supprime pas. */
	ordres: number
}

export type DepotField = 'warehouse_mp' | 'warehouse_conditionnement' | 'warehouse_atelier' | 'warehouse_pf' | 'warehouse_rebuts'

export interface ParametresProduction extends Record<DepotField, string | null> {
	modified: string
	tolerance: number
}

export interface ReglagesProduction {
	checklists: ChecklistModele[]
	parametres: ParametresProduction
	depots: string[]
	can_edit_checklists: boolean
	can_create_checklists: boolean
	can_edit_parametres: boolean
}

export const DEPOT_FIELDS: { key: DepotField; label: string; help?: string }[] = [
	{ key: 'warehouse_mp', label: 'Fûts (matières premières)' },
	{ key: 'warehouse_conditionnement', label: 'Articles de conditionnement' },
	{ key: 'warehouse_atelier', label: 'Atelier', help: 'Où les matières attendent pendant la production.' },
	{ key: 'warehouse_pf', label: 'Produits finis' },
	{ key: 'warehouse_rebuts', label: 'Rebuts' },
]

/** Déplace une ligne d'un cran (vers le haut : -1, vers le bas : +1) ; hors limites, rien ne bouge. */
export function moveLine<T>(lines: T[], index: number, offset: -1 | 1) {
	const target = index + offset
	if (target < 0 || target >= lines.length) return lines
	const copy = [...lines]
	;[copy[index], copy[target]] = [copy[target], copy[index]]
	return copy
}
