/** Chargement et écritures d'une recette, communs à l'aperçu et à la fiche. */
import { getRecette } from './api'
import type { RecetteDetail } from './recettes'
import { useRecord } from './useRecord'

export function useRecette(id: () => string, changed: () => void = () => {}) {
	const { record, ...rest } = useRecord<RecetteDetail>(id, getRecette, changed)
	return { recette: record, ...rest }
}
