<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import LucidePlus from '~icons/lucide/plus'
import LucideTrash2 from '~icons/lucide/trash-2'
import FormDialog from '@shared/components/FormDialog.vue'
import ChoicePicker from './ChoicePicker.vue'
import { createMouvement, getLotsArticle, getMouvementOptions, searchStockArticles, updateMouvement } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { formatDay } from '@/lib/display'
import type { LotChoice } from '@/lib/livraisons'
import { mouvementLinesForServer, NATURES, validateMouvement, type MouvementDetail, type MouvementDraftLine, type MouvementErrors, type Nature, type StockArticleChoice } from '@/lib/mouvements'

/**
 * Saisie d'un mouvement de stock : nature, dépôts, remarque et lignes (article, quantité, lot).
 * En sortie et en transfert, le lot se choisit parmi ceux du dépôt de départ (péremption la plus proche d'abord) ;
 * en entrée, il se saisit, avec sa péremption, et se crée au besoin. Sans `mouvement`, la fenêtre crée un brouillon.
 */
const props = defineProps<{ mouvement?: MouvementDetail }>()
const emit = defineEmits<{ close: []; created: [name: string]; saved: [mouvement: MouvementDetail] }>()

const editing = computed(() => Boolean(props.mouvement))
let nextKey = 0
function line(values: Partial<MouvementDraftLine> = {}): MouvementDraftLine {
	return { key: ++nextKey, article: '', designation: '', unite: '', avec_lot: false, quantite: '1', lot: '', peremption: '', ...values }
}
const form = reactive({
	nature: (props.mouvement?.nature === 'production' ? '' : props.mouvement?.nature ?? '') as Nature | '',
	source: props.mouvement?.lignes[0]?.source ?? props.mouvement?.source ?? '',
	cible: props.mouvement?.lignes[0]?.cible ?? props.mouvement?.cible ?? '',
	remarque: props.mouvement?.remarque ?? '',
	lignes: props.mouvement
		? props.mouvement.lignes.map((row) => line({ article: row.article, designation: row.designation, unite: row.unite ?? '', avec_lot: Boolean(row.avec_lot), quantite: String(row.quantite), lot: row.lots[0] ?? '' }))
		: [line()],
})
const initial = JSON.parse(JSON.stringify(form)) as typeof form
const dirty = computed(() => JSON.stringify(form) !== JSON.stringify(initial))
const nature = computed(() => NATURES.find((item) => item.key === form.nature))
const depots = ref<string[]>([])
const loadError = ref('')
const serverError = ref('')
const errors = ref<MouvementErrors>({})
const busy = ref(false)

onMounted(async () => {
	try {
		depots.value = (await getMouvementOptions()).depots
	} catch (e) {
		loadError.value = (e as Error).message
	}
})

// Lots disponibles par article dans le dépôt de départ, rechargés quand il change.
const lots = reactive<Record<string, LotChoice[]>>({})
async function loadLots(article: string) {
	if (!article || !form.source || !nature.value?.source) return
	try {
		lots[article] = await getLotsArticle(article, form.source)
	} catch {
		lots[article] = []
	}
}
watch(
	() => [form.source, form.nature],
	() => {
		for (const key of Object.keys(lots)) delete lots[key]
		for (const item of form.lignes) if (item.article && item.avec_lot) loadLots(item.article)
	},
	{ immediate: true },
)
function lotsFor(item: MouvementDraftLine) {
	const available = lots[item.article] ?? []
	return item.lot && !available.some((entry) => entry.lot === item.lot) ? [{ lot: item.lot, qty: 0, peremption: null }, ...available] : available
}
function lotLabel(entry: LotChoice) {
	return `${entry.lot} · ${formatQty(entry.qty)} dispo${entry.peremption ? ` · périme le ${formatDay(entry.peremption)}` : ''}`
}

const findArticles = async (query: string) =>
	(await searchStockArticles(query, nature.value?.source ? form.source : undefined)).map((article) => ({ ...article, hint: article.stock === null ? article.uom : `${formatQty(article.stock)} en stock` }))

