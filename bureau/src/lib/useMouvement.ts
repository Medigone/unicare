/** Chargement et écritures d'un mouvement de stock, communs à l'aperçu et à la fiche. */
import { getMouvement } from './api'
import type { MouvementDetail } from './mouvements'
import { useRecord } from './useRecord'

export function useMouvement(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<MouvementDetail>(id, getMouvement, changed)
	return { mouvement: record, ...rest }
}
