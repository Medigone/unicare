<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import FournisseurDialog from './FournisseurDialog.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getFournisseurOptions, getFournisseurs } from '@/lib/api'
import { allowedFournisseurColumns, allowedFournisseurViews, fournisseurSortText, DEFAULT_FOURNISSEUR_COLUMNS, formatAmount, type FournisseurOptions, type FournisseurRow, type FournisseurView } from '@/lib/fournisseurs'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { FournisseursState } from '@/lib/useFournisseurs'

const props = defineProps<{ state: FournisseursState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const dataList = ref<{ revealCreated: () => Promise<void> } | null>(null)
const options = ref<FournisseurOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getFournisseurs(query.view as FournisseurView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.fournisseurs as FournisseurRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getFournisseurOptions()
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

const columns = allowedFournisseurColumns()
const views = allowedFournisseurViews()
const defaultColumns = DEFAULT_FOURNISSEUR_COLUMNS.filter((key) => columns.some((column) => column.key === key))
</script>

<template>
	<DataList
		ref="dataList"
		:state="state"
		:rows="state.fournisseurs.value"
		title="Fournisseurs"
		noun="fournisseur"
		:create-label="canCreate('Supplier') ? 'Nouveau fournisseur' : undefined"
		search-label="Rechercher un fournisseur"
		search-placeholder="Nom, code, wilaya, catégorie"
		:columns="columns"
		locked-column="fournisseur"
		:default-columns="defaultColumns"
		list-id="fournisseurs"
		:views="views"
		:counts="state.response.value?.counts"
		default-sort-label="Ordre par nom"
		:sort-text="fournisseurSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:created="created ?? undefined"
		:load-error="optionsError"
		doctype="Supplier"
		:export-fields="fields"
		bulk-doctype="Supplier"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
		@create="creating = true"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Supplier" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'fournisseur'" class="flex min-w-0 items-baseline gap-1.5" :title="row.fournisseur">
					<span class="list-client truncate">{{ row.fournisseur }}</span>
				</span>
				<span v-else-if="column.key === 'status'"><StatusPill :status="row.status" /></span>
				<span v-else-if="column.key === 'categorie'">{{ row.categorie || '—' }}</span>
				<span v-else-if="column.key === 'wilaya'">{{ row.wilaya || '—' }}</span>
				<span v-else-if="column.key === 'contact'" :title="row.contact || undefined">{{ row.contact || '—' }}</span>
				<span v-else-if="column.key === 'telephone'" class="tabular-nums">{{ row.telephone || '—' }}</span>
				<span v-else-if="column.key === 'solde'" class="list-col-end tabular-nums" :class="!row.solde && 'text-ink-gray-6'">{{ formatAmount(row.solde) }}</span>
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
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Supplier', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>

		<FournisseurDialog v-if="creating" @close="creating = false" @created="onCreated" />
		<AppToast :message="created ? 'Fournisseur créé.' : ''" :duration="0" @close="created = null">
			<button type="button" class="app-toast-action" @click="openCreated">Ouvrir la fiche</button>
		</AppToast>
	</DataList>
</template>
