/** État de la liste des factures. */
import { computed } from 'vue'
import { getFactures } from './api'
import type { FacturesResponse, FactureView } from './factures'
import { useServerList } from './useServerList'

export function useFactures(initial: { view?: FactureView; page?: number } = {}) {
	const list = useServerList<FacturesResponse, FactureView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-factures-par-page', fetch: getFactures })
	const factures = computed(() => list.response.value?.factures ?? [])
	return { ...list, factures }
}

export type FacturesState = ReturnType<typeof useFactures>
