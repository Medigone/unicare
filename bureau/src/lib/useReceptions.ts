/** État de la liste des réceptions. */
import { computed } from 'vue'
import { getReceptions } from './api'
import type { ReceptionsResponse, ReceptionView } from './receptions'
import { useServerList } from './useServerList'

export function useReceptions(initial: { view?: ReceptionView; page?: number } = {}) {
	const list = useServerList<ReceptionsResponse, ReceptionView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-receptions-par-page', fetch: getReceptions })
	const receptions = computed(() => list.response.value?.receptions ?? [])
	return { ...list, receptions }
}

export type ReceptionsState = ReturnType<typeof useReceptions>
