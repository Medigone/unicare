/** Chargement et écritures d'un paiement, communs à l'aperçu et à la fiche. */
import { getPaiement } from './api'
import type { PaiementDetail } from './paiements'
import { useRecord } from './useRecord'

export function usePaiement(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<PaiementDetail>(id, getPaiement, changed)
	return { paiement: record, ...rest }
}
