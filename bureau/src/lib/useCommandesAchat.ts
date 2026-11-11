/** État de la liste des commandes d'achat. */
import { computed } from 'vue'
import { getCommandesAchat } from './api'
import type { CommandeAchatView, CommandesAchatResponse } from './commandesAchat'
import { useServerList } from './useServerList'

export function useCommandesAchat(initial: { view?: CommandeAchatView; page?: number } = {}) {
	const list = useServerList<CommandesAchatResponse, CommandeAchatView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-commandes-achat-par-page', fetch: getCommandesAchat })
	const commandes = computed(() => list.response.value?.commandes ?? [])
	return { ...list, commandes }
}

export type CommandesAchatState = ReturnType<typeof useCommandesAchat>
