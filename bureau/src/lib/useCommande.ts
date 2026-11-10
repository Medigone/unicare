/** Chargement et écritures d'une commande, communs à l'aperçu et à la fiche. */
import { getCommande } from './api'
import type { CommandeDetail } from './commandes'
import { useRecord } from './useRecord'

export function useCommande(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<CommandeDetail>(id, getCommande, changed)
	return { commande: record, ...rest }
}
