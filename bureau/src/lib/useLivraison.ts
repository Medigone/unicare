/** Chargement et écritures d'un bon de livraison, communs à l'aperçu et à la fiche. */
import { getLivraison } from './api'
import type { LivraisonDetail } from './livraisons'
import { useRecord } from './useRecord'

export function useLivraison(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<LivraisonDetail>(id, getLivraison, changed)
	return { livraison: record, ...rest }
}
