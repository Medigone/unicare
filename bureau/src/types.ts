/** Types communs aux listes du poste de bureau. */

/** Résultat d'une action groupée : chaque ligne est traitée à part. */
export interface BulkResult {
	done: string[]
	skipped: { name: string; reason: string }[]
}

/** Champ modifiable sur plusieurs lignes, décrit par la métadonnée du DocType. */
export interface BulkField {
	fieldname: string
	label: string
	fieldtype: string
	options: string[]
	required: boolean
}

export interface BulkOptions {
	fields: BulkField[]
	can_delete: boolean
}

/** Ce que le serveur attend de chaque ligne : son nom et la version affichée à l'écran. */
export interface BulkItem {
	name: string
	modified: string
}

export interface Option {
	value: string
	label: string
}
