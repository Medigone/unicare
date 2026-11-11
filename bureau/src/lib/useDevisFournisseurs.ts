/** État de la liste des devis fournisseur. */
import { computed } from 'vue'
import { getDevisFournisseurs } from './api'
import type { DevisFournisseurResponse, DevisFournisseurView } from './devisFournisseur'
import { useServerList } from './useServerList'

export function useDevisFournisseurs(initial: { view?: DevisFournisseurView; page?: number } = {}) {
	const list = useServerList<DevisFournisseurResponse, DevisFournisseurView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-devis-fournisseurs-par-page', fetch: getDevisFournisseurs })
	const devis = computed(() => list.response.value?.devis ?? [])
	return { ...list, devis }
}

export type DevisFournisseursState = ReturnType<typeof useDevisFournisseurs>
