/** Chargement et écritures d'une commande d'achat, communs à l'aperçu et à la fiche. */
import { getCommandeAchat } from './api'
import type { CommandeAchatDetail } from './commandesAchat'
import { useRecord } from './useRecord'

export function useCommandeAchat(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<CommandeAchatDetail>(id, getCommandeAchat, changed)
	return { commande: record, ...rest }
}