function pickArticle(target: MouvementDraftLine, choice: StockArticleChoice) {
	target.article = choice.name
	target.designation = choice.label
	target.unite = choice.uom ?? ''
	target.avec_lot = Boolean(choice.avec_lot)
	target.lot = ''
	if (errors.value.ligne) delete errors.value.ligne[target.key]
	delete errors.value.lignes
	if (target.avec_lot) {
		loadLots(choice.name).then(() => {
			// Le lot le plus proche de sa péremption est proposé d'abord.
			if (!target.lot && nature.value?.source) target.lot = lots[choice.name]?.[0]?.lot ?? ''
		})
	}
	if (form.lignes[form.lignes.length - 1] === target) form.lignes.push(line())
}
function clearArticle(target: MouvementDraftLine) {
	Object.assign(target, { article: '', designation: '', unite: '', avec_lot: false, lot: '', peremption: '' })
}
function removeLine(target: MouvementDraftLine) {
	form.lignes = form.lignes.filter((item) => item !== target)
	if (!form.lignes.length) form.lignes.push(line())
}

async function submit() {
	if (busy.value) return
	errors.value = validateMouvement(form)
	serverError.value = ''
	if (Object.keys(errors.value).length) {
		await nextTick()
		document.querySelector<HTMLElement>('.dialog [aria-invalid="true"]')?.focus()
		return
	}
	if (editing.value && !dirty.value) {
		emit('close')
		return
	}
	const kind = form.nature as Nature
	const values = {
		nature: kind,
		source: nature.value?.source ? form.source : undefined,
		cible: nature.value?.cible ? form.cible : undefined,
		remarque: form.remarque.trim(),
		lignes: mouvementLinesForServer(form.lignes, kind),
	}
	busy.value = true
	try {
		if (props.mouvement) emit('saved', await updateMouvement(props.mouvement, values))
		else emit('created', (await createMouvement(values)).name)
		emit('close')
	} catch (e) {
		serverError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog :title="editing ? `Modifier le mouvement ${mouvement?.name}` : 'Nouveau mouvement de stock'" :dirty="dirty" :busy="busy" :hint="editing ? 'Ctrl + Entrée pour enregistrer' : 'Ctrl + Entrée pour créer'" class="devis-dialog" @close="emit('close')" @submit="submit">
		<p v-if="loadError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ loadError }}</p>

		<fieldset class="form-field">
			<legend class="field-label">Nature <span v-if="!editing" class="req">obligatoire</span></legend>
			<div class="flex flex-wrap gap-2">
				<label v-for="item in NATURES" :key="item.key" class="card flex min-w-[180px] flex-1 cursor-pointer flex-col gap-0.5 p-2.5" :class="form.nature === item.key && 'ring-2 ring-outline-gray-4'">
					<span class="flex items-center gap-2 font-semibold"><input v-model="form.nature" type="radio" name="mouvement-nature" :value="item.key" :disabled="editing" @change="delete errors.nature" />{{ item.label }}</span>
					<span class="text-xs text-ink-gray-6">{{ item.aide }}</span>
				</label>
			</div>
			<p v-if="errors.nature" class="field-error" role="alert">{{ errors.nature }}</p>
		</fieldset>

		<div v-if="nature" class="form-grid">
			<div v-if="nature.source" class="form-field">
				<label class="field-label" for="mouvement-source">Dépôt de départ <span class="req">obligatoire</span></label>
				<select id="mouvement-source" v-model="form.source" class="field-input" :aria-invalid="Boolean(errors.source)" @change="delete errors.source">
					<option value="">Choisir…</option>
					<option v-for="item in depots" :key="item" :value="item">{{ item }}</option>
				</select>
				<p v-if="errors.source" class="field-error" role="alert">{{ errors.source }}</p>
			</div>
			<div v-if="nature.cible" class="form-field">
				<label class="field-label" for="mouvement-cible">Dépôt d'arrivée <span class="req">obligatoire</span></label>
				<select id="mouvement-cible" v-model="form.cible" class="field-input" :aria-invalid="Boolean(errors.cible)" @change="delete errors.cible">
					<option value="">Choisir…</option>
					<option v-for="item in depots" :key="item" :value="item" :disabled="nature.source && item === form.source">{{ item }}</option>
				</select>
				<p v-if="errors.cible" class="field-error" role="alert">{{ errors.cible }}</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="mouvement-remarque">Remarque</label>
				<input id="mouvement-remarque" v-model="form.remarque" class="field-input" :placeholder="form.nature === 'sortie' ? 'Casse, consommation, rebut…' : 'Motif du mouvement'" autocomplete="off" />
			</div>
		</div>

		<template v-if="nature">
			<h3 class="form-section">Lignes</h3>
			<div class="ref-scroll"><table class="ref-table livraison-prep">
				<thead><tr><th>Article</th><th class="end">Quantité</th><th>Lot</th><th v-if="form.nature === 'entree'">Péremption</th><th></th></tr></thead>
				<tbody>
					<tr v-for="(item, index) in form.lignes" :key="item.key">
						<td class="min-w-[220px]">
							<ChoicePicker :search="findArticles" :picked="item.designation" :input-id="`mouvement-article-${item.key}`" placeholder="Article ou code" compact @pick="(choice) => pickArticle(item, choice)" @clear="clearArticle(item)" />
							<p v-if="errors.ligne?.[item.key]" class="field-error" role="alert">{{ errors.ligne[item.key] }}</p>
						</td>
						<td class="end">
							<span class="inline-flex items-center gap-1">
								<input v-model="item.quantite" class="field-input w-20 text-right tabular-nums" inputmode="decimal" :aria-label="`Quantité, ligne ${index + 1}`" :aria-invalid="Boolean(errors.ligne?.[item.key])" />
								<span class="w-10 truncate text-xs text-ink-gray-6" :title="item.unite">{{ item.unite }}</span>
							</span>
						</td>
						<td>
							<template v-if="item.avec_lot">
								<input v-if="form.nature === 'entree'" v-model="item.lot" class="field-input tabular-nums" placeholder="Nº de lot" autocomplete="off" :aria-label="`Lot, ligne ${index + 1}`" />
								<select v-else v-model="item.lot" class="field-input" :aria-label="`Lot, ligne ${index + 1}`" :disabled="!form.source">
									<option value="">{{ form.source ? (lotsFor(item).length ? 'Choisir…' : 'Aucun lot dans ce dépôt') : 'Choisir le dépôt d\'abord' }}</option>
									<option v-for="entry in lotsFor(item)" :key="entry.lot" :value="entry.lot">{{ lotLabel(entry) }}</option>
								</select>
							</template>
							<span v-else class="text-ink-gray-6">—</span>
						</td>
						<td v-if="form.nature === 'entree'">
							<input v-if="item.avec_lot" v-model="item.peremption" class="field-input tabular-nums" type="date" :aria-label="`Péremption, ligne ${index + 1}`" />
						</td>
						<td><button type="button" class="icon-btn" :aria-label="`Retirer la ligne ${index + 1}`" @click="removeLine(item)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button></td>
					</tr>
				</tbody>
			</table></div>
			<button type="button" class="btn-ghost self-start" @click="form.lignes.push(line())"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Ajouter une ligne</button>
			<p v-if="errors.lignes" class="field-error" role="alert">{{ errors.lignes }}</p>
			<p class="field-note"><span>{{ form.nature === 'entree' ? 'Un lot saisi qui n\'existe pas encore est créé, avec sa péremption.' : 'Les lots proposés sont ceux du dépôt de départ, le plus proche de sa péremption d\'abord ; les lots périmés ne sont pas proposés.' }} Un lot manquant ou une quantité au-delà du disponible empêche la validation.</span></p>
		</template>

		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>

		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Enregistrement…' : editing ? 'Enregistrer' : 'Créer le mouvement' }}</button>
		</template>
	</FormDialog>
</template>
