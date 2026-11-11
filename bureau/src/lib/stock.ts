/** Ce que partagent les écrans Stock : lignes du grand livre de stock et formats des quantités. */

/** Une ligne du grand livre de stock (Stock Ledger Entry), la plus récente d'abord. */
export interface LedgerRow {
	date: string | null
	heure: string | null
	piece_type: string
	piece: string
	/** Route de la fiche du bureau pour cette pièce ; null : elle s'ouvre sur le Desk. */
	fiche: string | null
	article: string
	designation: string
	depot: string
	/** Positive à l'entrée, négative à la sortie. */
	quantite: number
	/** Stock de l'article dans ce dépôt après le mouvement. */
	solde: number
	valeur: number
	unite: string | null
	lots: string[]
}

/** Nature d'une pièce du grand livre, en français. */
const PIECES: Record<string, string> = {
	'Purchase Receipt': 'Réception',
	'Delivery Note': 'Livraison',
	'Stock Entry': 'Mouvement',
	'Stock Reconciliation': 'Inventaire',
	'Sales Invoice': 'Facture',
	'Purchase Invoice': "Facture d'achat",
}
export function pieceLabel(doctype: string) {
	return PIECES[doctype] ?? doctype
}

/** Quantité signée : « +10 », « −2,5 ». */
export function signedQty(value: number) {
	const text = Math.abs(value).toLocaleString('fr-FR', { maximumFractionDigits: 3 }).replace(/ /g, ' ')
	return value > 0 ? `+${text}` : value < 0 ? `−${text}` : text
}
