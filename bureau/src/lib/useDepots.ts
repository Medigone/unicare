/** État de la liste des dépôts. */
import { computed } from 'vue'
import { getDepots } from './api'
import type { DepotsResponse, DepotView } from './depots'
import { useServerList } from './useServerList'

export function useDepots(initial: { view?: DepotView; page?: number } = {}) {
	const list = useServerList<DepotsResponse, DepotView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-depots-par-page', fetch: getDepots })
	const depots = computed(() => list.response.value?.depots ?? [])
	return { ...list, depots }
}

export type DepotsState = ReturnType<typeof useDepots>
