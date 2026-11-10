/** État de la liste des commandes. */
import { computed } from 'vue'
import { getCommandes } from './api'
import type { CommandesResponse, CommandeView } from './commandes'
import { useServerList } from './useServerList'

export function useCommandes(initial: { view?: CommandeView; page?: number } = {}) {
	const list = useServerList<CommandesResponse, CommandeView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-commandes-par-page', fetch: getCommandes })
	const commandes = computed(() => list.response.value?.commandes ?? [])
	return { ...list, commandes }
}

export type CommandesState = ReturnType<typeof useCommandes>
