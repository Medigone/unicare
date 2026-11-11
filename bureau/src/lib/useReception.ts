/** Chargement et écritures d'une réception, communs à l'aperçu et à la fiche. */
import { getReception } from './api'
import type { ReceptionDetail } from './receptions'
import { useRecord } from './useRecord'

export function useReception(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<ReceptionDetail>(id, getReception, changed)
	return { reception: record, ...rest }
}
