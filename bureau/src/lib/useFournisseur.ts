/** Chargement et écritures d'un fournisseur : l'aperçu lit l'essentiel, la fiche (`full`) lit aussi achats, comptabilité et commentaires. */
import { getFournisseur, getFournisseurFiche } from './api'
import type { FournisseurDetail } from './fournisseurs'
import { useRecord } from './useRecord'

export function useFournisseur(id: () => string, changed: () => void = () => {}, full = false) {
	const { record, ...rest } = useRecord<FournisseurDetail>(id, full ? getFournisseurFiche : getFournisseur, changed)
	return { fournisseur: record, ...rest }
}
