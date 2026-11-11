<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import LucideArrowDownLeft from '~icons/lucide/arrow-down-left'
import LucideArrowLeft from '~icons/lucide/arrow-left'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideInfo from '~icons/lucide/info'
import LucideSparkles from '~icons/lucide/sparkles'
import FormDialog from '@shared/components/FormDialog.vue'
import ChoicePicker from './ChoicePicker.vue'
import { createPaiement, getPaiementOptions, getPiecesOuvertes, searchTiers, updatePaiement } from '@/lib/api'
import { formatAmount } from '@/lib/clients'
import { dayFromToday, parseNumber } from '@/lib/devis'
import { formatDay } from '@/lib/display'
import { capacity, proposeAllocation, TYPE_HELP, validateAssistant, type AssistantErrors, type PaiementDetail, type PaiementOptions, type PaiementType, type PieceOuverte } from '@/lib/paiements'

/**
 * Assistant de paiement : d'abord le type, puis tiers, montant, mode et rapprochement sur un seul écran.
 * Sans `paiement`, il crée un brouillon ; avec, il remplace la saisie du brouillon. `initial` préremplit (depuis une facture).
 */
const props = defineProps<{ paiement?: PaiementDetail; initial?: { type: PaiementType; tiers: string; tiersLabel: string } }>()
const emit = defineEmits<{ close: []; created: [name: string]; saved: [paiement: PaiementDetail] }>()

const today = dayFromToday(0)
const editing = Boolean(props.paiement)
const options = ref<PaiementOptions | null>(null)
const loadError = ref('')
const serverError = ref('')
const errors = ref<AssistantErrors>({})
const busy = ref(false)

const form = reactive({
	type: (props.paiement?.type ?? props.initial?.type ?? '') as PaiementType | '',
	tiers: props.paiement?.tiers ?? props.initial?.tiers ?? '',
	tiersLabel: props.paiement?.tiers_label ?? props.initial?.tiersLabel ?? '',
	montant: props.paiement ? String(props.paiement.montant) : '',
	mode: props.paiement?.mode ?? '',
	date: props.paiement?.date ?? today,
	reference: props.paiement?.reference ?? '',
	dateReference: props.paiement?.date_reference ?? '',
	remarque: props.paiement?.remarque ?? '',
})
// Montant affecté par pièce, en texte saisi.
const allocations = ref<Record<string, string>>(Object.fromEntries((props.paiement?.affectations ?? []).map((row) => [row.name, String(row.montant)])))
// Photo de la saisie de départ ; reprise après le préremplissage du mode, qui n'est pas une saisie.
const snapshot = () => JSON.stringify({ form, allocations: allocations.value })
const initial = ref(snapshot())
const dirty = computed(() => snapshot() !== initial.value)
const step = ref<'type' | 'saisie'>(form.type ? 'saisie' : 'type')
const help = computed(() => (form.type ? TYPE_HELP[form.type] : null))
const typeLabel = computed(() => options.value?.types.find((item) => item.value === form.type)?.label ?? '')
const sens = computed(() => options.value?.types.find((item) => item.value === form.type)?.sens)
const modeType = computed(() => options.value?.modes.find((item) => item.value === form.mode)?.type)

onMounted(async () => {
	try {
		options.value = await getPaiementOptions()
		if (!form.mode) {
			form.mode = options.value.modes.find((item) => item.type === 'Cash')?.value ?? ''
			initial.value = snapshot()
		}
	} catch (e) {
		loadError.value = (e as Error).message
	}
})

function chooseType(type: PaiementType) {
	if (form.type !== type) {
		form.tiers = ''
		form.tiersLabel = ''
		pieces.value = []
		allocations.value = {}
	}
	form.type = type
	errors.value = {}
	step.value = 'saisie'
}

// Tant qu'on n'a pas touché aux affectations, elles suivent le montant saisi (échéance la plus ancienne d'abord).
const manual = ref(editing)

