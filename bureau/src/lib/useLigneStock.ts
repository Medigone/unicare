/** Chargement d'une ligne de stock (article × dépôt) : l'aperçu lit l'essentiel, la fiche (`full`) l'historique et les lots. */
import { getLigneStock, getLigneStockFiche } from './api'
import type { LigneStockDetail } from './etatStock'
import { useRecord } from './useRecord'

export function useLigneStock(id: () => string, changed: () => void = () => {}, full = false) {
	const { record, ...rest } = useRecord<LigneStockDetail>(id, full ? getLigneStockFiche : getLigneStock, changed)
	return { ligne: record, ...rest }
}
