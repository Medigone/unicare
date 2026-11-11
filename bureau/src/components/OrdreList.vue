<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import OrdreDialog from './OrdreDialog.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getOrdreOptions, getOrdres } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { DEFAULT_ORDRE_COLUMNS, DEFAULT_ORDRE_VIEW, echeanceText, ETAPE_TONES, ORDRE_COLUMNS, ORDRE_VIEWS, ordreSortText, type OrdreOptions, type OrdreRow, type OrdreView } from '@/lib/ordres'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { OrdresState } from '@/lib/useOrdres'

const props = defineProps<{ state: OrdresState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const dataList = ref<{ revealCreated: () => Promise<void> } | null>(null)
const options = ref<OrdreOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getOrdres(query.view as OrdreView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.ordres as OrdreRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getOrdreOptions()
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
	state.view.value = DEFAULT_ORDRE_VIEW
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

const columns = ORDRE_COLUMNS
const defaultColumns = DEFAULT_ORDRE_COLUMNS
</script>

<template>
	<DataList
		ref="dataList"
		:state="state"
		:rows="state.ordres.value"
		title="Ordres de production"
		noun="ordre"
		:create-label="canCreate('Ordre de Conditionnement') ? 'Nouvel ordre' : undefined"
		search-label="Rechercher un ordre"
		search-placeholder="Ordre, produit, lot"
		:columns="columns"
		locked-column="name"
		:default-columns="defaultColumns"
		list-id="ordres"
		:views="ORDRE_VIEWS"
		:counts="state.response.value?.counts"
		default-sort-label="Plus récents d'abord"
		:sort-text="ordreSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:created="created ?? undefined"
		:load-error="optionsError"
		doctype="Ordre de Conditionnement"
		:export-fields="fields"
		bulk-doctype="Ordre de Conditionnement"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
		@create="creating = true"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Ordre de Conditionnement" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'name'" class="list-client tabular-nums">{{ row.name }}</span>
				<span v-else-if="column.key === 'designation'" class="truncate" :title="row.designation">{{ row.designation }}</span>
				<span v-else-if="column.key === 'etape'"><StatusPill :status="row.etape" :tone="ETAPE_TONES[row.state]" /></span>
				<span v-else-if="column.key === 'date_prevue'" class="tabular-nums" :class="row.retard && 'font-medium text-tone-red'">{{ echeanceText(row.date_prevue, row.retard) }}</span>
				<span v-else-if="column.key === 'qty_prevue'" class="list-col-end tabular-nums">{{ formatQty(row.qty_prevue) }} <span class="text-xs text-ink-gray-6">{{ row.unite }}</span></span>
				<span v-else-if="column.key === 'qty_reelle'" class="list-col-end tabular-nums" :class="row.qty_reelle === null && 'text-ink-gray-6'">{{ row.qty_reelle === null ? '—' : formatQty(row.qty_reelle) }}</span>
				<span v-else-if="column.key === 'rendement'" class="tabular-nums" :class="row.rendement === null && 'text-ink-gray-6'">{{ row.rendement === null ? '—' : `${String(row.rendement).replace('.', ',')} %` }}</span>
				<span v-else-if="column.key === 'lot_pf'" class="truncate tabular-nums" :class="!row.lot_pf && 'text-ink-gray-6'">{{ row.lot_pf || '—' }}</span>
				<span v-else-if="column.key === 'creation'" class="tabular-nums">{{ formatDay(row.creation) || '—' }}</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Ouvrir la fiche</button>
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('pick', row.name)">Aperçu</button>
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Ordre de Conditionnement', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>

		<OrdreDialog v-if="creating" @close="creating = false" @created="onCreated" />
		<AppToast :message="created ? 'Ordre créé : il est à planifier.' : ''" :duration="0" @close="created = null">
			<button type="button" class="app-toast-action" @click="openCreated">Ouvrir la fiche</button>
		</AppToast>
	</DataList>
</template>
