<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import MouvementDialog from './MouvementDialog.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getMouvementOptions, getMouvements } from '@/lib/api'
import { formatAmount } from '@/lib/clients'
import { DEFAULT_MOUVEMENT_COLUMNS, MOUVEMENT_COLUMNS, MOUVEMENT_VIEWS, mouvementSortText, natureLabel, type MouvementOptions, type MouvementRow, type MouvementView } from '@/lib/mouvements'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { MouvementsState } from '@/lib/useMouvements'

const props = defineProps<{ state: MouvementsState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const dataList = ref<{ revealCreated: () => Promise<void> } | null>(null)
const options = ref<MouvementOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getMouvements(query.view as MouvementView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.mouvements as MouvementRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getMouvementOptions()
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

const columns = MOUVEMENT_COLUMNS
const defaultColumns = DEFAULT_MOUVEMENT_COLUMNS
</script>

<template>
	<DataList
		ref="dataList"
		:state="state"
		:rows="state.mouvements.value"
		title="Mouvements de stock"
		noun="mouvement"
		:create-label="canCreate('Stock Entry') ? 'Nouveau mouvement' : undefined"
		search-label="Rechercher un mouvement"
		search-placeholder="Numéro, dépôt, remarque, ordre"
		:columns="columns"
		locked-column="name"
		:default-columns="defaultColumns"
		list-id="mouvements"
		:views="MOUVEMENT_VIEWS"
		:counts="state.response.value?.counts"
		default-sort-label="Plus récents d'abord"
		:sort-text="mouvementSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:created="created ?? undefined"
		:load-error="optionsError"
		doctype="Stock Entry"
		:export-fields="fields"
		bulk-doctype="Stock Entry"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
		@create="creating = true"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Stock Entry" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'name'" class="flex min-w-0 items-baseline gap-1.5"><span class="list-client tabular-nums">{{ row.name }}</span><span v-if="row.ordre" class="record-flag" :title="`Créé par l'ordre ${row.ordre}`">Ordre</span></span>
				<span v-else-if="column.key === 'nature'">{{ natureLabel(row.nature) }}</span>
				<span v-else-if="column.key === 'status'"><StatusPill :status="row.status" /></span>
				<span v-else-if="column.key === 'date'" class="tabular-nums">{{ formatDay(row.date) || '—' }}</span>
				<span v-else-if="column.key === 'source'" class="truncate">{{ row.source || '—' }}</span>
				<span v-else-if="column.key === 'cible'" class="truncate">{{ row.cible || '—' }}</span>
				<span v-else-if="column.key === 'articles'" class="truncate" :title="row.articles">{{ row.articles || '—' }}</span>
				<span v-else-if="column.key === 'valeur'" class="list-col-end tabular-nums">{{ formatAmount(row.valeur) }}</span>
				<span v-else-if="column.key === 'remarque'" class="truncate" :title="row.remarque || undefined">{{ row.remarque || '—' }}</span>
				<span v-else-if="column.key === 'creation'" class="tabular-nums">{{ formatDay(row.creation) || '—' }}</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Ouvrir la fiche</button>
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('pick', row.name)">Aperçu</button>
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Stock Entry', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>

		<MouvementDialog v-if="creating" @close="creating = false" @created="onCreated" />
		<AppToast :message="created ? 'Mouvement créé en brouillon.' : ''" :duration="0" @close="created = null">
			<button type="button" class="app-toast-action" @click="openCreated">Ouvrir la fiche</button>
		</AppToast>
	</DataList>
</template>
