/** Chargement et écritures d'une facture, communs à l'aperçu et à la fiche. */
import { getFacture } from './api'
import type { FactureDetail } from './factures'
import { useRecord } from './useRecord'

export function useFacture(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<FactureDetail>(id, getFacture, changed)
	return { facture: record, ...rest }
}
