/** Ce que partagent les pièces d'achat du bureau : articles d'achat proposés et options de saisie. */

/** Article d'achat proposé dans une fenêtre, avec son prix d'achat connu (tarif ou dernier achat). */
export interface AchatArticleChoice {
	name: string
	label: string
	uom: string | null
	/** null : aucun prix d'achat connu. */
	prix: number | null
	/** Prix de la liste seule, sans le dernier prix payé ; null : absent de la liste. */
	prix_liste?: number | null
	groupe?: string | null
	/** Stock de tous les dépôts ; null : article non stocké, ou stock non lisible pour ce rôle. */
	stock?: number | null
}

export interface AchatOptions {
	taxes: { value: string; label: string }[]
	taxes_defaut: string | null
	liste_prix: string | null
	listes_prix: string[]
}

/** Une ligne envoyée au serveur : un prix vide reprend le prix d'achat connu. */
export interface AchatLineValues {
	article: string
	quantite: number
	prix: number | null
}
