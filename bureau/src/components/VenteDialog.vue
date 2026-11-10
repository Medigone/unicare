<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import LucideInfo from '~icons/lucide/info'
import LucidePlus from '~icons/lucide/plus'
import LucideTrash2 from '~icons/lucide/trash-2'
import FormDialog from '@shared/components/FormDialog.vue'
import ChoicePicker from './ChoicePicker.vue'
import { createCommande, createDevis, getCommandeOptions, getDevisOptions, searchClients, searchDevisArticles, updateCommande, updateDevis } from '@/lib/api'
import { formatAmount } from '@/lib/clients'
import type { CommandeDetail } from '@/lib/commandes'
import { dayFromToday, draftTotal, linesForServer, parseNumber, validateDevis, type DevisArticleChoice, type DevisDetail, type DevisFormErrors, type DraftLine } from '@/lib/devis'

/**
 * Saisie d'un devis ou d'une commande : client, date (validité ou livraison), TVA et lignes, au prix du tarif.
 * Sans `piece`, la fenêtre crée ; avec, elle modifie le brouillon. Le client ne change plus une fois la pièce créée.
 */
const props = defineProps<{ kind: 'devis' | 'commande'; piece?: DevisDetail | CommandeDetail; client?: { name: string; label: string } }>()
const emit = defineEmits<{ close: []; created: [name: string]; saved: [piece: DevisDetail | CommandeDetail] }>()

const isDevis = props.kind === 'devis'
const devis = isDevis ? (props.piece as DevisDetail | undefined) : undefined
const commande = isDevis ? undefined : (props.piece as CommandeDetail | undefined)
const editing = computed(() => Boolean(props.piece))
// Les lignes reprises d'un devis gardent leur lien : elles se modifient sur le Desk.
const linesLocked = Boolean(commande?.lignes.some((row) => row.devis))

let nextKey = 0
function line(values: Partial<DraftLine> = {}): DraftLine {
	return { key: ++nextKey, article: '', designation: '', unite: '', quantite: '1', prix: '', ...values }
}
const form = reactive({
	client: props.piece?.client ?? props.client?.name ?? '',
	clientLabel: props.piece?.client_label ?? props.client?.label ?? '',
	date: (isDevis ? devis?.valable : commande?.livraison) ?? '',
	taxes: props.piece?.taxes_modele ?? '',
	reference: commande?.reference ?? '',
	lignes: props.piece ? props.piece.lignes.map((row) => line({ article: row.article, designation: row.designation, unite: row.unite ?? '', quantite: String(row.quantite), prix: String(row.prix) })) : [line()],
})
// Le tarif de chaque article choisi : il sert de prix quand le champ reste vide.
const tarifs = reactive<Record<string, number | null>>(Object.fromEntries((props.piece?.lignes ?? []).map((row) => [row.article, row.prix_tarif || null])))
const initial = JSON.parse(JSON.stringify(form)) as typeof form
const dirty = computed(() => JSON.stringify(form) !== JSON.stringify(initial))
const options = ref<{ taxes: { value: string; label: string }[]; taxes_defaut: string | null; liste_prix: string | null; validite_jours?: number } | null>(null)
const loadError = ref('')
const serverError = ref('')
const errors = ref<DevisFormErrors>({})
const busy = ref(false)
const total = computed(() => draftTotal(form.lignes, tarifs))
const dateLabel = isDevis ? 'la date de validité' : 'la date de livraison'

