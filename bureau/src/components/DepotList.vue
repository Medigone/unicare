<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import DepotDialog from './DepotDialog.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getDepotOptions, getDepots } from '@/lib/api'
import { formatAmount } from '@/lib/clients'
import { allowedDepotColumns, allowedDepotViews, DEFAULT_DEPOT_COLUMNS, depotSortText, type DepotOptions, type DepotRow, type DepotView } from '@/lib/depots'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { DepotsState } from '@/lib/useDepots'

const props = defineProps<{ state: DepotsState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const dataList = ref<{ revealCreated: () => Promise<void> } | null>(null)
const options = ref<DepotOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getDepots(query.view as DepotView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.depots as DepotRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getDepotOptions()
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
	state.view.value = 'all'
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

const columns = allowedDepotColumns()
const views = allowedDepotViews()
const defaultColumns = DEFAULT_DEPOT_COLUMNS.filter((key) => columns.some((column) => column.key === key))
</script>

<template>
	<DataList
		ref="dataList"
		:state="state"
		:rows="state.depots.value"
		title="Dépôts"
		noun="dépôt"
		:create-label="canCreate('Warehouse') ? 'Nouveau dépôt' : undefined"
		search-label="Rechercher un dépôt"
		search-placeholder="Nom, groupe"
		:columns="columns"
		locked-column="depot"
		:default-columns="defaultColumns"
		list-id="depots"
		:views="views"
		:counts="state.response.value?.counts"
		default-sort-label="Ordre par nom"
		:sort-text="depotSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:created="created ?? undefined"
		:load-error="optionsError"
		doctype="Warehouse"
		:export-fields="fields"
		bulk-doctype="Warehouse"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
		@create="creating = true"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Warehouse" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'depot'" class="flex min-w-0 items-baseline gap-1.5" :title="row.depot"><span class="list-client truncate">{{ row.depot }}</span><StatusPill v-if="row.desactive" status="Désactivé" tone="gray" /></span>
				<span v-else-if="column.key === 'parent'" class="truncate">{{ row.parent || '—' }}</span>
				<span v-else-if="column.key === 'type'">{{ row.type || '—' }}</span>
				<span v-else-if="column.key === 'articles'" class="list-col-end tabular-nums" :class="!row.articles && 'text-ink-gray-6'">{{ row.articles ?? '—' }}</span>
				<span v-else-if="column.key === 'valeur'" class="list-col-end tabular-nums" :class="!row.valeur && 'text-ink-gray-6'">{{ formatAmount(row.valeur) }}</span>
				<span v-else-if="column.key === 'name'" class="tabular-nums text-ink-gray-7">{{ row.name }}</span>
				<span v-else-if="column.key === 'creation'" class="tabular-nums">{{ formatDay(row.creation) || '—' }}</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Ouvrir la fiche</button>
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('pick', row.name)">Aperçu</button>
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Warehouse', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>

		<DepotDialog v-if="creating" @close="creating = false" @created="onCreated" />
		<AppToast :message="created ? 'Dépôt créé.' : ''" :duration="0" @close="created = null">
			<button type="button" class="app-toast-action" @click="openCreated">Ouvrir la fiche</button>
		</AppToast>
	</DataList>
</template>
