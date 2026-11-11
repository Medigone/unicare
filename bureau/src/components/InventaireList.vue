<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import InventaireDialog from './InventaireDialog.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getInventaireOptions, getInventaires } from '@/lib/api'
import { formatAmount } from '@/lib/clients'
import { DEFAULT_INVENTAIRE_COLUMNS, INVENTAIRE_COLUMNS, INVENTAIRE_VIEWS, inventaireSortText, type InventaireOptions, type InventaireRow, type InventaireView } from '@/lib/inventaires'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { InventairesState } from '@/lib/useInventaires'

const props = defineProps<{ state: InventairesState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const dataList = ref<{ revealCreated: () => Promise<void> } | null>(null)
const options = ref<InventaireOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getInventaires(query.view as InventaireView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.inventaires as InventaireRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getInventaireOptions()
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

const columns = INVENTAIRE_COLUMNS
const defaultColumns = DEFAULT_INVENTAIRE_COLUMNS
</script>

<template>
	<DataList
		ref="dataList"
		:state="state"
		:rows="state.inventaires.value"
		title="Inventaires"
		noun="inventaire"
		:create-label="canCreate('Stock Reconciliation') ? 'Nouvel inventaire' : undefined"
		search-label="Rechercher un inventaire"
		search-placeholder="Numéro, dépôt"
		:columns="columns"
		locked-column="name"
		:default-columns="defaultColumns"
		list-id="inventaires"
		:views="INVENTAIRE_VIEWS"
		:counts="state.response.value?.counts"
		default-sort-label="Plus récents d'abord"
		:sort-text="inventaireSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:created="created ?? undefined"
		:load-error="optionsError"
		doctype="Stock Reconciliation"
		:export-fields="fields"
		bulk-doctype="Stock Reconciliation"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
		@create="creating = true"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Stock Reconciliation" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'name'" class="list-client tabular-nums">{{ row.name }}</span>
				<span v-else-if="column.key === 'status'"><StatusPill :status="row.status" /></span>
				<span v-else-if="column.key === 'date'" class="tabular-nums">{{ formatDay(row.date) || '—' }}</span>
				<span v-else-if="column.key === 'depot'" class="truncate">{{ row.depot || '—' }}</span>
				<span v-else-if="column.key === 'lignes'" class="list-col-end tabular-nums">{{ row.lignes }}</span>
				<span v-else-if="column.key === 'ecart'" class="list-col-end tabular-nums" :class="row.ecart === null ? 'text-ink-gray-6' : row.ecart < 0 ? 'text-tone-red' : row.ecart > 0 && 'text-tone-green'">{{ row.ecart === null ? '—' : formatAmount(row.ecart) }}</span>
				<span v-else-if="column.key === 'creation'" class="tabular-nums">{{ formatDay(row.creation) || '—' }}</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Ouvrir la fiche</button>
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('pick', row.name)">Aperçu</button>
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Stock Reconciliation', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>

		<InventaireDialog v-if="creating" @close="creating = false" @created="onCreated" />
		<AppToast :message="created ? 'Feuille de comptage préparée.' : ''" :duration="0" @close="created = null">
			<button type="button" class="app-toast-action" @click="openCreated">Ouvrir la fiche</button>
		</AppToast>
	</DataList>
</template>
