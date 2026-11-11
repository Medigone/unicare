/** État de la liste des recettes. */
import { computed } from 'vue'
import { getRecettes } from './api'
import { DEFAULT_RECETTE_VIEW, type RecettesResponse, type RecetteView } from './recettes'
import { useServerList } from './useServerList'

export function useRecettes(initial: { view?: RecetteView; page?: number } = {}) {
	const list = useServerList<RecettesResponse, RecetteView>({ view: initial.view ?? DEFAULT_RECETTE_VIEW, page: initial.page, pageSizeKey: 'bureau-recettes-par-page', fetch: getRecettes })
	const recettes = computed(() => list.response.value?.recettes ?? [])
	return { ...list, recettes }
}

export type RecettesState = ReturnType<typeof useRecettes>
