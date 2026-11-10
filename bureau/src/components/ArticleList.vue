<script setup lang="ts">
import { fieldCellText } from '@/lib/listViews'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import AppToast from './AppToast.vue'
import ArticleDialog from './ArticleDialog.vue'
import DataList from './DataList.vue'
import FilterBuilder from './FilterBuilder.vue'
import TagCell from './TagCell.vue'
import { getArticleOptions, getArticles } from '@/lib/api'
import { allowedArticleColumns, ARTICLE_VIEWS, articleSortText, DEFAULT_ARTICLE_COLUMNS, formatQty, STOCK_DOCTYPE, type ArticleOptions, type ArticleRow, type ArticleView } from '@/lib/articles'
import { canCreate, canRead } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { describeCondition, type Condition } from '@/lib/filters'
import type { ExportQuery } from '@/lib/exports'
import type { ArticlesState } from '@/lib/useArticles'

const props = defineProps<{ state: ArticlesState; selected?: string }>()
const emit = defineEmits<{ pick: [name?: string]; open: [name: string]; changed: [] }>()

const dataList = ref<{ revealCreated: () => Promise<void> } | null>(null)
const options = ref<ArticleOptions | null>(null)
const optionsError = ref('')
const fields = computed(() => options.value?.filter_fields ?? [])
const labelOf = (condition: Condition) => describeCondition(condition, fields.value)
async function fetchRows(query: ExportQuery, start: number, pageLength: number) {
	const state = props.state
	const response = await getArticles(query.view as ArticleView, query.conditions, query.search, { start, pageLength, sort: state.sort.value?.key, direction: state.sort.value?.dir })
	return { rows: response.articles as ArticleRow[], total: response.total }
}

onMounted(async () => {
	try {
		options.value = await getArticleOptions()
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

const columns = allowedArticleColumns(canRead(STOCK_DOCTYPE))
const defaultColumns = DEFAULT_ARTICLE_COLUMNS.filter((key) => columns.some((column) => column.key === key))
</script>

<template>
	<DataList
		ref="dataList"
		:state="state"
		:rows="state.articles.value"
		title="Articles"
		noun="article"
		:create-label="canCreate('Item') ? 'Nouvel article' : undefined"
		search-label="Rechercher un article"
		search-placeholder="Désignation, code, groupe"
		:columns="columns"
		locked-column="designation"
		:default-columns="defaultColumns"
		list-id="articles"
		:views="ARTICLE_VIEWS"
		:counts="state.response.value?.counts"
		default-sort-label="Ordre par désignation"
		:sort-text="articleSortText(state.sort.value)"
		:condition-label="labelOf"
		:fetch-rows="fetchRows"
		:selected="selected"
		:created="created ?? undefined"
		:load-error="optionsError"
		doctype="Item"
		:export-fields="fields"
		bulk-doctype="Item"
		@pick="emit('pick', $event)"
		@open="emit('open', $event)"
		@changed="emit('changed')"
		@create="creating = true"
	>
		<template #filters="{ conditions, update, canSave }">
			<FilterBuilder :model-value="conditions" :fields="fields" doctype="Item" :can-save="canSave" @update:model-value="update" />
		</template>

		<template #cells="{ row, columns }">
			<template v-for="column in columns" :key="column.key">
				<span v-if="column.key === 'designation'" class="flex min-w-0 items-baseline gap-1.5" :title="row.designation">
					<span class="list-client truncate">{{ row.designation }}</span>
					<span v-if="row.disabled" class="record-flag">Désactivé</span>
				</span>
				<span v-else-if="column.key === 'name'" class="tabular-nums text-ink-gray-7">{{ row.name }}</span>
				<span v-else-if="column.key === 'type'">{{ row.type || '—' }}</span>
				<span v-else-if="column.key === 'groupe'" :title="row.groupe || undefined">{{ row.groupe || '—' }}</span>
				<span v-else-if="column.key === 'stock'" class="list-col-end tabular-nums" :class="!row.stock && 'text-ink-gray-6'">{{ row.stock === null ? '—' : formatQty(row.stock) }}</span>
				<span v-else-if="column.key === 'uom'">{{ row.uom || '—' }}</span>
				<span v-else-if="column.key === 'lots'">{{ row.lots ? 'Oui' : 'Non' }}</span>
				<span v-else-if="column.key === 'creation'" class="tabular-nums">{{ formatDay(row.creation) || '—' }}</span>
				<span v-else-if="column.key === 'modified'" class="tabular-nums">{{ formatDay(row.modified) || '—' }}</span>
				<TagCell v-else-if="column.key === 'tags'" :tags="row.tags" :max="2" />
				<span v-else :class="column.end && 'list-col-end tabular-nums'" :title="String(column.text(row))">{{ fieldCellText(column, row) }}</span>
			</template>
		</template>

		<template #rowMenu="{ row }">
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('open', row.name)">Ouvrir la fiche</button>
			<button type="button" class="app-menu-item" role="menuitem" @click="emit('pick', row.name)">Aperçu</button>
			<a class="app-menu-item" role="menuitem" :href="deskUrl('Item', row.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
		</template>

		<template #drawer><slot name="drawer"></slot></template>

		<ArticleDialog v-if="creating" @close="creating = false" @created="onCreated" />
		<AppToast :message="created ? 'Article créé.' : ''" :duration="0" @close="created = null">
			<button type="button" class="app-toast-action" @click="openCreated">Ouvrir la fiche</button>
		</AppToast>
	</DataList>
</template>
