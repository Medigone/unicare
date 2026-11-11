/** Chargement et écritures d'un lot : l'aperçu lit l'essentiel, la fiche (`full`) ses mouvements et sa traçabilité. */
import { getLot, getLotFiche } from './api'
import type { LotDetail } from './lots'
import { useRecord } from './useRecord'

export function useLot(id: () => string, changed: () => void = () => {}, full = false) {
	const { record, ...rest } = useRecord<LotDetail>(id, full ? getLotFiche : getLot, changed)
	return { lot: record, ...rest }
}