onMounted(async () => {
	try {
		options.value = isDevis ? await getDevisOptions() : await getCommandeOptions()
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

const findClients = async (query: string) => (await searchClients(query || ' ')).filter((client) => !client.disabled).map((client) => ({ ...client, hint: client.wilaya }))
const findArticles = async (query: string) => (await searchDevisArticles(query)).map((article) => ({ ...article, hint: article.prix === null ? 'sans prix au tarif' : `${formatAmount(article.prix)} DA` }))

function pickArticle(target: DraftLine, choice: DevisArticleChoice) {
	target.article = choice.name
	target.designation = choice.label
	target.unite = choice.uom ?? ''
	tarifs[choice.name] = choice.prix
	if (errors.value.ligne) delete errors.value.ligne[target.key]
	delete errors.value.lignes
	// Une ligne choisie en dernier en ajoute une vide : la saisie continue sans souris.
	if (form.lignes[form.lignes.length - 1] === target) form.lignes.push(line())
}
function clearArticle(target: DraftLine) {
	target.article = ''
	target.designation = ''
	target.unite = ''
	target.prix = ''
}
function removeLine(target: DraftLine) {
	form.lignes = form.lignes.filter((item) => item !== target)
	if (!form.lignes.length) form.lignes.push(line())
}
function lineTotal(target: DraftLine) {
	if (!target.article) return ''
	const quantite = parseNumber(target.quantite)
	const prix = target.prix.trim() ? parseNumber(target.prix) : (tarifs[target.article] ?? 0)
	return Number.isFinite(quantite * prix) ? formatAmount(quantite * prix) : '—'
}

async function submit() {
	if (busy.value) return
	errors.value = validateDevis({ client: form.client, valable: form.date, lignes: form.lignes }, dayFromToday(0), dateLabel)
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
	const lignes = linesLocked ? undefined : linesForServer(form.lignes)
	busy.value = true
	try {
		if (isDevis) {
			const values = { valable: form.date, taxes: form.taxes, lignes }
			if (devis) emit('saved', await updateDevis(devis, values))
			else emit('created', (await createDevis({ ...values, client: form.client })).name)
		} else {
			const values = { livraison: form.date, taxes: form.taxes, reference: form.reference.trim(), lignes }
			if (commande) emit('saved', await updateCommande(commande, values))
			else emit('created', (await createCommande({ ...values, client: form.client })).name)
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
	<FormDialog :title="editing ? `Modifier ${isDevis ? 'le devis' : 'la commande'} ${piece?.name}` : isDevis ? 'Nouveau devis' : 'Nouvelle commande'" :dirty="dirty" :busy="busy" :hint="editing ? 'Ctrl + Entrée pour enregistrer' : 'Ctrl + Entrée pour créer'" class="devis-dialog" @close="emit('close')" @submit="submit">
		<p v-if="loadError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ loadError }}</p>

		<div class="form-grid">
			<div class="form-field">
				<label class="field-label" for="vente-client">Client <span v-if="!editing" class="req">obligatoire</span></label>
				<p v-if="editing" id="vente-client" class="field-input flex items-center text-ink-gray-7">{{ form.clientLabel }}</p>
				<ChoicePicker
					v-else
					:search="findClients"
					:picked="form.clientLabel"
					input-id="vente-client"
					placeholder="Raison sociale ou code"
					:invalid="Boolean(errors.client)"
					@pick="(choice) => ((form.client = choice.name), (form.clientLabel = choice.label), delete errors.client)"
					@clear="(form.client = ''), (form.clientLabel = '')"
				/>
				<p v-if="errors.client" class="field-error" role="alert">{{ errors.client }}</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="vente-date">{{ isDevis ? "Valable jusqu'au" : 'Livraison prévue le' }} <span class="req">obligatoire</span></label>
				<input id="vente-date" v-model="form.date" class="field-input tabular-nums" type="date" :min="dayFromToday(0)" :aria-invalid="Boolean(errors.valable)" @input="delete errors.valable" />
				<p v-if="errors.valable" class="field-error" role="alert">{{ errors.valable }}</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="vente-taxes">TVA</label>
				<select id="vente-taxes" v-model="form.taxes" class="field-input">
					<option value="">Sans TVA</option>
					<option v-for="item in options?.taxes" :key="item.value" :value="item.value">{{ item.label }}</option>
				</select>
			</div>
			<div v-if="!isDevis" class="form-field">
				<label class="field-label" for="vente-reference">Référence client</label>
				<input id="vente-reference" v-model="form.reference" class="field-input" placeholder="Bon de commande du client" autocomplete="off" />
			</div>
		</div>

		<h3 class="form-section">Lignes</h3>
		<p v-if="linesLocked" class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Les lignes reprises d'un devis se modifient sur le Desk, pour garder le lien au devis.</span></p>
		<div class="devis-lines" role="table" :aria-label="`Lignes ${isDevis ? 'du devis' : 'de la commande'}`">
			<div class="devis-line devis-line-head" role="row">
				<span role="columnheader">Article</span>
				<span role="columnheader" class="end">Quantité</span>
				<span role="columnheader" class="end">Prix HT (DA)</span>
				<span role="columnheader" class="end">Montant</span>
				<span></span>
			</div>
			<template v-if="linesLocked">
				<div v-for="item in form.lignes" :key="item.key" class="devis-line" role="row">
					<span role="cell" class="truncate pt-1.5">{{ item.designation }}</span>
					<span role="cell" class="end tabular-nums">{{ item.quantite }} {{ item.unite }}</span>
					<span role="cell" class="end tabular-nums">{{ formatAmount(parseNumber(item.prix)) }}</span>
					<span role="cell" class="end tabular-nums text-ink-gray-7">{{ lineTotal(item) }}</span>
					<span></span>
				</div>
			</template>
			<template v-else>
				<div v-for="(item, index) in form.lignes" :key="item.key" class="devis-line" role="row">
					<div role="cell" class="min-w-0">
						<ChoicePicker :search="findArticles" :picked="item.designation" :input-id="`vente-article-${item.key}`" placeholder="Article ou code" compact @pick="(choice) => pickArticle(item, choice)" @clear="clearArticle(item)" />
						<p v-if="errors.ligne?.[item.key]" class="field-error" role="alert">{{ errors.ligne[item.key] }}</p>
					</div>
					<div role="cell" class="flex items-center gap-1">
						<input v-model="item.quantite" class="field-input end tabular-nums" inputmode="decimal" :aria-label="`Quantité, ligne ${index + 1}`" :aria-invalid="Boolean(errors.ligne?.[item.key])" />
						<span class="w-10 truncate text-xs text-ink-gray-6" :title="item.unite">{{ item.unite }}</span>
					</div>
					<input v-model="item.prix" role="cell" class="field-input end tabular-nums" inputmode="decimal" :placeholder="item.article && tarifs[item.article] !== null && tarifs[item.article] !== undefined ? formatAmount(tarifs[item.article]) : item.article ? 'À saisir' : ''" :aria-label="`Prix HT, ligne ${index + 1}`" />
					<span role="cell" class="end tabular-nums text-ink-gray-7">{{ lineTotal(item) }}</span>
					<button type="button" role="cell" class="icon-btn" :aria-label="`Retirer la ligne ${index + 1}`" @click="removeLine(item)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button>
				</div>
			</template>
		</div>
		<div class="flex flex-wrap items-center justify-between gap-2">
			<button v-if="!linesLocked" type="button" class="btn-ghost" @click="form.lignes.push(line())"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Ajouter une ligne</button>
			<span v-else></span>
			<p class="text-sm">Total HT : <strong class="tabular-nums">{{ formatAmount(total) }} DA</strong> <span class="text-ink-gray-6">· TVA calculée à l'enregistrement</span></p>
		</div>
		<p v-if="errors.lignes" class="field-error" role="alert">{{ errors.lignes }}</p>
		<p v-if="!linesLocked" class="field-note"><span>Un prix laissé vide reprend celui du tarif « {{ options?.liste_prix ?? 'de vente' }} ». Une ligne sans prix empêche la validation {{ isDevis ? 'du devis' : 'de la commande' }}.</span></p>

		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>

		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Enregistrement…' : editing ? 'Enregistrer' : `Créer ${isDevis ? 'le devis' : 'la commande'}` }}</button>
		</template>
	</FormDialog>
</template>
