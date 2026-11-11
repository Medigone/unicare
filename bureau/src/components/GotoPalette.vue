<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideSearch from '~icons/lucide/search'
import { filterPages, type GotoPage } from '@/lib/goto'

/**
 * « Aller à… » : la barre du haut l'ouvre, Ctrl K (⌘ K) aussi, de n'importe quelle page.
 * On tape quelques lettres d'une page ou de son module ; Entrée l'ouvre, Échap ferme.
 */
const props = defineProps<{ pages: GotoPage[] }>()

const router = useRouter()
const open = ref(false)
const query = ref('')
const cursor = ref(0)
const input = ref<HTMLInputElement | null>(null)
const results = computed(() => filterPages(props.pages, query.value))
watch(query, () => (cursor.value = 0))

async function show() {
	open.value = true
	query.value = ''
	await nextTick()
	input.value?.focus()
}
function hide() {
	open.value = false
}
function go(page?: GotoPage) {
	if (!page) return
	hide()
	if (page.to) router.push(page.to)
	else if (page.href) window.open(page.href, '_blank', 'noopener')
}
function onKey(event: KeyboardEvent) {
	const size = results.value.length
	if (event.key === 'Escape') {
		event.preventDefault()
		hide()
	} else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
		event.preventDefault()
		if (size) cursor.value = (cursor.value + (event.key === 'ArrowDown' ? 1 : size - 1)) % size
	} else if (event.key === 'Enter') {
		event.preventDefault()
		go(results.value[cursor.value])
	}
}
// Ctrl K (⌘ K sur Mac) ouvre la recherche, même depuis un champ de saisie.
function onGlobalKey(event: KeyboardEvent) {
	if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 'k') {
		event.preventDefault()
		if (open.value) hide()
		else show()
	}
}
onMounted(() => document.addEventListener('keydown', onGlobalKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onGlobalKey))
const shortcut = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘ K' : 'Ctrl K'
</script>

<template>
	<button type="button" class="goto-trigger" aria-haspopup="dialog" :aria-expanded="open" @click="show">
		<LucideSearch class="h-3.5 w-3.5 flex-none" aria-hidden="true" />
		<span class="goto-trigger-label">Aller à…</span>
		<kbd class="goto-kbd">{{ shortcut }}</kbd>
	</button>

	<div v-if="open" class="dialog-scrim goto-scrim" @click.self="hide">
		<div class="dialog goto-dialog" role="dialog" aria-modal="true" aria-label="Aller à une page" @keydown="onKey">
			<div class="goto-search">
				<LucideSearch class="h-4 w-4 flex-none text-ink-gray-5" aria-hidden="true" />
				<input
					ref="input"
					v-model="query"
					class="goto-input"
					type="search"
					placeholder="Page ou module : factures, stock, clients…"
					autocomplete="off"
					role="combobox"
					aria-autocomplete="list"
					aria-controls="goto-results"
					:aria-activedescendant="results.length ? `goto-${results[cursor]?.id}` : undefined"
					aria-expanded="true"
				/>
				<kbd class="goto-kbd">Échap</kbd>
			</div>
			<ul id="goto-results" class="goto-results" role="listbox" aria-label="Pages">
				<li v-for="(page, index) in results" :id="`goto-${page.id}`" :key="page.id" role="option" :aria-selected="index === cursor" class="goto-option" @mousedown.prevent @click="go(page)" @pointerenter="cursor = index">
					<component :is="page.icon" class="h-4 w-4 flex-none text-ink-gray-6" aria-hidden="true" />
					<span class="min-w-0 flex-auto truncate">{{ page.label }}</span>
					<span v-if="page.module" class="text-xs text-ink-gray-6">{{ page.module }}</span>
					<LucideArrowUpRight v-if="page.href" class="h-3.5 w-3.5 flex-none text-ink-gray-5" aria-label="s'ouvre sur le Desk" />
				</li>
				<li v-if="!results.length" class="goto-empty">Aucune page ne correspond.</li>
			</ul>
			<p class="goto-hint">↑ ↓ pour choisir · Entrée pour ouvrir</p>
		</div>
	</div>
</template>
