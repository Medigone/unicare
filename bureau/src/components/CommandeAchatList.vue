<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import AchatDialog from './AchatDialog.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getCommandeAchatOptions, getCommandesAchat } from '@/lib/api'
import { formatAmount } from '@/lib/clients'
import { dayFromToday } from '@/lib/devis'
import { A_RECEVOIR, COMMANDE_ACHAT_COLUMNS, COMMANDE_ACHAT_VIEWS, commandeAchatSortText, DEFAULT_COMMANDE_ACHAT_COLUMNS, formatPercent, type CommandeAchatOptions, type CommandeAchatRow, type CommandeAchatView } from '@/lib/commandesAchat'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { CommandesAchatState } from '@/lib/useCommandesAchat'

const props = defineProps<{ state: CommandesAchatState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const dataList = ref<{ revealCreated: () => Promise<void> } | null>(null)
const options = ref<CommandeAchatOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getCommandesAchat(query.view as CommandeAchatView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.commandes as CommandeAchatRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getCommandeAchatOptions()
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

// Une réception passée et pas encore faite se signale en rouge.
const today = dayFromToday(0)
const columns = COMMANDE_ACHAT_COLUMNS
const defaultColumns = DEFAULT_COMMANDE_ACHAT_COLUMNS
</script>

<template>
	<DataList
		ref="dataList"
		:state="state"
		:rows="state.commandes.value"
		title="Commandes d'achat"
		noun="commande"
		:create-label="canCreate('Purchase Order') ? 'Nouvelle commande d\'achat' : undefined"
		search-label="Rechercher une commande d'achat"
		search-placeholder="Numéro, fournisseur"
		:columns="columns"
		locked-column="name"
		:default-columns="defaultColumns"
		list-id="commandes-achat"
		:views="COMMANDE_ACHAT_VIEWS"
		:counts="state.response.value?.counts"
		default-sort-label="Plus récentes d'abord"
		:sort-text="commandeAchatSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:created="created ?? undefined"
		:load-error="optionsError"
		doctype="Purchase Order"
		:export-fields="fields"
		bulk-doctype="Purchase Order"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
		@create="creating = true"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Purchase Order" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'name'" class="list-client tabular-nums">{{ row.name }}</span>
				<span v-else-if="column.key === 'fournisseur_label'" class="truncate" :title="row.fournisseur_label">{{ row.fournisseur_label }}</span>
				<span v-else-if="column.key === 'status'"><StatusPill :status="row.status" /></span>
				<span v-else-if="column.key === 'date'" class="tabular-nums">{{ formatDay(row.date) || '—' }}</span>
				<span v-else-if="column.key === 'reception'" class="tabular-nums" :class="row.reception && row.reception < today && A_RECEVOIR.includes(row.status) && 'font-semibold text-tone-red'">{{ formatDay(row.reception) || '—' }}</span>
				<span v-else-if="column.key === 'recu'" class="list-col-end tabular-nums" :class="!row.recu && 'text-ink-gray-6'">{{ formatPercent(row.recu) }}</span>
				<span v-else-if="column.key === 'facture'" class="list-col-end tabular-nums" :class="!row.facture && 'text-ink-gray-6'">{{ formatPercent(row.facture) }}</span>
				<span v-else-if="column.key === 'devis'" class="tabular-nums">{{ row.devis || '—' }}</span>
				<span v-else-if="column.key === 'total_ttc'" class="list-col-end tabular-nums">{{ formatAmount(row.total_ttc) }}</span>
				<span v-else-if="column.key === 'total'" class="list-col-end tabular-nums">{{ formatAmount(row.total) }}</span>
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
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Purchase Order', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>

		<AchatDialog v-if="creating" kind="commande" @close="creating = false" @created="onCreated" />
		<AppToast :message="created ? 'Commande d\'achat créée.' : ''" :duration="0" @close="created = null">
			<button type="button" class="app-toast-action" @click="openCreated">Ouvrir la fiche</button>
		</AppToast>
	</DataList>
</template>
