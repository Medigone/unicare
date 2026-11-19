/** État de la liste de Réglages › Aide. */
import { computed } from 'vue'
import { getArticlesAideListe } from './api'
import type { AideListeResponse, AideListeVue } from './aideListe'
import { useServerList } from './useServerList'

export function useArticlesAide(initial: { view?: AideListeVue; page?: number } = {}) {
	const list = useServerList<AideListeResponse, AideListeVue>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-aide-par-page', fetch: getArticlesAideListe })
	const articles = computed(() => list.response.value?.articles ?? [])
	return { ...list, articles }
}

export type ArticlesAideState = ReturnType<typeof useArticlesAide>
