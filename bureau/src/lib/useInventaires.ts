/** État de la liste des inventaires. */
import { computed } from 'vue'
import { getInventaires } from './api'
import type { InventairesResponse, InventaireView } from './inventaires'
import { useServerList } from './useServerList'

export function useInventaires(initial: { view?: InventaireView; page?: number } = {}) {
	const list = useServerList<InventairesResponse, InventaireView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-inventaires-par-page', fetch: getInventaires })
	const inventaires = computed(() => list.response.value?.inventaires ?? [])
	return { ...list, inventaires }
}

export type InventairesState = ReturnType<typeof useInventaires>
