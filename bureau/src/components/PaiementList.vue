<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideArrowDownLeft from '~icons/lucide/arrow-down-left'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import PaiementAssistant from './PaiementAssistant.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getPaiementOptions, getPaiements } from '@/lib/api'
import { formatAmount } from '@/lib/clients'
import { DEFAULT_PAIEMENT_COLUMNS, PAIEMENT_COLUMNS, PAIEMENT_STATUS, PAIEMENT_VIEWS, paiementSortText, type PaiementOptions, type PaiementRow, type PaiementView } from '@/lib/paiements'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { PaiementsState } from '@/lib/usePaiements'

const props = defineProps<{ state: PaiementsState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const dataList = ref<{ revealCreated: () => Promise<void> } | null>(null)
const options = ref<PaiementOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getPaiements(query.view as PaiementView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.paiements as PaiementRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getPaiementOptions()
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

const columns = PAIEMENT_COLUMNS
const defaultColumns = DEFAULT_PAIEMENT_COLUMNS
</script>

<template>
	<DataList
		ref="dataList"
		:state="state"
		:rows="state.paiements.value"
		title="Paiements"
		noun="paiement"
		:create-label="options?.can_create ? 'Nouveau paiement' : undefined"
		search-label="Rechercher un paiement"
		search-placeholder="Numéro, tiers, référence"
		:columns="columns"
		locked-column="name"
		:default-columns="defaultColumns"
		list-id="paiements"
		:views="PAIEMENT_VIEWS"
		:counts="state.response.value?.counts"
		default-sort-label="Plus récents d'abord"
		:sort-text="paiementSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:created="created ?? undefined"
		:load-error="optionsError"
		doctype="Payment Entry"
		:export-fields="fields"
		bulk-doctype="Payment Entry"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
		@create="creating = true"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Payment Entry" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'name'" class="list-client tabular-nums">{{ row.name }}</span>
				<span v-else-if="column.key === 'type_label'" class="flex min-w-0 items-center gap-1.5">
					<component :is="row.sens === 'Receive' ? LucideArrowDownLeft : LucideArrowUpRight" class="h-3.5 w-3.5 flex-none" :class="row.sens === 'Receive' ? 'text-tone-green' : 'text-tone-amber'" aria-hidden="true" />
					<span class="truncate">{{ row.type_label }}</span>
				</span>
				<span v-else-if="column.key === 'tiers_label'" class="truncate" :title="row.tiers_label">{{ row.tiers_label }}</span>
				<span v-else-if="column.key === 'date'" class="tabular-nums">{{ formatDay(row.date) || '—' }}</span>
				<span v-else-if="column.key === 'mode'">{{ row.mode || '—' }}</span>
				<span v-else-if="column.key === 'montant'" class="list-col-end tabular-nums">{{ row.sens === 'Pay' ? '−' : '' }}{{ formatAmount(row.montant) }}</span>
				<span v-else-if="column.key === 'non_affecte'" class="list-col-end tabular-nums" :class="!row.non_affecte && 'text-ink-gray-6'">{{ formatAmount(row.non_affecte) }}</span>
				<span v-else-if="column.key === 'status'"><StatusPill :status="PAIEMENT_STATUS[row.status]" :tone="row.status === 'Submitted' ? 'green' : row.status === 'Draft' ? 'amber' : 'gray'" /></span>
				<span v-else-if="column.key === 'reference'">{{ row.reference || '—' }}</span>
				<span v-else-if="column.key === 'creation'" class="tabular-nums">{{ formatDay(row.creation) || '—' }}</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Ouvrir la fiche</button>
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('pick', row.name)">Aperçu</button>
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Payment Entry', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>

		<PaiementAssistant v-if="creating" @close="creating = false" @created="onCreated" />
		<AppToast :message="created ? 'Paiement créé en brouillon : relisez-le puis validez-le.' : ''" :duration="0" @close="created = null">
			<button type="button" class="app-toast-action" @click="openCreated">Ouvrir la fiche</button>
		</AppToast>
	</DataList>
</template>