// Pièces ouvertes du tiers : elles arrivent à chaque changement de tiers ; une réponse périmée est ignorée.
const pieces = ref<PieceOuverte[]>([])
const piecesLoading = ref(false)
const piecesError = ref('')
let lastPieces = 0
async function loadPieces() {
	const request = ++lastPieces
	pieces.value = []
	piecesError.value = ''
	if (!form.type || !form.tiers) return
	piecesLoading.value = true
	try {
		const found = await getPiecesOuvertes(form.type, form.tiers, props.paiement?.name)
		if (request !== lastPieces) return
		pieces.value = found
		// Les affectations d'une pièce qui n'est plus ouverte disparaissent ; les autres restent.
		allocations.value = Object.fromEntries(Object.entries(allocations.value).filter(([name]) => found.some((piece) => piece.name === name)))
		if (!manual.value && parseNumber(form.montant) > 0) propose()
	} catch (e) {
		if (request === lastPieces) piecesError.value = (e as Error).message
	} finally {
		if (request === lastPieces) piecesLoading.value = false
	}
}
watch(() => [form.type, form.tiers], loadPieces, { immediate: true })

const montant = computed(() => parseNumber(form.montant))
watch(montant, () => {
	if (!manual.value && pieces.value.length) propose()
})
const allocated = computed(() => Object.values(allocations.value).reduce((total, value) => total + (Number.isFinite(parseNumber(value)) ? parseNumber(value) : 0), 0))
const avance = computed(() => Math.round(((Number.isFinite(montant.value) ? montant.value : 0) - allocated.value) * 100) / 100)
const totalOuvert = computed(() => pieces.value.reduce((total, piece) => total + capacity(piece), 0))

function repartir() {
	manual.value = false
	propose()
}
function propose() {
	const amounts = proposeAllocation(Number.isFinite(montant.value) ? montant.value : 0, pieces.value)
	allocations.value = Object.fromEntries(Object.entries(amounts).filter(([, value]) => value > 0).map(([name, value]) => [name, String(value)]))
}
function payAll() {
	manual.value = false
	form.montant = String(Math.round(totalOuvert.value * 100) / 100)
	propose()
}
function toggle(piece: PieceOuverte, checked: boolean) {
	manual.value = true
	if (!checked) {
		const next = { ...allocations.value }
		delete next[piece.name]
		allocations.value = next
		return
	}
	// Cocher : la pièce reçoit ce qui reste disponible du montant, au plus son reste dû.
	const free = Math.max(0, avance.value)
	allocations.value = { ...allocations.value, [piece.name]: String(Math.round(Math.min(free || capacity(piece), capacity(piece)) * 100) / 100) }
}

const findTiers = async (query: string) => (form.type ? searchTiers(form.type, query) : [])

