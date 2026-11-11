/** Tableaux de bord des modules (unicare/api/bureau_tableaux.py) : types, périodes et mise en forme des graphiques. */

export type TableauModule = 'ventes' | 'achats' | 'stock' | 'tresorerie' | 'production'
export type PeriodeKey = 'mois' | '30j' | 'trimestre' | 'annee'
export type Ton = 'red' | 'amber' | 'green' | 'blue' | 'gray' | null

export const MODULE_LABELS: Record<TableauModule, string> = { ventes: 'Ventes', achats: 'Achats', stock: 'Stock', tresorerie: 'Trésorerie', production: 'Production' }

export const PERIODES: { key: PeriodeKey; label: string }[] = [
	{ key: 'mois', label: 'Ce mois' },
	{ key: '30j', label: '30 jours' },
	{ key: 'trimestre', label: 'Trimestre' },
	{ key: 'annee', label: 'Année' },
]

/** Page de l'interface (nom de route) et vue de sa liste. */
export interface TableauLien {
	page: string
	vue?: string
}

export interface Indicateur {
	key: string
	label: string
	valeur: number
	format: 'montant' | 'nombre' | 'pourcent'
	ton?: Ton
	details: { texte: string; ton?: Ton; fort?: boolean }[]
	lien: TableauLien
}

export interface Serie {
	key: string
	label: string
}

/** Unité des valeurs d'un graphique : des dinars (par défaut) ou des quantités. */
export type Unite = 'montant' | 'quantite'

export interface Tendance {
	titre: string
	unite?: Unite
	note?: string
	series: Serie[]
	points: { label: string; titre: string; valeurs: number[] }[]
}

export interface Repartition {
	titre: string
	unite?: Unite
	sous_titre?: string
	note?: string | null
	vide: string
	lignes: { label: string; valeur: number; fiche: string; name: string }[]
}

export interface Echeancier {
	titre: string
	note?: string
	series: Serie[]
	lignes: { label: string; valeurs: number[] }[]
}

export interface ListeLigne {
	fiche: string
	name: string
	titre: string
	detail?: string | null
	badge?: { texte: string; ton: Ton } | null
	montant?: number | null
	nature?: string | null
}

export interface Liste {
	key: string
	titre: string
	lien: TableauLien
	lignes: ListeLigne[]
	total: number
	ton: Ton
}

export interface Tableau {
	module: TableauModule
	periode: { key: PeriodeKey; libelle: string; debut: string; fin: string }
	jour: string
	indicateurs: Indicateur[]
	tendance: Tendance | null
	repartition: Repartition | null
	echeancier: Echeancier | null
	listes: Liste[]
	sans_periode: number
}

/** Couleurs des séries, dans l'ordre (validées pour la lecture des daltoniens) ; jamais réutilisées pour un état. */
export const SERIES_COLORS = ['var(--chart-1)', 'var(--chart-2)']

/** Haut de l'axe : un nombre rond juste au-dessus du maximum, découpé en 4 graduations au plus. */
export function niceScale(max: number): { top: number; ticks: number[] } {
	if (!(max > 0)) return { top: 1, ticks: [0, 1] }
	const rough = max / 4
	const power = 10 ** Math.floor(Math.log10(rough))
	const step = [1, 2, 2.5, 5, 10].map((factor) => factor * power).find((candidate) => candidate >= rough) ?? 10 * power
	const top = Math.ceil(max / step) * step
	const ticks: number[] = []
	for (let value = 0; value <= top + step / 2; value += step) ticks.push(Number(value.toPrecision(12)))
	return { top, ticks }
}

/** Libellé d'axe court : « 2,5 M », « 300 k », « 40 ». */
export function compactAmount(value: number) {
	const format = (number: number) => new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 }).format(number)
	if (Math.abs(value) >= 1_000_000) return `${format(value / 1_000_000)} M`
	if (Math.abs(value) >= 1_000) return `${format(value / 1_000)} k`
	return format(value)
}

/** Montant affiché en DA, sans décimales. */
export function amount(value?: number | null) {
	if (value == null) return '—'
	return `${new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(value)} DA`
}

export function indicateurValue(indicateur: Indicateur) {
	if (indicateur.format === 'montant') return amount(indicateur.valeur)
	if (indicateur.format === 'pourcent') return `${new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 }).format(indicateur.valeur)} %`
	return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 3 }).format(indicateur.valeur)
}

/** La liste derrière un lien : sa page, avec la vue demandée. */
export function lienRoute(lien: TableauLien) {
	return { name: lien.page, query: lien.vue ? { vue: lien.vue } : {} }
}

/** Les fiches d'un tiers ou d'un dépôt prennent `id`, comme les pièces. */
export function ficheRoute(fiche: string, name: string) {
	return { name: fiche, params: { id: name } }
}

/** Une valeur de graphique selon son unité : « 428 400 DA » ou « 1 476 ». */
export function valueText(value: number | null | undefined, unite: Unite = 'montant') {
	if (unite === 'montant') return amount(value)
	if (value == null) return '—'
	return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 3 }).format(value)
}
