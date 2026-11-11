/** État de la liste des fournisseurs. */
import { computed } from 'vue'
import { getFournisseurs } from './api'
import type { FournisseursResponse, FournisseurView } from './fournisseurs'
import { useServerList } from './useServerList'

export function useFournisseurs(initial: { view?: FournisseurView; page?: number } = {}) {
	const list = useServerList<FournisseursResponse, FournisseurView>({ view: initial.view ?? 'all', page: initial.page, pageSizeKey: 'bureau-fournisseurs-par-page', fetch: getFournisseurs })
	const fournisseurs = computed(() => list.response.value?.fournisseurs ?? [])
	return { ...list, fournisseurs }
}

export type FournisseursState = ReturnType<typeof useFournisseurs>
