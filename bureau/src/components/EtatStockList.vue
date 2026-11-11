<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, onMounted, ref } from 'vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getEtatStock, getEtatStockOptions } from '@/lib/api'
import { formatAmount } from '@/lib/clients'
import { formatQty } from '@/lib/articles'
import { DEFAULT_ETAT_STOCK_COLUMNS, ETAT_STOCK_COLUMNS, ETAT_STOCK_VIEWS, etatStockSortText, niveauStock, type EtatStockOptions, type EtatStockView, type LigneStock } from '@/lib/etatStock'
import { formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { EtatStockState } from '@/lib/useEtatStock'

const props = defineProps<{ state: EtatStockState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const options = ref<EtatStockOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getEtatStock(query.view as EtatStockView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.lignes as LigneStock[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getEtatStockOptions()
	} catch (e) {
		optionsError.value = (e as Error).message
	}
})

const columns = ETAT_STOCK_COLUMNS
const views = ETAT_STOCK_VIEWS
const defaultColumns = DEFAULT_ETAT_STOCK_COLUMNS.filter((key) => columns.some((column) => column.key === key))
</script>

<template>
	<DataList
		:state="state"
		:rows="state.lignes.value"
		title="État du stock"
		noun="ligne"
				search-label="Rechercher un article ou un dépôt"
		search-placeholder="Article, code, dépôt, groupe"
		:columns="columns"
		locked-column="designation"
		:default-columns="defaultColumns"
		list-id="etat-stock"
		:views="views"
		:counts="state.response.value?.counts"
		default-sort-label="Ordre par article"
		:sort-text="etatStockSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:load-error="optionsError"
		doctype="Bin"
		:export-fields="fields"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Bin" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'designation'" class="flex min-w-0 items-baseline gap-1.5" :title="row.designation"><span class="list-client truncate">{{ row.designation }}</span><span class="text-xs tabular-nums text-ink-gray-6">{{ row.article }}</span></span>
				<span v-else-if="column.key === 'depot'" class="truncate">{{ row.depot }}</span>
				<span v-else-if="column.key === 'quantite'" class="list-col-end tabular-nums" :class="{ 'font-semibold text-tone-red': niveauStock(row) === 'negatif' || niveauStock(row) === 'rupture', 'font-semibold text-tone-amber': niveauStock(row) === 'bas' }">{{ formatQty(row.quantite) }} <span class="text-xs font-normal text-ink-gray-6">{{ row.unite }}</span></span>
				<span v-else-if="column.key === 'reserve'" class="list-col-end tabular-nums" :class="!row.reserve && 'text-ink-gray-6'">{{ formatQty(row.reserve) }}</span>
				<span v-else-if="column.key === 'projete'" class="list-col-end tabular-nums">{{ formatQty(row.projete) }}</span>
				<span v-else-if="column.key === 'commande'" class="list-col-end tabular-nums" :class="!row.commande && 'text-ink-gray-6'">{{ formatQty(row.commande) }}</span>
				<span v-else-if="column.key === 'seuil'" class="list-col-end tabular-nums" :class="row.seuil === null && 'text-ink-gray-6'">{{ row.seuil === null ? '—' : formatQty(row.seuil) }}</span>
				<span v-else-if="column.key === 'valeur'" class="list-col-end tabular-nums">{{ formatAmount(row.valeur) }}</span>
				<span v-else-if="column.key === 'groupe'" class="truncate">{{ row.groupe || '—' }}</span>
				<span v-else-if="column.key === 'article'" class="tabular-nums text-ink-gray-7">{{ row.article }}</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Ouvrir la fiche</button>
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('pick', row.name)">Aperçu</button>
			<RouterLink class="app-menu-item" role="menuitem" :to="{ name: 'Article', params: { id: row.article } }">Fiche de l'article</RouterLink>
			<RouterLink class="app-menu-item" role="menuitem" :to="{ name: 'Depot', params: { id: row.depot } }">Fiche du dépôt</RouterLink>
		</template>

		<template #drawer><slot name="drawer"></slot></template>

	</DataList>
</template>
