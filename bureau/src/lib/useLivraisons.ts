/** État de la liste des bons de livraison. */
import { computed } from 'vue'
import { getLivraisons } from './api'
import type { LivraisonsResponse, LivraisonView } from './livraisons'
import { useServerList } from './useServerList'

export function useLivraisons(initial: { view?: LivraisonView; page?: number } = {}) {
	const list = useServerList<LivraisonsResponse, LivraisonView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-livraisons-par-page', fetch: getLivraisons })
	const livraisons = computed(() => list.response.value?.livraisons ?? [])
	return { ...list, livraisons }
}

export type LivraisonsState = ReturnType<typeof useLivraisons>
