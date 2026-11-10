/** État de la liste des paiements. */
import { computed } from 'vue'
import { getPaiements } from './api'
import type { PaiementsResponse, PaiementView } from './paiements'
import { useServerList } from './useServerList'

export function usePaiements(initial: { view?: PaiementView; page?: number } = {}) {
	const list = useServerList<PaiementsResponse, PaiementView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-paiements-par-page', fetch: getPaiements })
	const paiements = computed(() => list.response.value?.paiements ?? [])
	return { ...list, paiements }
}

export type PaiementsState = ReturnType<typeof usePaiements>
