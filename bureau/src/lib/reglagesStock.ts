/** Réglages › Stock et seuils : paramètres de stock et seuils de réapprovisionnement (unicare/api/bureau_reglages_stock.py). */
import { formatQty } from './articles'
import { parseQty } from './ordres'

export interface ParametresStock {
	modified: string
	default_warehouse: string | null
	stock_uom: string | null
	allow_negative_stock: boolean
	auto_indent: boolean
	valuation_method: string | null
}

export interface ReglagesStock {
	parametres: ParametresStock
	depots: string[]
	unites: string[]
	droits: { parametres: boolean; seuils: boolean }
}

export type SeuilVue = 'tous' | 'avec_seuil' | 'sous_seuil'

export interface SeuilLigne {
	article: string
	designation: string
	unite: string | null
	stock: number
	seuil: number | null
	quantite: number | null
	modified: string
}

export interface SeuilsResponse {
	depot: string
	lignes: SeuilLigne[]
	total: number
	compte: Record<SeuilVue, number>
	start: number
	page: number
}

export const SEUIL_VUES: { key: SeuilVue; label: string }[] = [
	{ key: 'tous', label: 'Tous' },
	{ key: 'avec_seuil', label: 'Avec seuil' },
	{ key: 'sous_seuil', label: 'Sous le seuil' },
]

export const VALORISATION: Record<string, string> = { FIFO: 'Premier entré, premier sorti (FIFO)', 'Moving Average': 'Coût moyen pondéré', LIFO: 'Dernier entré, premier sorti (LIFO)' }

export interface SeuilDraft {
	seuil: string
	quantite: string
}

export function seuilDraft(ligne: Pick<SeuilLigne, 'seuil' | 'quantite'>): SeuilDraft {
	return { seuil: ligne.seuil ? formatQty(ligne.seuil) : '', quantite: ligne.quantite ? formatQty(ligne.quantite) : '' }
}

/** Vérifie la saisie : une erreur lisible, ou null si elle est enregistrable. */
export function seuilErreur(draft: SeuilDraft): string | null {
	for (const [valeur, label, e] of [
		[draft.seuil, 'Le seuil', 'négatif'],
		[draft.quantite, 'La quantité à commander', 'négative'],
	] as const) {
		if (!valeur.trim()) continue
		const n = parseQty(valeur)
		if (Number.isNaN(n)) return `${label} est illisible.`
		if (n < 0) return `${label} ne peut pas être ${e}.`
	}
	return null
}

/** La saisie diffère-t-elle de ce qui est enregistré ? */
export function seuilChange(draft: SeuilDraft, ligne: Pick<SeuilLigne, 'seuil' | 'quantite'>): boolean {
	const num = (text: string) => (text.trim() ? parseQty(text) : 0)
	return num(draft.seuil) !== (ligne.seuil ?? 0) || (num(draft.seuil) > 0 && num(draft.quantite) !== (ligne.quantite ?? 0) && draft.quantite.trim() !== '')
}
