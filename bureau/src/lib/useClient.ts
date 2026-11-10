/** Chargement et écritures d'un client : l'aperçu lit l'essentiel, la fiche (`full`) lit aussi ventes, comptabilité et commentaires. */
import { getClient, getClientFiche } from './api'
import type { ClientDetail } from './clients'
import { useRecord } from './useRecord'

export function useClient(id: () => string, changed: () => void = () => {}, full = false) {
	const { record, ...rest } = useRecord<ClientDetail>(id, full ? getClientFiche : getClient, changed)
	return { client: record, ...rest }
}
