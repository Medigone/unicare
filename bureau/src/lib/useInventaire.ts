/** Chargement et écritures d'un inventaire, communs à l'aperçu et à la fiche. */
import { getInventaire } from './api'
import type { InventaireDetail } from './inventaires'
import { useRecord } from './useRecord'

export function useInventaire(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<InventaireDetail>(id, getInventaire, changed)
	return { inventaire: record, ...rest }
}
