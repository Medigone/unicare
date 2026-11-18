/** Réglages › Tarifs et prix (unicare/api/bureau_tarifs.py) : types, vues et saisie d'un prix. */

export type TarifSens = 'vente' | 'achat'
export type PrixVue = 'tous' | 'sans_prix' | 'avec_prix'

export interface Tarif {
	name: string
	sens: TarifSens
	devise: string
	/** Articles qui ont un prix dans ce tarif. */
	prix: number
	defaut: boolean
}

export interface TarifsReglages {
	tarifs: Tarif[]
	defauts: Record<TarifSens, string | null>
	can_edit_prix: boolean
	can_create_tarif: boolean
	can_set_defaut: Record<TarifSens, boolean>
}

export interface PrixLigne {
	article: string
	designation: string
	unite: string
	prix: number | null
	unite_prix: string | null
	/** Date de modification de la ligne de prix : garde contre une modification faite ailleurs. */
	modified: string | null
	/** Tarif d'achat : dernier prix payé, proposé quand le tarif n'a pas de prix. */
	dernier_achat: number | null
}

export interface PrixResponse {
	tarif: { name: string; sens: TarifSens; devise: string }
	lignes: PrixLigne[]
	total: number
	compte: Record<PrixVue, number>
	start: number
	page: number
}

/** Prix d'un article dans les tarifs par défaut, sur sa fiche (null : le rôle ne lit pas les prix). */
export interface PrixArticle {
	vente: { tarif: string | null; prix: number | null; concerne: boolean }
	achat: { tarif: string | null; prix: number | null; concerne: boolean }
	dernier_achat: number | null
	can_edit: boolean
}

export const PRIX_VUES: { key: PrixVue; label: string }[] = [
	{ key: 'tous', label: 'Tous' },
	{ key: 'sans_prix', label: 'Sans prix' },
	{ key: 'avec_prix', label: 'Avec prix' },
]

export const SENS_LABELS: Record<TarifSens, string> = { vente: 'Vente', achat: 'Achat' }

/** Prix affiché : espaces des milliers, virgule, deux décimales seulement s'il y en a. */
export function formatPrix(value?: number | null) {
	if (value === null || value === undefined) return ''
	const [entier, decimales] = (Math.round(value * 100) / 100).toFixed(2).split('.')
	const groupe = entier.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
	return decimales === '00' ? groupe : `${groupe},${decimales}`
}

/** Saisie d'un prix : vide (retirer le prix), un nombre > 0, ou une erreur à afficher. */
export function parsePrix(text: string): { value: number | null } | { error: string } {
	const clean = text.replace(/[\s ]/g, '').replace(',', '.')
	if (!clean) return { value: null }
	if (!/^\d+(\.\d+)?$/.test(clean)) return { error: 'Saisissez un nombre, par exemple 1 250,50.' }
	const value = Number(clean)
	if (!(value > 0)) return { error: 'Un prix doit être supérieur à zéro. Pour retirer le prix, videz le champ.' }
	return { value }
}

/** Le prix saisi change-t-il quelque chose ? (« 1 250,5 » et 1250.5 sont le même prix). */
export function prixChange(text: string, current: number | null) {
	const parsed = parsePrix(text)
	if ('error' in parsed) return true
	return parsed.value !== current
}
