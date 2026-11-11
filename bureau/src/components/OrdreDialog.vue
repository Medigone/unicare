<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import LucideInfo from '~icons/lucide/info'
import FormDialog from '@shared/components/FormDialog.vue'
import { createOrdre, getBesoins, getOrdreOptions } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { parseQty, type Besoin, type OrdreOptions } from '@/lib/ordres'

/**
 * Nouvel ordre : le produit, la quantité et la date. La recette du produit est proposée d'office ; les matières
 * nécessaires et le stock s'affichent aussitôt. Un manque n'empêche pas de créer l'ordre, seulement de le préparer.
 */
const props = defineProps<{ produit?: string; recette?: string }>()
const emit = defineEmits<{ close: []; created: [name: string] }>()

const today = new Date().toISOString().slice(0, 10)
const values = reactive({ produit: '', recette: '', quantite: '', date_prevue: today, checklist: '' })
const options = ref<OrdreOptions | null>(null)
const loadError = ref('')
const serverError = ref('')
const errors = reactive({ produit: '', quantite: '' })
const busy = ref(false)
const dirty = computed(() => Boolean(values.produit || values.quantite))

onMounted(async () => {
	try {
		options.value = await getOrdreOptions()
		values.checklist = options.value.checklists[0] ?? ''
		if (props.produit) values.produit = props.produit
		else if (options.value.produits.length === 1) values.produit = options.value.produits[0].value
	} catch (e) {
		loadError.value = (e as Error).message
	}
})

const recettes = computed(() => (options.value?.recettes ?? []).filter((item) => item.produit === values.produit))
watch(
	() => values.produit,
	() => {
		errors.produit = ''
		values.recette = recettes.value.find((item) => item.value === props.recette)?.value ?? recettes.value[0]?.value ?? ''
	},
)

// Matières nécessaires, recalculées un instant après la dernière frappe.
const besoins = ref<Besoin[]>([])
const besoinsError = ref('')
let timer: ReturnType<typeof setTimeout> | null = null
let lastRequest = 0
watch([() => values.recette, () => values.quantite], () => {
	if (timer) clearTimeout(timer)
	const quantite = parseQty(values.quantite)
	if (!values.recette || !(quantite > 0)) {
		besoins.value = []
		return
	}
	timer = setTimeout(async () => {
		const request = ++lastRequest
		try {
			const response = await getBesoins(values.recette, quantite)
			if (request === lastRequest) {
				besoins.value = response.lignes
				besoinsError.value = ''
			}
		} catch (e) {
			if (request === lastRequest) besoinsError.value = (e as Error).message
		}
	}, 300)
})
const manques = computed(() => besoins.value.filter((line) => line.disponible + 0.0001 < line.quantite))

