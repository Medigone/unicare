/** Chargement et écritures d'un dépôt : l'aperçu lit l'essentiel, la fiche (`full`) lit aussi stock, mouvements et commentaires. */
import { getDepot, getDepotFiche } from './api'
import type { DepotDetail } from './depots'
import { useRecord } from './useRecord'

export function useDepot(id: () => string, changed: () => void = () => {}, full = false) {
	const { record, ...rest } = useRecord<DepotDetail>(id, full ? getDepotFiche : getDepot, changed)
	return { depot: record, ...rest }
}
