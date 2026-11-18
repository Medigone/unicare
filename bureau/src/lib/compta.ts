/** Réglages › Comptabilité : bilan, comptes par défaut, TVA, modes de paiement, exercices, timbre (unicare/api/bureau_compta.py). */

export type BilanEtat = 'ok' | 'attention' | 'manque'
export type TvaSens = 'vente' | 'achat'
export type ModeType = 'Cash' | 'Bank' | 'General'

export interface BilanPoint {
	code: string
	label: string
	etat: BilanEtat
	detail: string
	/** Section de la page où se règle ce point (`tarifs` : la page Tarifs et prix). */
	ancre: string
}

export interface CompteChamp {
	field: string
	label: string
	aide: string | null
	requis: boolean
	valeur: string | null
}

export interface TauxTva {
	name: string
	titre: string
	taux: number
	compte: string | null
	defaut: boolean
	actif: boolean
	modified: string
}

export interface ModePaiement {
	name: string
	type: ModeType
	actif: boolean
	compte: string | null
	/** Compte pris quand le mode n'en a pas : la banque ou la caisse par défaut de la société. */
	repli: string | null
	modified: string
}

export interface Exercice {
	name: string
	debut: string
	fin: string
	en_cours: boolean
}

export interface ReglagesCompta {
	societe: { name: string; modified: string; devise: string }
	bilan: BilanPoint[]
	comptes: { groupes: { titre: string; champs: CompteChamp[] }[]; options: Record<string, string[]> }
	tva: Record<TvaSens, TauxTva[]>
	modes: ModePaiement[]
	comptes_tresorerie: string[]
	exercices: Exercice[]
	exercice_suivant: { name: string; debut: string; fin: string }
	timbre: { compte: string; compte_nom: string | null; minimum: number; tranches: { jusqu_a: number | null; taux: number }[] }
	droits: {
		comptes: boolean
		tva: Record<TvaSens, boolean>
		tva_creer: Record<TvaSens, boolean>
		modes: boolean
		modes_creer: boolean
		exercices: boolean
	}
}

export const TVA_SENS: { key: TvaSens; label: string; help: string }[] = [
	{ key: 'vente', label: 'TVA des ventes', help: 'Collectée sur les devis, commandes et factures clients.' },
	{ key: 'achat', label: 'TVA des achats', help: 'Déductible, sur les commandes et factures fournisseurs.' },
]

export const MODE_TYPES: { value: ModeType; label: string }[] = [
	{ value: 'Cash', label: 'Espèces' },
	{ value: 'Bank', label: 'Banque' },
	{ value: 'General', label: 'Autre' },
]

export const ETAT_LABELS: Record<BilanEtat, string> = { ok: 'En place', attention: 'À vérifier', manque: 'À régler' }

/** « 5121 - Banque - compte principal - U » → « 5121 - Banque - compte principal » : le suffixe de la société n'apprend rien. */
export function libelleCompte(compte: string | null | undefined): string {
	if (!compte) return ''
	return compte.replace(/ - [^ -]{1,6}$/, '')
}

/** Date ISO → jj/mm/aaaa. */
export function formatDate(iso: string): string {
	const [y, m, d] = iso.split('-')
	return d && m && y ? `${d}/${m}/${y}` : iso
}

export function formatTaux(taux: number): string {
	return `${String(taux).replace('.', ',')} %`
}
