<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucidePlus from '~icons/lucide/plus'
import LucideSearch from '~icons/lucide/search'
import { normalize } from '@/lib/goto'
import { creer, creerItems, type CreerItem } from '@/lib/creer'

/** Bouton « Créer » : les entrées les plus fréquentes en tête, le reste par module, une recherche et les raccourcis. */
const open = ref(false)
const query = ref('')
const cursor = ref(0)
const root = ref<HTMLElement | null>(null)
const input = ref<HTMLInputElement | null>(null)
const items = computed(() => creerItems())
const filtered = computed(() => {
	const words = normalize(query.value).split(/\s+/).filter(Boolean)
	return words.length ? items.value.filter((item) => words.every((word) => normalize(`${item.label} ${item.hint ?? ''} ${item.groupe}`).includes(word))) : items.value
})
const frequents = computed(() => filtered.value.filter((item) => item.groupe === 'frequent'))
const groupes = computed(() =>
	(['Ventes', 'Achats', 'Stock et production'] as const).map((groupe) => ({ groupe, items: filtered.value.filter((item) => item.groupe === groupe) })).filter((entry) => entry.items.length),
)
// Ordre de navigation au clavier : celui de l'affichage.
const ordered = computed(() => [...frequents.value, ...groupes.value.flatMap((entry) => entry.items)])

async function toggle() {
	open.value = !open.value
	if (open.value) {
		query.value = ''
		cursor.value = 0
		await nextTick()
		input.value?.focus()
	}
}
function pick(item?: CreerItem) {
	if (!item) return
	open.value = false
	creer(item.key)
}
function onKey(event: KeyboardEvent) {
	const size = ordered.value.length
	if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
		event.preventDefault()
		if (size) cursor.value = (cursor.value + (event.key === 'ArrowDown' ? 1 : size - 1)) % size
	} else if (event.key === 'Enter') {
		event.preventDefault()
		pick(ordered.value[cursor.value])
	} else if (event.key === 'Escape') {
		event.preventDefault()
		open.value = false
	}
}
function onPointer(event: PointerEvent) {
	if (open.value && !root.value?.contains(event.target as Node)) open.value = false
}
onMounted(() => document.addEventListener('pointerdown', onPointer))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onPointer))
const isActive = (item: CreerItem) => ordered.value[cursor.value]?.key === item.key
</script>

<template>
	<div v-if="items.length" ref="root" class="relative">
		<button type="button" class="creer-btn" aria-haspopup="menu" :aria-expanded="open" @click="toggle">
			<LucidePlus class="h-4 w-4" aria-hidden="true" />Créer<LucideChevronDown class="h-3.5 w-3.5" aria-hidden="true" />
		</button>
		<div v-if="open" class="creer-menu" role="menu" aria-label="Créer" @keydown="onKey">
			<label class="creer-search">
				<LucideSearch class="h-3.5 w-3.5 flex-none text-ink-gray-5" aria-hidden="true" />
				<input ref="input" v-model="query" placeholder="Que voulez-vous créer ?" aria-label="Que voulez-vous créer ?" autocomplete="off" @input="cursor = 0" />
			</label>
			<template v-if="frequents.length">
				<p class="creer-group">Les plus utilisés</p>
				<div class="creer-frequents">
					<button v-for="item in frequents" :key="item.key" type="button" class="creer-item" role="menuitem" :data-active="isActive(item)" @click="pick(item)" @pointerenter="cursor = ordered.indexOf(item)">
						<component :is="item.icon" class="h-[18px] w-[18px] flex-none text-accent" aria-hidden="true" />
						<span class="min-w-0 flex-auto text-left">{{ item.label }}<small v-if="item.hint" class="block text-xs text-ink-gray-6">{{ item.hint }}</small></span>
						<span v-if="item.lettre" class="creer-keys" :aria-label="`Raccourci N puis ${item.lettre.toUpperCase()}`"><kbd>N</kbd><kbd>{{ item.lettre.toUpperCase() }}</kbd></span>
					</button>
				</div>
			</template>
			<div v-if="groupes.length" class="creer-groups">
				<div v-for="entry in groupes" :key="entry.groupe">
					<p class="creer-group">{{ entry.groupe }}</p>
					<button v-for="item in entry.items" :key="item.key" type="button" class="creer-item creer-item-small" role="menuitem" :data-active="isActive(item)" @click="pick(item)" @pointerenter="cursor = ordered.indexOf(item)">
						<span class="flex-auto text-left">{{ item.label }}</span>
						<span v-if="item.lettre" class="creer-keys"><kbd>N</kbd><kbd>{{ item.lettre.toUpperCase() }}</kbd></span>
					</button>
				</div>
			</div>
			<p v-if="!ordered.length" class="px-3 py-2 text-sm text-ink-gray-6">Rien ne correspond.</p>
			<p class="creer-hint">La fenêtre s'ouvre ici même. Raccourci de n'importe quelle page : <strong>N</strong>, puis la lettre.</p>
		</div>
	</div>
</template>
