/** État de la liste des lots. */
import { computed } from 'vue'
import { getLots } from './api'
import type { LotsResponse, LotView } from './lots'
import { useServerList } from './useServerList'

export function useLots(initial: { view?: LotView; page?: number } = {}) {
	const list = useServerList<LotsResponse, LotView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-lots-par-page', fetch: getLots })
	const lots = computed(() => list.response.value?.lots ?? [])
	return { ...list, lots }
}

export type LotsState = ReturnType<typeof useLots>
