<script setup lang="ts" generic="Choice extends { name: string; label: string; hint?: string | null }">
import { nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import LucidePlus from '~icons/lucide/plus'
import LucideSearch from '~icons/lucide/search'
import LucideX from '~icons/lucide/x'

/** Choix d'un document cherché sur le serveur (client, article). Une seule réponse compte, celle de la dernière frappe. */
const props = defineProps<{
	search: (query: string) => Promise<Choice[]>
	/** Libellé du choix en cours ; vide : la recherche est affichée. */
	picked?: string
	inputId: string
	placeholder?: string
	invalid?: boolean
	compact?: boolean
	/** Libellé de l'option de création, en fin de liste (« Créer le client ») ; absent : pas de création. */
	createLabel?: string
}>()
const emit = defineEmits<{ pick: [choice: Choice]; clear: []; create: [query: string] }>()

const query = ref('')
const choices = shallowRef<Choice[]>([])
const open = ref(false)
const searched = ref(false)
const cursor = ref(0)
const error = ref('')
const input = ref<HTMLInputElement | null>(null)
let last = 0
let timer: ReturnType<typeof setTimeout> | null = null

async function run() {
	const request = ++last
	try {
		const found = await props.search(query.value)
		if (request !== last) return
		choices.value = found
		searched.value = true
		error.value = ''
		cursor.value = 0
	} catch (e) {
		if (request === last) error.value = (e as Error).message
	}
}
watch(query, () => {
	open.value = true
	if (timer) clearTimeout(timer)
	timer = setTimeout(run, 200)
})
function show() {
	open.value = true
	if (!searched.value) run()
}
// L'option de création suit les résultats : sans résultat, c'est elle que choisit Entrée.
const canCreate = () => Boolean(props.createLabel && searched.value)
function create() {
	open.value = false
	emit('create', query.value.trim())
}
function pick(choice?: Choice) {
	if (!choice) {
		if (canCreate() && cursor.value === choices.value.length) create()
		return
	}
	open.value = false
	emit('pick', choice)
}
async function clear() {
	query.value = ''
	searched.value = false
	emit('clear')
	await nextTick()
	input.value?.focus()
}
function onKey(event: KeyboardEvent) {
	if (event.key === 'Escape' && open.value) {
		event.stopPropagation()
		open.value = false
	} else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
		event.preventDefault()
		const count = choices.value.length + (canCreate() ? 1 : 0)
		if (count) cursor.value = (cursor.value + (event.key === 'ArrowDown' ? 1 : count - 1)) % count
		open.value = true
	} else if (event.key === 'Enter' && !event.ctrlKey && !event.metaKey && open.value) {
		event.preventDefault()
		pick(choices.value[cursor.value])
	}
}
function onBlur(event: FocusEvent) {
	if (!(event.relatedTarget as HTMLElement | null)?.closest?.('.picker-menu')) open.value = false
}
onBeforeUnmount(() => {
	if (timer) clearTimeout(timer)
})
</script>

<template>
	<div v-if="picked" class="picked" :class="compact && 'py-1'">
		<strong class="min-w-0 flex-auto truncate font-semibold text-ink-gray-9" :title="picked">{{ picked }}</strong>
		<button :id="inputId" type="button" class="comment-tool" aria-label="Changer" title="Changer" @click="clear"><LucideX class="h-3.5 w-3.5" aria-hidden="true" /></button>
	</div>
	<div v-else class="relative">
		<LucideSearch class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-gray-5" aria-hidden="true" />
		<input
			:id="inputId"
			ref="input"
			v-model="query"
			class="field-input pl-8"
			type="search"
			:placeholder="placeholder ?? 'Rechercher'"
			autocomplete="off"
			role="combobox"
			aria-autocomplete="list"
			:aria-expanded="open"
			:aria-invalid="invalid"
			@focus="show"
			@click="show"
			@keydown="onKey"
			@blur="onBlur"
		/>
		<div v-if="open" class="app-menu picker-menu" role="listbox">
			<button v-for="(choice, index) in choices" :key="choice.name" type="button" class="app-menu-item" role="option" :aria-selected="index === cursor" @mousedown.prevent @click="pick(choice)" @pointerenter="cursor = index">
				<span class="min-w-0 flex-auto truncate">{{ choice.label }}</span>
				<span v-if="choice.hint" class="text-xs text-ink-gray-6">{{ choice.hint }}</span>
			</button>
			<p v-if="error" class="app-menu-title" role="alert">{{ error }}</p>
			<p v-else-if="searched && !choices.length" class="app-menu-title">{{ query.trim() ? 'Aucun résultat.' : 'Tapez pour rechercher.' }}</p>
			<p v-else-if="!searched" class="app-menu-title">Recherche…</p>
			<button v-if="createLabel && searched" type="button" class="app-menu-item" role="option" :aria-selected="cursor === choices.length" @mousedown.prevent @click="create" @pointerenter="cursor = choices.length">
				<LucidePlus class="h-3.5 w-3.5 flex-none text-accent" aria-hidden="true" />
				<span class="min-w-0 flex-auto truncate">{{ createLabel }}<template v-if="query.trim()"> « {{ query.trim() }} »</template></span>
			</button>
		</div>
	</div>
</template>
