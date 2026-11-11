/** Ce que partagent les pièces d'achat du bureau : articles d'achat proposés et options de saisie. */

/** Article d'achat proposé dans une fenêtre, avec son prix d'achat connu (tarif ou dernier achat). */
export interface AchatArticleChoice {
	name: string
	label: string
	uom: string | null
	/** null : aucun prix d'achat connu. */
	prix: number | null
}

export interface AchatOptions {
	taxes: { value: string; label: string }[]
	taxes_defaut: string | null
	liste_prix: string | null
}

/** Une ligne envoyée au serveur : un prix vide reprend le prix d'achat connu. */
export interface AchatLineValues {
	article: string
	quantite: number
	prix: number | null
}
