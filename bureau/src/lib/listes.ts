/** Réglages › Listes de choix : valeurs des listes déroulantes du bureau (unicare/api/bureau_listes.py). */

export type ListeCode = 'raisons' | 'clients' | 'fournisseurs' | 'articles' | 'unites'

export interface ListeResume {
	code: ListeCode
	label: string
	aide: string
	total: number
	/** Unités seulement : celles proposées dans les listes. */
	actifs: number | null
	droits: { creer: boolean; modifier: boolean; supprimer: boolean; renommer_utilisee: boolean }
}

export interface ListeValeur {
	name: string
	modified: string
	/** Fiches et pièces qui l'utilisent : une valeur utilisée ne se supprime pas. */
	usages: number
	actif: boolean
	/** Unités : quantités entières seulement. */
	entier?: boolean
}

export type UniteVue = 'actives' | 'toutes'

/** Filtre sans tenir compte des accents ni de la casse. */
export function filtrerValeurs(valeurs: ListeValeur[], recherche: string, vue?: UniteVue): ListeValeur[] {
	const plain = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
	const mots = plain(recherche).split(/\s+/).filter(Boolean)
	return valeurs.filter((row) => (vue !== 'actives' || row.actif) && mots.every((mot) => plain(row.name).includes(mot)))
}

export function usagesLabel(usages: number): string {
	if (!usages) return 'Inutilisée'
	return `${usages} fiche${usages > 1 ? 's' : ''}`
}
