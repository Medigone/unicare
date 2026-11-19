<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getArticlesAideListe, getArticlesAideOptions } from '@/lib/api'
import { AIDE_COLONNES_DEFAUT, AIDE_LISTE_VUES, aideColonnes, aideTriTexte, type AideListeOptions, type AideListeVue } from '@/lib/aideListe'
import { dureeLabel } from '@/lib/aide'
import { formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import { fieldCellText } from '@/lib/listViews'
import { activePoste, pagesFor } from '@/lib/postes'
import type { ArticlesAideState } from '@/lib/useArticlesAide'

/** La liste des articles d'aide, sur le gabarit commun des listes : vues, colonnes, filtres, export. */
const props = defineProps<{ state: ArticlesAideState; selected?: string }>()
const emit = defineEmits<{ open: [name: string]; create: []; changed: [] }>()

const options = ref<AideListeOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
onMounted(async () => {
	try {
		options.value = await getArticlesAideOptions()
	} catch (e) {
		optionsError.value = (e as Error).message
	}
})

const ecrans = new Map(pagesFor(activePoste().key).map((page) => [page.id, page.module ? `${page.module} › ${page.label}` : page.label]))
const nomEcran = (id: string) => ecrans.get(id) ?? id
const columns = aideColonnes(nomEcran)

async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getArticlesAideListe(query.view as AideListeVue, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.articles, total: response.total }
}
</script>

<template>
	<DataList
		:state="state"
		:rows="state.articles.value"
		title="Aide"
		noun="article"
		create-label="Nouvel article"
		search-label="Rechercher un article"
		search-placeholder="Titre, résumé, écran, mot-clé"
		:columns="columns"
		locked-column="titre"
		:default-columns="AIDE_COLONNES_DEFAUT"
		list-id="aide"
		:views="AIDE_LISTE_VUES"
		:counts="state.response.value?.counts"
		default-sort-label="Ordre de l'aide"
		:sort-text="aideTriTexte(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:load-error="optionsError"
		doctype="Article Aide"
		:export-fields="fields"
		@pick="$event && emit('open', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
		@create="emit('create')"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Article Aide" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns: shown }">
			<template v-for="column in shown" :key="column.key">
				<span v-if="column.key === 'titre'" class="list-client truncate" :title="row.resume || row.titre">{{ row.titre }}</span>
				<span v-else-if="column.key === 'rubrique'" class="truncate">{{ row.rubrique || '—' }}</span>
				<span v-else-if="column.key === 'statut'"><StatusPill :status="row.statut" :tone="row.statut === 'Publié' ? 'green' : 'amber'" /></span>
				<span v-else-if="column.key === 'ecrans'" class="truncate" :class="!row.ecrans.length && 'text-ink-gray-6'" :title="row.ecrans.map(nomEcran).join('\n')">
					<template v-if="row.ecrans.length">{{ nomEcran(row.ecrans[0]) }}<span v-if="row.ecrans.length > 1" class="text-ink-gray-6"> + {{ row.ecrans.length - 1 }}</span></template>
					<template v-else>Aucun écran</template>
				</span>
				<span v-else-if="column.key === 'resume'" class="truncate text-ink-gray-7" :title="row.resume">{{ row.resume || '—' }}</span>
				<span v-else-if="column.key === 'source'" class="truncate" :class="!row.source && 'text-ink-gray-6'">{{ row.source || 'Bureau' }}</span>
				<span v-else-if="column.key === 'date_revision'" class="tabular-nums">{{ formatDay(row.date_revision) || '—' }}</span>
				<span v-else-if="column.key === 'duree_lecture'" class="list-col-end tabular-nums">{{ row.duree_lecture ? dureeLabel(row.duree_lecture) : '—' }}</span>
				<span v-else-if="column.key === 'name'" class="truncate tabular-nums text-ink-gray-7">{{ row.name }}</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Modifier l'article</button>
			<RouterLink :to="{ name: 'AideArticle', params: { slug: row.name } }" class="app-menu-item" role="menuitem"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Voir dans le centre d'aide</RouterLink>
		</template>

		<slot></slot>
	</DataList>
</template>
