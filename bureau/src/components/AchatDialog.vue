<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import LucideInfo from '~icons/lucide/info'
import LucideTrash2 from '~icons/lucide/trash-2'
import FormDialog from '@shared/components/FormDialog.vue'
import ChoicePicker from './ChoicePicker.vue'
import QuickAddBar from './QuickAddBar.vue'
import { createCommandeAchat, createDevisFournisseur, getCommandeAchatOptions, getDevisFournisseurOptions, searchAchatArticles, searchFournisseurs, updateCommandeAchat, updateDevisFournisseur } from '@/lib/api'
import type { AchatArticleChoice, AchatOptions } from '@/lib/achats'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { addArticle, dayFromToday, draftTotal, linesForServer, parseNumber, validateDevis, type DevisFormErrors, type DraftLine } from '@/lib/devis'
import type { CommandeAchatDetail } from '@/lib/commandesAchat'
import type { DevisFournisseurDetail } from '@/lib/devisFournisseur'

/**
 * Saisie d'un devis fournisseur ou d'une commande d'achat : fournisseur, date (validité ou réception prévue), TVA
 * déductible et lignes au prix d'achat connu. Sans `piece`, la fenêtre crée ; avec, elle modifie le brouillon.
 * Le fournisseur ne change plus une fois la pièce créée.
 */
const props = defineProps<{ kind: 'devis' | 'commande'; piece?: DevisFournisseurDetail | CommandeAchatDetail; fournisseur?: { name: string; label: string } }>()
const emit = defineEmits<{ close: []; created: [name: string]; saved: [piece: DevisFournisseurDetail | CommandeAchatDetail] }>()

const isDevis = props.kind === 'devis'
const devis = isDevis ? (props.piece as DevisFournisseurDetail | undefined) : undefined
const commande = isDevis ? undefined : (props.piece as CommandeAchatDetail | undefined)
const editing = computed(() => Boolean(props.piece))
const pieceLabel = isDevis ? 'le devis fournisseur' : "la commande d'achat"
// Les lignes reprises d'un devis fournisseur gardent leur lien : elles se modifient sur le Desk.
const linesLocked = Boolean(commande?.lignes.some((row) => row.devis))

let nextKey = 0
function line(values: Partial<DraftLine> = {}): DraftLine {
	return { key: ++nextKey, article: '', designation: '', unite: '', quantite: '1', prix: '', ...values }
}
const form = reactive({
	fournisseur: props.piece?.fournisseur ?? props.fournisseur?.name ?? '',
	fournisseurLabel: props.piece?.fournisseur_label ?? props.fournisseur?.label ?? '',
	date: (isDevis ? devis?.valable : commande?.reception) ?? '',
	taxes: props.piece?.taxes_modele ?? '',
	reference: devis?.reference ?? '',
	lignes: props.piece ? props.piece.lignes.map((row) => line({ article: row.article, designation: row.designation, unite: row.unite ?? '', quantite: String(row.quantite), prix: String(row.prix) })) : ([] as DraftLine[]),
})
// Le prix d'achat connu de chaque article : il sert de prix quand le champ reste vide.
const tarifs = reactive<Record<string, number | null>>(Object.fromEntries((props.piece?.lignes ?? []).map((row) => [row.article, row.prix_tarif || null])))
const initial = JSON.parse(JSON.stringify(form)) as typeof form
const dirty = computed(() => JSON.stringify(form) !== JSON.stringify(initial))
const options = ref<(AchatOptions & { validite_jours?: number }) | null>(null)
const loadError = ref('')
const serverError = ref('')
const errors = ref<DevisFormErrors>({})
const busy = ref(false)
const total = computed(() => draftTotal(form.lignes, tarifs))
const dateLabel = isDevis ? 'la date de validité' : 'la date de réception prévue'

onMounted(async () => {
	try {
		options.value = isDevis ? await getDevisFournisseurOptions() : await getCommandeAchatOptions()
		if (!editing.value) {
			form.date ||= dayFromToday(isDevis ? (options.value.validite_jours ?? 30) : 7)
			form.taxes ||= options.value.taxes_defaut ?? ''
			// Préremplis : ce n'est pas une saisie, la fermeture ne demande pas de confirmation.
			initial.date = form.date
			initial.taxes = form.taxes
		}
	} catch (e) {
		loadError.value = (e as Error).message
	}
})

const findFournisseurs = async (query: string) => (await searchFournisseurs(query, true)).map((item) => ({ ...item, hint: item.wilaya }))
const findArticles = (query: string) => searchAchatArticles(query)
// Stock de chaque article ajouté par la barre : affiché sous sa désignation.
const stocks = reactive<Record<string, number | null | undefined>>({})
const highlighted = ref<number | null>(null)
let highlightTimer: ReturnType<typeof setTimeout> | null = null

