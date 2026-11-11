/** Chargement et écritures d'une facture d'achat, communs à l'aperçu et à la fiche. */
import { getFactureAchat } from './api'
import type { FactureAchatDetail } from './facturesAchat'
import { useRecord } from './useRecord'

export function useFactureAchat(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<FactureAchatDetail>(id, getFactureAchat, changed)
	return { facture: record, ...rest }
}
