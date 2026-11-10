<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getFactureOptions, getFactures } from '@/lib/api'
import { formatAmount } from '@/lib/clients'
import { dayFromToday } from '@/lib/devis'
import { DEFAULT_FACTURE_COLUMNS, FACTURE_COLUMNS, FACTURE_VIEWS, factureSortText, factureStatus, factureTone, type FactureRow, type FactureView } from '@/lib/factures'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition, type FilterField } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { FacturesState } from '@/lib/useFactures'

const props = defineProps<{ state: FacturesState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const options = ref<{ filter_fields?: FilterField[] } | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getFactures(query.view as FactureView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.factures as FactureRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getFactureOptions()
	} catch (e) {
		optionsError.value = (e as Error).message
	}
})

// Une échéance passée sur une facture impayée se signale en rouge.
const today = dayFromToday(0)
const columns = FACTURE_COLUMNS
const defaultColumns = DEFAULT_FACTURE_COLUMNS
</script>

<template>
	<DataList
		:state="state"
		:rows="state.factures.value"
		title="Factures"
		noun="facture"
		search-label="Rechercher une facture"
		search-placeholder="Numéro, client"
		:columns="columns"
		locked-column="name"
		:default-columns="defaultColumns"
		list-id="factures"
		:views="FACTURE_VIEWS"
		:counts="state.response.value?.counts"
		default-sort-label="Plus récentes d'abord"
		:sort-text="factureSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:load-error="optionsError"
		doctype="Sales Invoice"
		:export-fields="fields"
		bulk-doctype="Sales Invoice"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Sales Invoice" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'name'" class="flex min-w-0 items-baseline gap-1.5"><span class="list-client tabular-nums">{{ row.name }}</span><span v-if="row.avoir" class="record-flag">Avoir</span></span>
				<span v-else-if="column.key === 'client_label'" class="truncate" :title="row.client_label">{{ row.client_label }}</span>
				<span v-else-if="column.key === 'status'"><StatusPill :status="factureStatus(row.status)" :tone="factureTone(row.status)" /></span>
				<span v-else-if="column.key === 'echeance'" class="tabular-nums" :class="row.echeance && row.echeance < today && row.reste > 0 && 'font-semibold text-tone-red'">{{ formatDay(row.echeance) || '—' }}</span>
				<span v-else-if="column.key === 'reste'" class="list-col-end tabular-nums" :class="!row.reste && 'text-ink-gray-6'">{{ formatAmount(row.reste) }}</span>
				<span v-else-if="column.key === 'date'" class="tabular-nums">{{ formatDay(row.date) || '—' }}</span>
				<span v-else-if="column.key === 'commandes'" class="truncate tabular-nums">{{ row.commandes || '—' }}</span>
				<span v-else-if="column.key === 'livraisons'" class="truncate tabular-nums">{{ row.avoir_de ? `Avoir sur ${row.avoir_de}` : row.livraisons || '—' }}</span>
				<span v-else-if="column.key === 'total_ttc'" class="list-col-end tabular-nums">{{ formatAmount(row.total_ttc) }}</span>
				<span v-else-if="column.key === 'creation'" class="tabular-nums">{{ formatDay(row.creation) || '—' }}</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Ouvrir la fiche</button>
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('pick', row.name)">Aperçu</button>
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Sales Invoice', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>
	</DataList>
</template>
