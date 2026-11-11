/** État de la liste des mouvements de stock. */
import { computed } from 'vue'
import { getMouvements } from './api'
import type { MouvementsResponse, MouvementView } from './mouvements'
import { useServerList } from './useServerList'

export function useMouvements(initial: { view?: MouvementView; page?: number } = {}) {
	const list = useServerList<MouvementsResponse, MouvementView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-mouvements-par-page', fetch: getMouvements })
	const mouvements = computed(() => list.response.value?.mouvements ?? [])
	return { ...list, mouvements }
}

export type MouvementsState = ReturnType<typeof useMouvements>
