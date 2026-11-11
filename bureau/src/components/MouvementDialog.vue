<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import LucideTrash2 from '~icons/lucide/trash-2'
import FormDialog from '@shared/components/FormDialog.vue'
import QuickAddBar from './QuickAddBar.vue'
import { createMouvement, getLotsArticle, getMouvementOptions, searchStockArticles, updateMouvement } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { parseNumber, type QuickAddChoice } from '@/lib/devis'
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
		: ([] as MouvementDraftLine[]),
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
function lotPerime(item: MouvementDraftLine) {
	return Boolean(item.lot && lots[item.article]?.find((entry) => entry.lot === item.lot)?.perime)
}
function lotsFor(item: MouvementDraftLine) {
	const available = lots[item.article] ?? []
	return item.lot && !available.some((entry) => entry.lot === item.lot) ? [{ lot: item.lot, qty: 0, peremption: null }, ...available] : available
}
function lotLabel(entry: LotChoice) {
	if (entry.perime) return `${entry.lot} · ${formatQty(entry.qty)} dispo · PÉRIMÉ depuis le ${formatDay(entry.peremption)}`
	return `${entry.lot} · ${formatQty(entry.qty)} dispo${entry.peremption ? ` · périme le ${formatDay(entry.peremption)}` : ''}`
}

// Le stock affiché est celui du dépôt de départ (sortie, transfert) ou d'arrivée (entrée).
const stockDepot = computed(() => (nature.value?.source ? form.source : form.cible) || undefined)
const findArticles = async (query: string): Promise<QuickAddChoice[]> =>
	(await searchStockArticles(query, stockDepot.value)).map((article) => ({ ...article, prix: null }))
const stocks = reactive<Record<string, number | null | undefined>>({})
const highlighted = ref<number | null>(null)
let highlightTimer: ReturnType<typeof setTimeout> | null = null

/**
 * Ajout par la barre. Un article sans lot déjà présent voit sa quantité augmenter ; un article suivi par lots prend une
 * nouvelle ligne (un autre lot), avec le lot le plus proche de sa péremption qui n'est pas déjà pris.
 */
function onAdd(choice: QuickAddChoice, quantite: number) {
	const avecLot = Boolean((choice as unknown as StockArticleChoice).avec_lot)
	stocks[choice.name] = choice.stock
	let target = avecLot ? undefined : form.lignes.find((item) => item.article === choice.name)
	if (target) {
		const current = parseNumber(target.quantite)
		target.quantite = String((Number.isFinite(current) ? current : 0) + quantite).replace('.', ',')
	} else {
		target = line({ article: choice.name, designation: choice.label, unite: choice.uom ?? '', avec_lot: avecLot, quantite: String(quantite).replace('.', ',') })
		form.lignes.push(target)
		const added = target
		if (avecLot && nature.value?.source) {
			loadLots(choice.name).then(() => {
				const pris = new Set(form.lignes.filter((item) => item !== added && item.article === choice.name).map((item) => item.lot))
				// Un lot encore bon d'abord ; s'il n'y a que des lots périmés, le premier (pour les sortir).
				const libres = (lots[choice.name] ?? []).filter((entry) => !pris.has(entry.lot))
				if (!added.lot) added.lot = (libres.find((entry) => !entry.perime) ?? libres[0])?.lot ?? ''
			})
		}
	}
	if (errors.value.ligne) delete errors.value.ligne[target.key]
	delete errors.value.lignes
	highlighted.value = target.key
	if (highlightTimer) clearTimeout(highlightTimer)
	highlightTimer = setTimeout(() => (highlighted.value = null), 1500)
}
function removeLine(target: MouvementDraftLine) {
	form.lignes = form.lignes.filter((item) => item !== target)
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
				<select v-search id="mouvement-source" v-model="form.source" class="field-input" :aria-invalid="Boolean(errors.source)" @change="delete errors.source">
					<option value="">Choisir…</option>
					<option v-for="item in depots" :key="item" :value="item">{{ item }}</option>
				</select>
				<p v-if="errors.source" class="field-error" role="alert">{{ errors.source }}</p>
			</div>
			<div v-if="nature.cible" class="form-field">
				<label class="field-label" for="mouvement-cible">Dépôt d'arrivée <span class="req">obligatoire</span></label>
				<select v-search id="mouvement-cible" v-model="form.cible" class="field-input" :aria-invalid="Boolean(errors.cible)" @change="delete errors.cible">
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
			<QuickAddBar :search="findArticles" input-id="mouvement-ajout" :show-price="false" :stock-label="stockDepot ? `Dans ${stockDepot}` : 'En stock'" :invalid="Boolean(errors.lignes)" @add="onAdd" />
			<div v-if="form.lignes.length" class="ref-scroll"><table class="ref-table livraison-prep">
				<thead><tr><th>Article</th><th class="end">Quantité</th><th>Lot</th><th v-if="form.nature === 'entree'">Péremption</th><th></th></tr></thead>
				<tbody>
					<tr v-for="(item, index) in form.lignes" :key="item.key" :class="highlighted === item.key && 'devis-line-new'">
						<td class="min-w-[220px]">
							<strong class="block truncate" :title="item.designation">{{ item.designation }}</strong>
							<small class="block truncate text-xs text-ink-gray-6">{{ item.article }}<template v-if="stocks[item.article] !== undefined && stocks[item.article] !== null"> · {{ formatQty(stocks[item.article] ?? 0) }} {{ item.unite }} dans {{ stockDepot }}</template></small>
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
								<select v-search v-else v-model="item.lot" class="field-input" :aria-label="`Lot, ligne ${index + 1}`" :disabled="!form.source">
									<option value="">{{ form.source ? (lotsFor(item).length ? 'Choisir…' : 'Aucun lot dans ce dépôt') : 'Choisir le dépôt d\'abord' }}</option>
									<option v-for="entry in lotsFor(item)" :key="entry.lot" :value="entry.lot">{{ lotLabel(entry) }}</option>
								</select>
								<p v-if="lotPerime(item)" class="mt-1 text-xs font-medium text-tone-red">Lot périmé : à sortir du stock ou à mettre au rebut.</p>
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
			<p v-if="!form.lignes.length" class="devis-lines-empty">Aucune ligne : cherchez un article dans la barre ci-dessus.</p>
			<p v-if="errors.lignes" class="field-error" role="alert">{{ errors.lignes }}</p>
			<p class="field-note"><span>{{ form.nature === 'entree' ? 'Un lot saisi qui n\'existe pas encore est créé, avec sa péremption.' : 'Les lots proposés sont ceux du dépôt de départ, le plus proche de sa péremption d\'abord ; les lots périmés viennent en dernier, marqués, pour pouvoir les sortir ou les mettre au rebut.' }} Un lot manquant ou une quantité au-delà du disponible empêche la validation.</span></p>
		</template>

		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>

		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Enregistrement…' : editing ? 'Enregistrer' : 'Créer le mouvement' }}</button>
		</template>
	</FormDialog>
</template>
