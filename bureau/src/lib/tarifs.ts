/** Réglages › Tarifs et prix (unicare/api/bureau_tarifs.py) : types, vues et saisie d'un prix. */

export type TarifSens = 'vente' | 'achat'
export type PrixVue = 'tous' | 'sans_prix' | 'avec_prix' | 'a_venir' | 'expire' | 'ecart'

export interface Tarif {
	name: string
	sens: TarifSens
	devise: string
	/** Désactivé : plus proposé sur les pièces, ses prix ne se modifient plus. */
	actif: boolean
	/** Articles qui ont un prix général en vigueur aujourd'hui. */
	prix: number
	/** Articles actifs du sens du tarif (vendus ou achetés). */
	total: number
	defaut: boolean
	/** Tarif calculé : le tarif de base qu'il suit. */
	base: string | null
}

export type Ajustement = 'aucun' | 'remise' | 'majoration'

/** Règle d'un tarif calculé depuis un autre. */
export interface Regle {
	base: string
	ajustement: Ajustement
	pourcentage: number
	/** Pas d'arrondi : 0 au centime, 1 au dinar, 10 à la dizaine… */
	arrondi: number
	calcule_le: string | null
	/** Changements du tarif de base pas encore repris. */
	changements?: number
}

/** Un changement du tarif de base : prix ou fin changés, ligne ajoutée ou supprimée. */
export interface Changement {
	cle: string
	type: 'prix' | 'nouveau' | 'supprime'
	article: string
	designation: string
	tiers: string | null
	base_avant: number | null
	base_apres: number | null
	actuel: number | null
	nouveau: number | null
	debut: string | null
	fin: string | null
	/** Le prix de ce tarif a été changé à la main depuis son calcul. */
	manuel: boolean
}

/** Création d'un tarif à partir d'un autre. */
export interface TarifCopie {
	base: string
	ajustement: Ajustement
	pourcentage: number
	arrondi: number
	debut: string
	a_venir: 0 | 1
	tiers: 0 | 1
	lien: 0 | 1
}

export interface Changements {
	regle: Regle
	changements: Changement[]
}

export interface TarifsReglages {
	tarifs: Tarif[]
	defauts: Record<TarifSens, string | null>
	can_edit_prix: boolean
	can_create_tarif: boolean
	can_toggle_tarif: boolean
	can_delete_tarif: boolean
	can_set_defaut: Record<TarifSens, boolean>
}

/** Une ligne de la page : le prix général en vigueur d'un article et ce qui l'entoure. */
export interface PrixLigne {
	article: string
	designation: string
	unite: string
	prix: number | null
	unite_prix: string | null
	/** Ligne « Item Price » en vigueur, et sa date de modification : garde contre une modification faite ailleurs. */
	ligne: string | null
	modified: string | null
	debut: string | null
	fin: string | null
	expire_bientot: boolean
	a_venir: { prix: number; debut: string } | null
	nb_a_venir: number
	/** Prix réservés à un client (vente) ou à un fournisseur (achat), en cours ou à venir. */
	nb_tiers: number
	nb_anciens: number
	/** Sans prix en vigueur : le dernier prix général expiré. */
	dernier_expire: { prix: number; fin: string } | null
	nb_lignes: number
	/** Tarif d'achat : dernier prix payé, et son écart relatif avec le prix du tarif (0,1 = +10 %). */
	dernier_achat: number | null
	ecart: number | null
}

export interface PrixResponse {
	tarif: { name: string; sens: TarifSens; devise: string; actif: boolean; regle: Regle | null }
	date: string
	lignes: PrixLigne[]
	total: number
	compte: Partial<Record<PrixVue, number>>
	/** Tarif d'achat : articles sans prix en vigueur qui ont un dernier prix payé. */
	reprenables: number
	start: number
	page: number
}

export type LigneStatut = 'vigueur' | 'a_venir' | 'expire' | 'tiers' | 'remplace' | 'lot'

/** Une ligne « Item Price » d'un article, dans la fenêtre de ses prix. */
export interface LignePrix {
	ligne: string
	statut: LigneStatut
	prix: number
	debut: string | null
	fin: string | null
	unite: string
	/** Client (vente) ou fournisseur (achat) ; null : tous. */
	tiers: string | null
	lot: string | null
	note: string
	/** Délai de livraison en jours (achat). */
	delai: number | null
	modified: string
}

export interface LignesArticle {
	article: string
	designation: string
	unite: string
	unites: string[]
	sens: TarifSens
	devise: string
	dernier_achat: number | null
	lignes: LignePrix[]
}

/** Saisie de la fenêtre « Nouveau prix ». */
export interface LigneValeurs {
	prix: string
	debut: string
	fin: string
	unite: string
	tiers: string
	note: string
	delai: string
}

/** Prix d'un article dans les tarifs par défaut, sur sa fiche (null : le rôle ne lit pas les prix). */
export interface PrixArticle {
	vente: { tarif: string | null; prix: number | null; concerne: boolean }
	achat: { tarif: string | null; prix: number | null; concerne: boolean }
	dernier_achat: number | null
	can_edit: boolean
}

