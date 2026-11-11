<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getLotOptions, getLots } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { DEFAULT_LOT_COLUMNS, etatPeremption, LOT_COLUMNS, LOT_VIEWS, lotSortText, type LotOptions, type LotRow, type LotView } from '@/lib/lots'
import { dayFromToday } from '@/lib/devis'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { LotsState } from '@/lib/useLots'

const props = defineProps<{ state: LotsState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const options = ref<LotOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getLots(query.view as LotView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.lots as LotRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getLotOptions()
	} catch (e) {
		optionsError.value = (e as Error).message
	}
})

const today = dayFromToday(0)
const columns = LOT_COLUMNS
const views = LOT_VIEWS
const defaultColumns = DEFAULT_LOT_COLUMNS.filter((key) => columns.some((column) => column.key === key))
</script>

<template>
	<DataList
		:state="state"
		:rows="state.lots.value"
		title="Lots"
		noun="lot"
				search-label="Rechercher un lot"
		search-placeholder="Lot, article, lot fournisseur"
		:columns="columns"
		locked-column="name"
		:default-columns="defaultColumns"
		list-id="lots"
		:views="views"
		:counts="state.response.value?.counts"
		default-sort-label="Plus récents d'abord"
		:sort-text="lotSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:load-error="optionsError"
		doctype="Batch"
		:export-fields="fields"
		bulk-doctype="Batch"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Batch" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'name'" class="flex min-w-0 items-baseline gap-1.5"><span class="list-client truncate tabular-nums">{{ row.name }}</span><StatusPill v-if="row.desactive" status="Désactivé" tone="gray" /></span>
				<span v-else-if="column.key === 'designation'" class="truncate" :title="row.designation">{{ row.designation }}</span>
				<span v-else-if="column.key === 'quantite'" class="list-col-end tabular-nums" :class="row.quantite <= 0 && 'text-ink-gray-6'">{{ formatQty(row.quantite) }} <span class="text-xs text-ink-gray-6">{{ row.unite }}</span></span>
				<span v-else-if="column.key === 'peremption'" class="tabular-nums" :class="{ 'font-semibold text-tone-red': etatPeremption(row, 30, today) === 'perime', 'font-semibold text-tone-amber': etatPeremption(row, 30, today) === 'proche' }">{{ formatDay(row.peremption) || '—' }}</span>
				<span v-else-if="column.key === 'origine'">{{ row.origine || '—' }}</span>
				<span v-else-if="column.key === 'lot_fournisseur'" class="truncate tabular-nums">{{ row.lot_fournisseur || '—' }}</span>
				<span v-else-if="column.key === 'fabrication'" class="tabular-nums">{{ formatDay(row.fabrication) || '—' }}</span>
				<span v-else-if="column.key === 'creation'" class="tabular-nums">{{ formatDay(row.creation) || '—' }}</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Ouvrir la fiche</button>
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('pick', row.name)">Aperçu</button>
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Batch', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>

	</DataList>
</template>