async function submit() {
	if (busy.value || step.value !== 'saisie' || !form.type) return
	const amounts = Object.fromEntries(Object.entries(allocations.value).map(([name, value]) => [name, parseNumber(value)]))
	errors.value = validateAssistant({ type: form.type, tiers: form.tiers, montant: montant.value, mode: form.mode, date: form.date, reference: form.reference }, modeType.value, amounts, pieces.value, today)
	serverError.value = ''
	if (Object.keys(errors.value).length) {
		await nextTick()
		document.querySelector<HTMLElement>('.dialog [aria-invalid="true"]')?.focus()
		return
	}
	const values = {
		type: form.type,
		tiers: form.tiers,
		montant: montant.value,
		mode: form.mode,
		date: form.date,
		reference: form.reference.trim() || undefined,
		date_reference: form.reference.trim() && form.dateReference ? form.dateReference : undefined,
		remarque: form.remarque.trim() || undefined,
		affectations: Object.entries(amounts).filter(([, value]) => value > 0).map(([name, value]) => ({ name, montant: value })),
	}
	busy.value = true
	try {
		if (props.paiement) emit('saved', await updatePaiement(props.paiement, values))
		else emit('created', (await createPaiement(values)).name)
		emit('close')
	} catch (e) {
		serverError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog :title="editing ? `Modifier le paiement ${paiement?.name}` : 'Nouveau paiement'" :dirty="dirty" :busy="busy" :hint="step === 'saisie' ? (editing ? 'Ctrl + Entrée pour enregistrer' : 'Ctrl + Entrée pour créer le brouillon') : ''" class="paiement-dialog" @close="emit('close')" @submit="submit">
		<p v-if="loadError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ loadError }}</p>

		<!-- Étape 1 : le type de paiement. -->
		<template v-if="step === 'type'">
			<p class="text-sm text-ink-gray-7">Quel paiement enregistrez-vous ?</p>
			<div class="paiement-types" role="radiogroup" aria-label="Type de paiement">
				<button v-for="item in options?.types" :key="item.value" type="button" class="paiement-type" role="radio" :aria-checked="form.type === item.value" @click="chooseType(item.value)">
					<component :is="item.sens === 'Receive' ? LucideArrowDownLeft : LucideArrowUpRight" class="h-4 w-4 flex-none" :class="item.sens === 'Receive' ? 'text-tone-green' : 'text-tone-amber'" aria-hidden="true" />
					<span class="min-w-0">
						<strong class="block font-semibold text-ink-gray-9">{{ item.label }}</strong>
						<span class="block text-sm text-ink-gray-6">{{ item.sens === 'Receive' ? 'Entrée d\'argent' : 'Sortie d\'argent' }} · {{ TYPE_HELP[item.value].pieces.toLowerCase() }}</span>
					</span>
				</button>
				<p v-if="options && !options.types.length" class="text-ink-gray-6">Votre rôle ne lit ni clients ni fournisseurs : aucun paiement à saisir.</p>
			</div>
		</template>

		<!-- Étape 2 : tiers, montant, mode, puis rapprochement. -->
		<template v-else-if="help">
			<div class="flex flex-wrap items-center gap-2">
				<button v-if="!editing" type="button" class="btn-ghost" @click="step = 'type'"><LucideArrowLeft class="h-3.5 w-3.5" aria-hidden="true" />Type</button>
				<span class="record-flag">{{ typeLabel }}</span>
				<span class="text-sm text-ink-gray-6">{{ sens === 'Receive' ? "Entrée d'argent" : "Sortie d'argent" }}</span>
			</div>

			<div class="form-grid">
				<div class="form-field">
					<label class="field-label" for="paiement-tiers">{{ help.tiers }} <span class="req">obligatoire</span></label>
					<ChoicePicker
						:search="findTiers"
						:picked="form.tiersLabel"
						input-id="paiement-tiers"
						:placeholder="`${help.tiers} ou code`"
						:invalid="Boolean(errors.tiers)"
						@pick="(choice) => ((form.tiers = choice.name), (form.tiersLabel = choice.label), delete errors.tiers)"
						@clear="(form.tiers = ''), (form.tiersLabel = ''), (allocations = {})"
					/>
					<p v-if="errors.tiers" class="field-error" role="alert">{{ errors.tiers }}</p>
				</div>
				<div class="form-field">
					<label class="field-label" for="paiement-montant">Montant (DA) <span class="req">obligatoire</span></label>
					<input id="paiement-montant" v-model="form.montant" class="field-input text-right tabular-nums" inputmode="decimal" :aria-invalid="Boolean(errors.montant)" @input="delete errors.montant" />
					<p v-if="errors.montant" class="field-error" role="alert">{{ errors.montant }}</p>
				</div>
				<div class="form-field">
					<label class="field-label" for="paiement-mode">Mode <span class="req">obligatoire</span></label>
					<select v-search id="paiement-mode" v-model="form.mode" class="field-input" :aria-invalid="Boolean(errors.mode)">
						<option value="">Choisir…</option>
						<option v-for="item in options?.modes" :key="item.value" :value="item.value">{{ item.value }}</option>
					</select>
					<p v-if="errors.mode" class="field-error" role="alert">{{ errors.mode }}</p>
				</div>
				<div class="form-field">
					<label class="field-label" for="paiement-date">Date</label>
					<input id="paiement-date" v-model="form.date" class="field-input tabular-nums" type="date" :max="today" :aria-invalid="Boolean(errors.date)" />
					<p v-if="errors.date" class="field-error" role="alert">{{ errors.date }}</p>
				</div>
				<template v-if="modeType === 'Bank'">
					<div class="form-field">
						<label class="field-label" for="paiement-reference">Référence <span class="req">obligatoire</span></label>
						<input id="paiement-reference" v-model="form.reference" class="field-input" placeholder="Nº de chèque, de virement…" autocomplete="off" :aria-invalid="Boolean(errors.reference)" @input="delete errors.reference" />
						<p v-if="errors.reference" class="field-error" role="alert">{{ errors.reference }}</p>
					</div>
					<div class="form-field">
						<label class="field-label" for="paiement-date-ref">Date du chèque ou du virement</label>
						<input id="paiement-date-ref" v-model="form.dateReference" class="field-input tabular-nums" type="date" />
					</div>
				</template>
			</div>

			<h3 class="form-section">Rapprochement</h3>
			<p v-if="!form.tiers" class="text-sm text-ink-gray-6">Choisissez le {{ help.tiers.toLowerCase() }} : ses {{ help.pieces.toLowerCase() }} s'afficheront ici.</p>
			<p v-else-if="piecesLoading" class="text-sm text-ink-gray-6">Recherche des pièces ouvertes…</p>
			<p v-else-if="piecesError" role="alert" class="text-sm text-tone-red">{{ piecesError }}</p>
			<p v-else-if="!pieces.length" class="text-sm text-ink-gray-6">{{ help.vide }} Le paiement restera une avance.</p>
			<template v-else>
				<div class="flex flex-wrap items-center justify-between gap-2">
					<p class="text-sm text-ink-gray-7">{{ help.pieces }} : <strong class="tabular-nums">{{ formatAmount(totalOuvert) }} DA</strong> au total, l'échéance la plus ancienne d'abord.</p>
					<span class="flex gap-1.5">
						<button type="button" class="btn-ghost" @click="payAll">Tout régler</button>
						<button type="button" class="btn-secondary" :disabled="!(montant > 0)" @click="repartir"><LucideSparkles class="h-3.5 w-3.5" aria-hidden="true" />Répartir le montant</button>
					</span>
				</div>
				<div class="ref-scroll"><table class="ref-table">
					<thead><tr><th class="w-8"><span class="sr-only">Affecter</span></th><th>Pièce</th><th>Échéance</th><th class="end">Reste dû (DA)</th><th class="end">Affecté (DA)</th></tr></thead>
					<tbody>
						<tr v-for="piece in pieces" :key="piece.name">
							<td><input type="checkbox" :checked="piece.name in allocations" :aria-label="`Affecter à ${piece.name}`" @change="toggle(piece, ($event.target as HTMLInputElement).checked)" /></td>
							<td class="tabular-nums">{{ piece.name }}<span v-if="piece.avoir" class="ml-1 record-flag">Avoir</span><span class="block text-xs text-ink-gray-6">{{ formatDay(piece.date) }} · total {{ formatAmount(piece.total) }}</span></td>
							<td class="tabular-nums" :class="piece.echeance && piece.echeance < today && 'text-tone-red'">{{ formatDay(piece.echeance) || '—' }}</td>
							<td class="end tabular-nums">{{ formatAmount(capacity(piece)) }}</td>
							<td class="end">
								<input v-if="piece.name in allocations" v-model="allocations[piece.name]" class="field-input ml-auto w-28 text-right tabular-nums" inputmode="decimal" :aria-label="`Montant affecté à ${piece.name}`" :aria-invalid="Boolean(errors.piece?.[piece.name])" @input="manual = true" />
								<span v-else class="text-ink-gray-6">—</span>
								<p v-if="errors.piece?.[piece.name]" class="field-error" role="alert">{{ errors.piece[piece.name] }}</p>
							</td>
						</tr>
					</tbody>
				</table></div>
			</template>

			<dl class="devis-totaux">
				<div><dt>Montant du paiement</dt><dd class="tabular-nums">{{ formatAmount(Number.isFinite(montant) ? montant : 0) }} DA</dd></div>
				<div><dt>Affecté aux pièces</dt><dd class="tabular-nums">{{ formatAmount(allocated) }} DA</dd></div>
				<div class="devis-total-ttc"><dt>{{ avance < 0 ? 'Dépassement' : 'Avance (non affecté)' }}</dt><dd class="tabular-nums" :class="avance < 0 && 'text-tone-red'">{{ formatAmount(Math.abs(avance)) }} DA</dd></div>
			</dl>
			<p v-if="errors.affectations" class="field-error" role="alert">{{ errors.affectations }}</p>
			<p v-else-if="avance > 0 && form.tiers" class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>{{ help.avance }}</span></p>

			<div class="form-field">
				<label class="field-label" for="paiement-remarque">Remarque</label>
				<textarea id="paiement-remarque" v-model="form.remarque" class="field-input" rows="2" placeholder="Visible sur la pièce comptable"></textarea>
			</div>
			<p class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Le paiement est créé en brouillon : relisez-le sur sa fiche, puis validez-le pour passer l'écriture.</span></p>
		</template>

		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>

		<template #actions>
			<button v-if="step === 'saisie'" type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Enregistrement…' : editing ? 'Enregistrer' : 'Créer le brouillon' }}</button>
		</template>
	</FormDialog>
</template>
