/** État de la liste des ordres de conditionnement. */
import { computed } from 'vue'
import { getOrdres } from './api'
import { DEFAULT_ORDRE_VIEW, type OrdresResponse, type OrdreView } from './ordres'
import { useServerList } from './useServerList'

export function useOrdres(initial: { view?: OrdreView; page?: number } = {}) {
	const list = useServerList<OrdresResponse, OrdreView>({ view: initial.view ?? DEFAULT_ORDRE_VIEW, page: initial.page, pageSizeKey: 'bureau-ordres-par-page', fetch: getOrdres })
	const ordres = computed(() => list.response.value?.ordres ?? [])
	return { ...list, ordres }
}

export type OrdresState = ReturnType<typeof useOrdres>
