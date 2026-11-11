/** Chargement et écritures d'un ordre de conditionnement, communs à l'aperçu et à la fiche. */
import { getOrdre } from './api'
import type { OrdreDetail } from './ordres'
import { useRecord } from './useRecord'

export function useOrdre(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<OrdreDetail>(id, getOrdre, changed)
	return { ordre: record, ...rest }
}