async function submit() {
	if (busy.value) return
	serverError.value = ''
	const quantite = parseQty(values.quantite)
	errors.produit = values.produit && values.recette ? '' : values.produit ? "Ce produit n'a pas de recette active." : 'Choisissez le produit.'
	errors.quantite = quantite > 0 ? '' : 'Indiquez combien produire.'
	if (errors.produit || errors.quantite) return
	busy.value = true
	try {
		const created = await createOrdre({ produit: values.produit, recette: values.recette, quantite, date_prevue: values.date_prevue || undefined, checklist: values.checklist || undefined })
		emit('created', created.name)
		emit('close')
	} catch (e) {
		serverError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog title="Nouvel ordre de conditionnement" :dirty="dirty" :busy="busy" hint="Ctrl + Entrée pour créer l'ordre" @close="emit('close')" @submit="submit">
		<p class="text-sm text-ink-gray-7">Choisissez le produit et la quantité : les matières se calculent toutes seules d'après la recette.</p>
		<p v-if="loadError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ loadError }}</p>
		<p v-else-if="options && !options.produits.length" role="alert" class="rounded-control tone-amber px-3 py-2 text-sm">Aucun produit n'a de recette active : créez d'abord une recette.</p>

		<div class="form-field">
			<label class="field-label" for="ordre-produit">Que produit-on ? <span class="req">obligatoire</span></label>
			<select id="ordre-produit" v-model="values.produit" class="field-input" :aria-invalid="Boolean(errors.produit)">
				<option value="">Choisir le produit…</option>
				<option v-for="item in options?.produits" :key="item.value" :value="item.value">{{ item.label }} ({{ item.value }})</option>
			</select>
			<p v-if="errors.produit" class="field-error" role="alert">{{ errors.produit }}</p>
		</div>
		<div v-if="recettes.length > 1" class="form-field">
			<label class="field-label" for="ordre-recette">Recette</label>
			<select id="ordre-recette" v-model="values.recette" class="field-input">
				<option v-for="item in recettes" :key="item.value" :value="item.value">{{ item.label }}</option>
			</select>
		</div>
		<p v-else-if="recettes.length === 1" class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Recette {{ recettes[0].label }}.</span></p>

		<div class="form-grid">
			<div class="form-field">
				<label class="field-label" for="ordre-quantite">Combien ? <span class="req">obligatoire</span></label>
				<input id="ordre-quantite" v-model="values.quantite" class="field-input text-right tabular-nums" inputmode="decimal" :aria-invalid="Boolean(errors.quantite)" @input="errors.quantite = ''" />
				<p v-if="errors.quantite" class="field-error" role="alert">{{ errors.quantite }}</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="ordre-date">Pour quand ?</label>
				<input id="ordre-date" v-model="values.date_prevue" type="date" class="field-input" />
			</div>
		</div>
		<div class="form-field">
			<label class="field-label" for="ordre-checklist">Contrôles avant production</label>
			<select id="ordre-checklist" v-model="values.checklist" class="field-input">
				<option v-for="item in options?.checklists" :key="item" :value="item">{{ item }}</option>
			</select>
			<p class="field-note"><span>Les contrôles se cochent à l'atelier, avant d'envoyer les matières.</span></p>
		</div>

		<section v-if="besoins.length" class="flex flex-col gap-1.5">
			<h3 class="text-sm font-semibold">Matières nécessaires pour {{ formatQty(parseQty(values.quantite)) }}</h3>
			<div class="ref-scroll"><table class="ref-table">
				<thead><tr><th>Matière</th><th>Type</th><th class="end">Il faut</th><th class="end">En stock</th><th></th></tr></thead>
				<tbody>
					<tr v-for="line in besoins" :key="line.article">
						<td class="font-medium">{{ line.designation }}</td>
						<td>{{ line.type || '—' }}</td>
						<td class="end tabular-nums">{{ formatQty(line.quantite) }} <span class="text-xs text-ink-gray-6">{{ line.unite }}</span></td>
						<td class="end tabular-nums" :class="line.disponible < line.quantite && 'font-semibold text-tone-red'">{{ formatQty(line.disponible) }} <span class="text-xs text-ink-gray-6">{{ line.depot }}</span></td>
						<td>
							<span v-if="line.disponible + 0.0001 < line.quantite" class="badge tone-red">manque {{ formatQty(line.quantite - line.disponible) }}</span>
							<span v-else-if="line.avec_lot" class="badge tone-blue">lot proposé</span>
							<span v-else class="badge tone-green">suffisant</span>
						</td>
					</tr>
				</tbody>
			</table></div>
			<p class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>{{ manques.length ? "Un manque n'empêche pas de créer l'ordre : il empêchera seulement de l'envoyer à l'atelier tant que le stock n'est pas là." : 'Le lot de chaque matière suivie par lots est proposé : le plus proche de la péremption, jamais un lot périmé.' }}</span></p>
		</section>
		<p v-if="besoinsError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ besoinsError }}</p>
		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>
		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Création…' : "Créer l'ordre" }}</button>
		</template>
	</FormDialog>
</template>
