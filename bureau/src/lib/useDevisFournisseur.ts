/** Chargement et écritures d'un devis fournisseur, communs à l'aperçu et à la fiche. */
import { getDevisFournisseur } from './api'
import type { DevisFournisseurDetail } from './devisFournisseur'
import { useRecord } from './useRecord'

export function useDevisFournisseur(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<DevisFournisseurDetail>(id, getDevisFournisseur, changed)
	return { devis: record, ...rest }
}
