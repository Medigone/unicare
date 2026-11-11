<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getReceptionOptions, getReceptions } from '@/lib/api'
import { formatAmount } from '@/lib/clients'
import { formatPercent } from '@/lib/commandes'
import { DEFAULT_RECEPTION_COLUMNS, RECEPTION_COLUMNS, RECEPTION_VIEWS, receptionSortText, type ReceptionRow, type ReceptionView } from '@/lib/receptions'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition, type FilterField } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { ReceptionsState } from '@/lib/useReceptions'

const props = defineProps<{ state: ReceptionsState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const options = ref<{ filter_fields?: FilterField[] } | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getReceptions(query.view as ReceptionView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.receptions as ReceptionRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getReceptionOptions()
	} catch (e) {
		optionsError.value = (e as Error).message
	}
})

const columns = RECEPTION_COLUMNS
const defaultColumns = DEFAULT_RECEPTION_COLUMNS
</script>

<template>
	<DataList
		:state="state"
		:rows="state.receptions.value"
		title="Réceptions"
		noun="réception"
		search-label="Rechercher une réception"
		search-placeholder="Numéro, fournisseur, BL fournisseur"
		:columns="columns"
		locked-column="name"
		:default-columns="defaultColumns"
		list-id="receptions"
		:views="RECEPTION_VIEWS"
		:counts="state.response.value?.counts"
		default-sort-label="Plus récentes d'abord"
		:sort-text="receptionSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:load-error="optionsError"
		doctype="Purchase Receipt"
		:export-fields="fields"
		bulk-doctype="Purchase Receipt"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Purchase Receipt" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'name'" class="flex min-w-0 items-baseline gap-1.5"><span class="list-client tabular-nums">{{ row.name }}</span><span v-if="row.retour" class="record-flag">Retour</span></span>
				<span v-else-if="column.key === 'fournisseur_label'" class="truncate" :title="row.fournisseur_label">{{ row.fournisseur_label }}</span>
				<span v-else-if="column.key === 'status'"><StatusPill :status="row.status" /></span>
				<span v-else-if="column.key === 'date'" class="tabular-nums">{{ formatDay(row.date) || '—' }}</span>
				<span v-else-if="column.key === 'facture'" class="list-col-end tabular-nums" :class="!row.facture && 'text-ink-gray-6'">{{ formatPercent(row.facture) }}</span>
				<span v-else-if="column.key === 'bl_fournisseur'" class="tabular-nums">{{ row.bl_fournisseur || '—' }}</span>
				<span v-else-if="column.key === 'commandes'" class="truncate tabular-nums" :title="row.commandes || undefined">{{ row.retour_de ? `Retour de ${row.retour_de}` : row.commandes || '—' }}</span>
				<span v-else-if="column.key === 'total_ttc'" class="list-col-end tabular-nums">{{ formatAmount(row.total_ttc) }}</span>
				<span v-else-if="column.key === 'articles'" class="truncate" :title="row.articles">{{ row.articles || '—' }}</span>
				<span v-else-if="column.key === 'creation'" class="tabular-nums">{{ formatDay(row.creation) || '—' }}</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Ouvrir la fiche</button>
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('pick', row.name)">Aperçu</button>
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Purchase Receipt', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>
	</DataList>
</template>
