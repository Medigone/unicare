/** État de la liste des factures d'achat. */
import { computed } from 'vue'
import { getFacturesAchat } from './api'
import type { FactureAchatView, FacturesAchatResponse } from './facturesAchat'
import { useServerList } from './useServerList'

export function useFacturesAchat(initial: { view?: FactureAchatView; page?: number } = {}) {
	const list = useServerList<FacturesAchatResponse, FactureAchatView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-factures-achat-par-page', fetch: getFacturesAchat })
	const factures = computed(() => list.response.value?.factures ?? [])
	return { ...list, factures }
}

export type FacturesAchatState = ReturnType<typeof useFacturesAchat>