/** Filtres de la liste ; « Écart » n'existe que pour un tarif d'achat. */
export const PRIX_VUES: { key: PrixVue; label: string; achat?: boolean }[] = [
	{ key: 'tous', label: 'Tous' },
	{ key: 'sans_prix', label: 'Sans prix' },
	{ key: 'avec_prix', label: 'Avec prix' },
	{ key: 'a_venir', label: 'À venir' },
	{ key: 'expire', label: 'Expire bientôt' },
	{ key: 'ecart', label: 'Écart > 5 %', achat: true },
]

export const STATUT_LABELS: Record<LigneStatut, string> = {
	vigueur: 'En vigueur',
	a_venir: 'À venir',
	expire: 'Expiré',
	tiers: '',
	remplace: 'Remplacé',
	lot: 'Lot',
}

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

const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']

/** « 2026-11-01 » → « 1 nov. 2026 » (sans l'année avec `court`). */
export function formatDate(iso?: string | null, court = false) {
	if (!iso) return ''
	const [annee, mois, jour] = iso.slice(0, 10).split('-').map(Number)
	return court ? `${jour} ${MOIS[mois - 1]}` : `${jour} ${MOIS[mois - 1]} ${annee}`
}

/** Période d'une ligne de prix : « 1 oct. 2026 → 31 déc. 2026 », « 1 oct. 2026 → sans fin ». */
export function formatPeriode(debut: string | null, fin: string | null) {
	return `${debut ? formatDate(debut) : 'toujours'} → ${fin ? formatDate(fin) : 'sans fin'}`
}

/** Colonne « Validité » de la liste. */
export function validite(ligne: Pick<PrixLigne, 'prix' | 'debut' | 'fin' | 'nb_lignes' | 'dernier_expire'>) {
	if (ligne.prix === null) return ligne.dernier_expire || ligne.nb_lignes ? 'aucun prix en vigueur' : 'jamais chiffré'
	if (ligne.debut && ligne.fin) return `${formatDate(ligne.debut, true)} → ${formatDate(ligne.fin)}`
	if (ligne.fin) return `jusqu'au ${formatDate(ligne.fin)}`
	if (ligne.debut) return `depuis le ${formatDate(ligne.debut)}`
	return 'sans limite'
}

/** Jours restants avant `fin`, à compter de `date` (les deux au format AAAA-MM-JJ). */
export function joursAvant(fin: string, date: string) {
	return Math.round((Date.parse(fin.slice(0, 10)) - Date.parse(date.slice(0, 10))) / 86400000)
}

/** Écart relatif signé, « +8,2 % », « −3 % », « = » quand il est nul. */
export function formatEcart(ecart: number | null) {
	if (ecart === null) return '—'
	const pct = Math.round(ecart * 1000) / 10
	if (pct === 0) return '='
	return `${pct > 0 ? '+' : '−'}${String(Math.abs(pct)).replace('.', ',')} %`
}

/** La veille d'une date AAAA-MM-JJ. */
export function veille(iso: string) {
	const date = new Date(`${iso.slice(0, 10)}T12:00:00Z`)
	date.setUTCDate(date.getUTCDate() - 1)
	return date.toISOString().slice(0, 10)
}

export const ARRONDIS: { pas: number; label: string }[] = [
	{ pas: 0, label: 'Au centime (pas d\'arrondi)' },
	{ pas: 1, label: 'Au dinar' },
	{ pas: 10, label: 'À la dizaine' },
	{ pas: 100, label: 'À la centaine' },
]

/** Même calcul que le serveur (tarifs_calcules.calculer) : ajustement, puis arrondi au pas le plus proche. */
export function calculerPrix(taux: number, ajustement: Ajustement, pourcentage: number, arrondi: number) {
	const facteur = ajustement === 'remise' ? 1 - pourcentage / 100 : ajustement === 'majoration' ? 1 + pourcentage / 100 : 1
	let valeur = taux * facteur
	if (arrondi) valeur = Math.floor(valeur / arrondi + 0.5 + 1e-9) * arrondi
	valeur = Math.round(valeur * 100) / 100
	return valeur > 0 ? valeur : arrondi || 0.01
}

/** « remise 10 % · arrondi au dinar ». */
export function regleTexte(regle: Pick<Regle, 'ajustement' | 'pourcentage' | 'arrondi'>) {
	const pct = String(regle.pourcentage).replace('.', ',')
	const ajustement = regle.ajustement === 'remise' ? `remise ${pct} %` : regle.ajustement === 'majoration' ? `majoration ${pct} %` : 'mêmes prix'
	const arrondi = ARRONDIS.find((item) => item.pas === regle.arrondi)
	return regle.arrondi && arrondi ? `${ajustement} · arrondi ${arrondi.label.toLowerCase()}` : ajustement
}
