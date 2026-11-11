<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import LucideSearch from '~icons/lucide/search'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { parseNumber, type QuickAddChoice } from '@/lib/devis'

/**
 * Barre de saisie rapide d'une pièce : on tape quelques lettres, les articles s'affichent avec leur prix au tarif et
 * leur stock ; Entrée ajoute l'article choisi avec la quantité. Tab passe à la quantité, Entrée y ajoute aussi.
 * Tout au clavier : après l'ajout, la barre se vide et garde le focus pour l'article suivant.
 */
const props = withDefaults(defineProps<{ search: (query: string) => Promise<QuickAddChoice[]>; inputId?: string; invalid?: boolean; priceLabel?: string; noPrice?: string }>(), { priceLabel: 'Prix HT', noPrice: 'pas de prix' })
const emit = defineEmits<{ add: [choice: QuickAddChoice, quantite: number] }>()

const query = ref('')
const quantite = ref('1')
const results = ref<QuickAddChoice[]>([])
const cursor = ref(0)
const open = ref(false)
const loading = ref(false)
const error = ref('')
const input = ref<HTMLInputElement | null>(null)
const qtyError = ref(false)

let timer: ReturnType<typeof setTimeout> | null = null
let lastRequest = 0
watch(query, (value) => {
	if (timer) clearTimeout(timer)
	if (!value.trim()) {
		results.value = []
		open.value = false
		return
	}
	open.value = true
	loading.value = true
	timer = setTimeout(async () => {
		const request = ++lastRequest
		try {
			const found = await props.search(value)
			if (request !== lastRequest) return
			results.value = found
			cursor.value = 0
			error.value = ''
		} catch (e) {
			if (request === lastRequest) error.value = (e as Error).message
		} finally {
			if (request === lastRequest) loading.value = false
		}
	}, 200)
})

/** Les morceaux du libellé, avec ceux qui correspondent à la recherche marqués. */
function parts(label: string) {
	const words = query.value.trim().split(/\s+/).filter(Boolean).map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
	if (!words.length) return [{ text: label, hit: false }]
	return label.split(new RegExp(`(${words.join('|')})`, 'gi')).filter(Boolean).map((text) => ({ text, hit: words.some((word) => new RegExp(`^${word}$`, 'i').test(text)) }))
}

function stockTone(choice: QuickAddChoice) {
	if (choice.stock === null || choice.stock === undefined) return ''
	return choice.stock <= 0 ? 'tone-red' : 'tone-green'
}

const selected = computed(() => results.value[cursor.value])
function add(choice = selected.value) {
	if (!choice) return
	const value = parseNumber(quantite.value)
	qtyError.value = !(value > 0)
	if (qtyError.value) return
	emit('add', choice, value)
	query.value = ''
	quantite.value = '1'
	results.value = []
	open.value = false
	input.value?.focus()
}
function onKey(event: KeyboardEvent) {
	const size = results.value.length
	if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
		event.preventDefault()
		if (!open.value && query.value.trim()) open.value = true
		if (size) cursor.value = (cursor.value + (event.key === 'ArrowDown' ? 1 : size - 1)) % size
	} else if (event.key === 'Enter' && !event.ctrlKey && !event.metaKey) {
		event.preventDefault()
		// Entrée n'envoie pas la fenêtre : elle ajoute l'article (Ctrl + Entrée crée toujours la pièce).
		event.stopPropagation()
		add()
	} else if (event.key === 'Escape' && open.value) {
		event.preventDefault()
		event.stopPropagation()
		open.value = false
	}
}
function onQtyKey(event: KeyboardEvent) {
	if (event.key === 'Enter' && !event.ctrlKey && !event.metaKey) {
		event.preventDefault()
		event.stopPropagation()
		add()
	}
}
function onBlur() {
	setTimeout(() => {
		if (!document.activeElement?.closest('.quick-add')) open.value = false
	}, 120)
}
defineExpose({ focus: () => input.value?.focus() })
</script>

<template>
	<div class="quick-add" :class="invalid && 'quick-add-invalid'" @focusout="onBlur">
		<LucideSearch class="h-4 w-4 flex-none text-accent" aria-hidden="true" />
		<input
			:id="inputId"
			ref="input"
			v-model="query"
			class="quick-add-input"
			type="search"
			placeholder="Ajouter un article : tapez son nom ou son code…"
			autocomplete="off"
			role="combobox"
			aria-autocomplete="list"
			:aria-expanded="open"
			aria-controls="quick-add-results"
			:aria-activedescendant="open && selected ? `quick-add-${cursor}` : undefined"
			:aria-invalid="invalid"
			@keydown="onKey"
			@focus="open = Boolean(query.trim())"
		/>
		<label class="quick-add-qty-label" for="quick-add-qty">Quantité</label>
		<input id="quick-add-qty" v-model="quantite" class="field-input quick-add-qty" inputmode="decimal" :aria-invalid="qtyError" @keydown="onQtyKey" @input="qtyError = false" />
		<button type="button" class="btn-primary" :disabled="!selected" @mousedown.prevent @click="add()">Ajouter</button>

		<div v-if="open" id="quick-add-results" class="quick-add-menu" role="listbox" aria-label="Articles trouvés">
			<div v-if="results.length" class="quick-add-row quick-add-head" aria-hidden="true"><span>Article</span><span class="end">{{ priceLabel }}</span><span class="end">En stock</span><span></span></div>
			<div
				v-for="(choice, index) in results"
				:id="`quick-add-${index}`"
				:key="choice.name"
				class="quick-add-row quick-add-option"
				role="option"
				:aria-selected="index === cursor"
				@mousedown.prevent
				@click="add(choice)"
				@pointerenter="cursor = index"
			>
				<span class="min-w-0">
					<strong class="block truncate"><template v-for="(part, key) in parts(choice.label)" :key="key"><mark v-if="part.hit">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></strong>
					<small class="block truncate text-ink-gray-6">{{ choice.name }}<template v-if="choice.groupe"> · {{ choice.groupe }}</template><template v-if="choice.uom"> · {{ choice.uom }}</template></small>
				</span>
				<span class="end tabular-nums" :class="choice.prix === null && 'text-ink-gray-6'">{{ choice.prix === null ? noPrice : `${formatAmount(choice.prix)} DA` }}</span>
				<span class="end"><span v-if="choice.stock !== null && choice.stock !== undefined" class="badge tabular-nums" :class="stockTone(choice)">{{ choice.stock <= 0 ? 'rupture' : `${formatQty(choice.stock)} ${choice.uom ?? ''}` }}</span></span>
				<span class="end"><kbd v-if="index === cursor" class="goto-kbd">Entrée</kbd></span>
			</div>
			<p v-if="loading && !results.length" class="quick-add-hint">Recherche…</p>
			<p v-else-if="error" class="quick-add-hint text-tone-red" role="alert">{{ error }}</p>
			<p v-else-if="!results.length" class="quick-add-hint">Aucun article ne correspond.</p>
			<p v-else class="quick-add-hint">↑ ↓ pour choisir · Entrée ajoute avec la quantité · Tab passe à la quantité · un article déjà présent voit sa quantité augmenter</p>
		</div>
	</div>
</template>
