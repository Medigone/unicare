<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import RecetteDialog from './RecetteDialog.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getRecetteOptions, getRecettes } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { DEFAULT_RECETTE_COLUMNS, DEFAULT_RECETTE_VIEW, RECETTE_COLUMNS, RECETTE_VIEWS, recetteSortText, type RecetteOptions, type RecetteRow, type RecetteView } from '@/lib/recettes'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { RecettesState } from '@/lib/useRecettes'

const props = defineProps<{ state: RecettesState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const dataList = ref<{ revealCreated: () => Promise<void> } | null>(null)
const options = ref<RecetteOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getRecettes(query.view as RecetteView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.recettes as RecetteRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getRecetteOptions()
	} catch (e) {
		optionsError.value = (e as Error).message
	}
})

// Création : la liste reste en place, avec la nouvelle ligne surlignée et un lien vers sa fiche.
const creating = ref(false)
const created = ref<string | null>(null)
let createdTimer: ReturnType<typeof setTimeout> | null = null
function dismissCreated() {
	if (createdTimer) clearTimeout(createdTimer)
	created.value = null
}
async function onCreated(name: string) {
	const state = props.state
	dismissCreated()
	created.value = name
	createdTimer = setTimeout(dismissCreated, 8000)
	state.view.value = DEFAULT_RECETTE_VIEW
	state.search.value = ''
	state.conditions.value = []
	await nextTick()
	await state.load()
	await state.reveal(name)
	await dataList.value?.revealCreated()
}
function openCreated() {
	const name = created.value
	dismissCreated()
	if (name) emit('open', name)
}
onBeforeUnmount(() => {
	if (createdTimer) clearTimeout(createdTimer)
})

const columns = RECETTE_COLUMNS
const defaultColumns = DEFAULT_RECETTE_COLUMNS
</script>

<template>
	<DataList
		ref="dataList"
		:state="state"
		:rows="state.recettes.value"
		title="Recettes"
		noun="recette"
		:create-label="canCreate('Recette de Conditionnement') ? 'Nouvelle recette' : undefined"
		search-label="Rechercher une recette"
		search-placeholder="Produit, recette"
		:columns="columns"
		locked-column="designation"
		:default-columns="defaultColumns"
		list-id="recettes"
		:views="RECETTE_VIEWS"
		:counts="state.response.value?.counts"
		default-sort-label="Par produit"
		:sort-text="recetteSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:created="created ?? undefined"
		:load-error="optionsError"
		doctype="Recette de Conditionnement"
		:export-fields="fields"
		bulk-doctype="Recette de Conditionnement"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
		@create="creating = true"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Recette de Conditionnement" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'designation'" class="list-client truncate" :title="row.designation">{{ row.designation }}</span>
				<span v-else-if="column.key === 'name'" class="truncate tabular-nums text-ink-gray-7">{{ row.name }}</span>
				<span v-else-if="column.key === 'actif'"><StatusPill :status="row.actif ? 'Active' : 'Inactive'" :tone="row.actif ? 'green' : 'gray'" /></span>
				<span v-else-if="column.key === 'base'" class="list-col-end tabular-nums">{{ formatQty(row.quantite_base) }} <span class="text-xs text-ink-gray-6">{{ row.unite }}</span></span>
				<span v-else-if="column.key === 'rendement'" class="list-col-end tabular-nums">{{ String(row.rendement).replace('.', ',') }} %</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Ouvrir la fiche</button>
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('pick', row.name)">Aperçu</button>
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Recette de Conditionnement', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>

		<RecetteDialog v-if="creating" @close="creating = false" @created="onCreated" />
		<AppToast :message="created ? 'Recette créée.' : ''" :duration="0" @close="created = null">
			<button type="button" class="app-toast-action" @click="openCreated">Ouvrir la fiche</button>
		</AppToast>
	</DataList>
</template>