/** Ajout par la barre : un article déjà présent voit sa quantité augmenter, et sa ligne s'éclaire un instant. */
function onAdd(choice: AchatArticleChoice, quantite: number) {
	tarifs[choice.name] = choice.prix
	stocks[choice.name] = choice.stock
	const target = addArticle(form.lignes, choice, quantite, line)
	if (errors.value.ligne) delete errors.value.ligne[target.key]
	delete errors.value.lignes
	highlighted.value = target.key
	if (highlightTimer) clearTimeout(highlightTimer)
	highlightTimer = setTimeout(() => (highlighted.value = null), 1500)
}
function removeLine(target: DraftLine) {
	form.lignes = form.lignes.filter((item) => item !== target)
}
function lineTotal(target: DraftLine) {
	if (!target.article) return ''
	const quantite = parseNumber(target.quantite)
	const prix = target.prix.trim() ? parseNumber(target.prix) : (tarifs[target.article] ?? 0)
	return Number.isFinite(quantite * prix) ? formatAmount(quantite * prix) : '—'
}

async function submit() {
	if (busy.value) return
	errors.value = validateDevis({ client: form.fournisseur, valable: form.date, lignes: form.lignes }, dayFromToday(0), dateLabel)
	if (errors.value.client) errors.value.client = 'Choisissez le fournisseur.'
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
	busy.value = true
	try {
		const lignes = linesLocked ? undefined : linesForServer(form.lignes)
		if (isDevis) {
			const values = { valable: form.date, taxes: form.taxes, reference: form.reference.trim(), lignes }
			if (devis) emit('saved', await updateDevisFournisseur(devis, values))
			else emit('created', (await createDevisFournisseur({ ...values, fournisseur: form.fournisseur })).name)
		} else {
			const values = { reception: form.date, taxes: form.taxes, lignes }
			if (commande) emit('saved', await updateCommandeAchat(commande, values))
			else emit('created', (await createCommandeAchat({ ...values, fournisseur: form.fournisseur })).name)
		}
		emit('close')
	} catch (e) {
		// La saisie reste en place : rien n'est perdu si le serveur refuse.
		serverError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog :title="editing ? `Modifier ${pieceLabel} ${piece?.name}` : isDevis ? 'Nouveau devis fournisseur' : 'Nouvelle commande d\'achat'" :dirty="dirty" :busy="busy" :hint="editing ? 'Ctrl + Entrée pour enregistrer' : 'Ctrl + Entrée pour créer'" class="devis-dialog" @close="emit('close')" @submit="submit">
		<p v-if="loadError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ loadError }}</p>

		<div class="form-grid">
			<div class="form-field">
				<label class="field-label" for="achat-fournisseur">Fournisseur <span v-if="!editing" class="req">obligatoire</span></label>
				<p v-if="editing" id="achat-fournisseur" class="field-input flex items-center text-ink-gray-7">{{ form.fournisseurLabel }}</p>
				<ChoicePicker
					v-else
					:search="findFournisseurs"
					:picked="form.fournisseurLabel"
					input-id="achat-fournisseur"
					placeholder="Raison sociale ou code"
					:invalid="Boolean(errors.client)"
					@pick="(choice) => ((form.fournisseur = choice.name), (form.fournisseurLabel = choice.label), delete errors.client)"
					@clear="(form.fournisseur = ''), (form.fournisseurLabel = '')"
				/>
				<p v-if="errors.client" class="field-error" role="alert">{{ errors.client }}</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="achat-date">{{ isDevis ? "Valable jusqu'au" : 'Réception prévue le' }} <span class="req">obligatoire</span></label>
				<input id="achat-date" v-model="form.date" class="field-input tabular-nums" type="date" :min="dayFromToday(0)" :aria-invalid="Boolean(errors.valable)" @input="delete errors.valable" />
				<p v-if="errors.valable" class="field-error" role="alert">{{ errors.valable }}</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="achat-taxes">TVA déductible</label>
				<select v-search id="achat-taxes" v-model="form.taxes" class="field-input">
					<option value="">Sans TVA</option>
					<option v-for="item in options?.taxes" :key="item.value" :value="item.value">{{ item.label }}</option>
				</select>
			</div>
			<div v-if="isDevis" class="form-field">
				<label class="field-label" for="achat-reference">Référence fournisseur</label>
				<input id="achat-reference" v-model="form.reference" class="field-input" placeholder="Numéro du devis reçu" autocomplete="off" />
			</div>
		</div>

		<h3 class="form-section">Lignes</h3>
		<p v-if="linesLocked" class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Les lignes reprises d'un devis fournisseur se modifient sur le Desk, pour garder le lien au devis.</span></p>
		<QuickAddBar v-if="!linesLocked" :search="findArticles" input-id="achat-ajout" price-label="Prix d'achat" no-price="pas de prix connu" :invalid="Boolean(errors.lignes)" @add="onAdd" />
		<div class="devis-lines" role="table" :aria-label="`Lignes ${isDevis ? 'du devis fournisseur' : 'de la commande'}`">
			<div v-if="linesLocked || form.lignes.length" class="devis-line devis-line-head" role="row">
				<span role="columnheader">Article</span>
				<span role="columnheader" class="end">Quantité</span>
				<span role="columnheader" class="end">Prix HT (DA)</span>
				<span role="columnheader" class="end">Montant</span>
				<span></span>
			</div>
			<template v-if="linesLocked">
				<div v-for="item in form.lignes" :key="item.key" class="devis-line" role="row">
					<span role="cell" class="truncate">{{ item.designation }}</span>
					<span role="cell" class="end tabular-nums">{{ item.quantite }} {{ item.unite }}</span>
					<span role="cell" class="end tabular-nums">{{ formatAmount(parseNumber(item.prix)) }}</span>
					<span role="cell" class="end tabular-nums text-ink-gray-7">{{ lineTotal(item) }}</span>
					<span></span>
				</div>
			</template>
			<template v-if="!linesLocked">
				<div v-for="item in form.lignes" :key="item.key" class="devis-line" :class="highlighted === item.key && 'devis-line-new'" role="row">
					<div role="cell" class="devis-line-article">
						<strong class="block truncate" :title="item.designation">{{ item.designation }}</strong>
						<small class="block truncate text-ink-gray-6">
							{{ item.article }}<template v-if="stocks[item.article] !== undefined && stocks[item.article] !== null"> · <span :class="(stocks[item.article] ?? 0) <= 0 && 'text-tone-red'">{{ (stocks[item.article] ?? 0) <= 0 ? 'plus en stock' : `${formatQty(stocks[item.article] ?? 0)} en stock` }}</span></template>
						</small>
						<p v-if="errors.ligne?.[item.key]" class="field-error" role="alert">{{ errors.ligne[item.key] }}</p>
					</div>
					<div role="cell" class="flex items-center gap-1">
						<input v-model="item.quantite" class="field-input end tabular-nums" inputmode="decimal" :aria-label="`Quantité, ${item.designation}`" :aria-invalid="Boolean(errors.ligne?.[item.key])" />
						<span class="w-10 truncate text-xs text-ink-gray-6" :title="item.unite">{{ item.unite }}</span>
					</div>
					<input v-model="item.prix" role="cell" class="field-input end tabular-nums" inputmode="decimal" :placeholder="tarifs[item.article] !== null && tarifs[item.article] !== undefined ? formatAmount(tarifs[item.article]) : 'À saisir'" :aria-label="`Prix HT, ${item.designation}`" />
					<span role="cell" class="end tabular-nums font-semibold">{{ lineTotal(item) }}</span>
					<button type="button" role="cell" class="icon-btn" :aria-label="`Retirer ${item.designation}`" @click="removeLine(item)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button>
				</div>
				<p v-if="!form.lignes.length" class="devis-lines-empty">Aucune ligne : cherchez un article dans la barre ci-dessus.</p>
			</template>
		</div>
		<div class="flex flex-wrap items-center justify-between gap-2">
			<span class="text-sm text-ink-gray-6">{{ form.lignes.length }} article{{ form.lignes.length > 1 ? 's' : '' }}</span>
			<p class="text-sm">Total HT : <strong class="tabular-nums">{{ formatAmount(total) }} DA</strong> <span class="text-ink-gray-6">· TVA calculée à l'enregistrement</span></p>
		</div>
		<p v-if="errors.lignes" class="field-error" role="alert">{{ errors.lignes }}</p>
		<p v-if="!linesLocked" class="field-note"><span>Un prix laissé vide reprend le tarif « {{ options?.liste_prix ?? "d'achat" }} », sinon le dernier prix d'achat. Une ligne sans prix empêche la validation.</span></p>

		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>

		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Enregistrement…' : editing ? 'Enregistrer' : isDevis ? 'Créer le devis' : 'Créer la commande' }}</button>
		</template>
	</FormDialog>
</template>
