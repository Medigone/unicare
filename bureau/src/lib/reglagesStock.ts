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
	/** Par dépôt : articles avec un seuil, et ceux passés dessous. */
	resume: Record<string, { seuils: number; sous: number }>
	unites: string[]
	droits: { parametres: boolean; seuils: boolean; creer_depot: boolean; supprimer_depot: boolean }
	/** Dossiers (groupes) et dépôts actifs, chacun avec son dossier ; null sous la racine. */
	arbre: NoeudDepot[]
}

export interface NoeudDepot {
	name: string
	label: string
	parent: string | null
	dossier: boolean
	modified: string
}

/** L'arbre des dépôts à plat, dossiers d'abord, avec la profondeur et le nombre d'enfants de chaque dossier. */
export function arbreDepots(noeuds: NoeudDepot[]): (NoeudDepot & { niveau: number; enfants: number })[] {
	const connus = new Set(noeuds.map((n) => n.name))
	const parentDe = (n: NoeudDepot) => (n.parent && connus.has(n.parent) ? n.parent : null)
	const result: (NoeudDepot & { niveau: number; enfants: number })[] = []
	function parcourir(parent: string | null, niveau: number) {
		noeuds
			.filter((n) => parentDe(n) === parent)
			.sort((a, b) => Number(b.dossier) - Number(a.dossier) || a.label.localeCompare(b.label, 'fr'))
			.forEach((n) => {
				result.push({ ...n, niveau, enfants: noeuds.filter((e) => parentDe(e) === n.name).length })
				if (n.dossier) parcourir(n.name, niveau + 1)
			})
	}
	parcourir(null, 1)
	return result
}

export type SeuilVue = 'tous' | 'avec_seuil' | 'sous_seuil' | 'sans_seuil'

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
	{ key: 'sans_seuil', label: 'Sans seuil' },
]

/** Articles d'un dépôt passés sous leur seuil, à reprendre dans une commande d'achat. */
export interface ACommander {
	depot: string
	lignes: { article: string; designation: string; unite: string | null; stock: number; seuil: number; quantite: number; prix_tarif: number | null }[]
	/** Le fournisseur par défaut, quand tous ces articles ont le même. */
	fournisseur: { name: string; label: string } | null
}

/** État d'une ligne de seuil : ce qui manque pour revenir au seuil. */
export function etatSeuil(ligne: Pick<SeuilLigne, 'stock' | 'seuil'>): { label: string; tone: 'red' | 'green' | null } {
	if (!ligne.seuil) return { label: 'Sans seuil', tone: null }
	if (ligne.stock < ligne.seuil) return { label: `Manque ${formatQty(Math.round((ligne.seuil - ligne.stock) * 1000) / 1000)}`, tone: 'red' }
	return { label: 'OK', tone: 'green' }
}

/** Barre de stock : la part du stock et la place du trait du seuil, en %, sur une échelle un peu plus large que le plus grand des deux. */
export function jaugeSeuil(stock: number, seuil: number) {
	const echelle = Math.max(stock, seuil, 0.001) * 1.15
	return { stock: Math.max(0, Math.round((stock * 100) / echelle)), seuil: Math.round((seuil * 100) / echelle) }
}

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
