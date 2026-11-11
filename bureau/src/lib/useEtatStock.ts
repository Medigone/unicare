/** État de la liste « État du stock ». */
import { computed } from 'vue'
import { getEtatStock } from './api'
import type { EtatStockResponse, EtatStockView } from './etatStock'
import { useServerList } from './useServerList'

export function useEtatStock(initial: { view?: EtatStockView; page?: number } = {}) {
	const list = useServerList<EtatStockResponse, EtatStockView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-etat-stock-par-page', fetch: getEtatStock })
	const lignes = computed(() => list.response.value?.lignes ?? [])
	return { ...list, lignes }
}

export type EtatStockState = ReturnType<typeof useEtatStock>
