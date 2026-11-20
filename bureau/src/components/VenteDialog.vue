<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import LucideInfo from '~icons/lucide/info'
import LucideTrash2 from '~icons/lucide/trash-2'
import FormDialog from '@shared/components/FormDialog.vue'
import ChoicePicker from './ChoicePicker.vue'
import ClientDialog from './ClientDialog.vue'
import PrixTarifDialog from './PrixTarifDialog.vue'
import QuickAddBar from './QuickAddBar.vue'
import { createCommande, createDevis, getCommandeOptions, getDevisOptions, getPrixVente, searchClients, searchDevisArticles, updateCommande, updateDevis } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { formatAmount, type ClientChoice } from '@/lib/clients'
import type { CommandeDetail } from '@/lib/commandes'
import { canCreate, canRead } from '@/lib/droits'
import { addArticle, applyTarifs, dayFromToday, draftTotal, linesForServer, parseNumber, prixManuels, validateDevis, type DevisArticleChoice, type DevisDetail, type DevisFormErrors, type DraftLine } from '@/lib/devis'

/**
 * Saisie d'un devis ou d'une commande : client, date (validité ou livraison), TVA, liste de prix et lignes, au prix
 * de cette liste. La liste vient du client s'il en a une, sinon des réglages de vente ; elle se change à la main.
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
	liste: props.piece?.liste_prix ?? '',
	reference: commande?.reference ?? '',
	lignes: props.piece ? props.piece.lignes.map((row) => line({ article: row.article, designation: row.designation, unite: row.unite ?? '', quantite: String(row.quantite), prix: String(row.prix) })) : ([] as DraftLine[]),
})
// Le tarif de chaque article choisi : il sert de prix quand le champ reste vide.
const tarifs = reactive<Record<string, number | null>>(Object.fromEntries((props.piece?.lignes ?? []).map((row) => [row.article, row.prix_tarif || null])))
const initial = JSON.parse(JSON.stringify(form)) as typeof form
// Prix des lignes à l'ouverture : seuls les prix saisis depuis se reportent dans la liste.
const prixAvant: Record<number, string> = Object.fromEntries(form.lignes.map((line) => [line.key, line.prix]))
const dirty = computed(() => JSON.stringify(form) !== JSON.stringify(initial))
const options = ref<{ taxes: { value: string; label: string }[]; taxes_defaut: string | null; liste_prix: string | null; listes_prix: string[]; validite_jours?: number } | null>(null)
// La liste de la pièce reste proposée même désactivée depuis : la fenêtre ne la change pas d'elle-même.
const listes = computed(() => {
	const actives = options.value?.listes_prix ?? []
	return form.liste && !actives.includes(form.liste) ? [form.liste, ...actives] : actives
})
const loadError = ref('')
const serverError = ref('')
const errors = ref<DevisFormErrors>({})
const busy = ref(false)
const total = computed(() => draftTotal(form.lignes, tarifs))
// Une ligne sans prix saisi ni prix du tarif : le lien vers le tarif s'affiche.
const sansPrix = computed(() => form.lignes.some((line) => line.article && !line.prix.trim() && (tarifs[line.article] ?? null) === null))
const dateLabel = isDevis ? 'la date de validité' : 'la date de livraison'

onMounted(async () => {
	try {
		options.value = isDevis ? await getDevisOptions() : await getCommandeOptions()
		if (!editing.value) {
			form.date ||= dayFromToday(isDevis ? (options.value.validite_jours ?? 30) : 7)
			form.taxes ||= options.value.taxes_defaut ?? ''
			form.liste ||= (await listeDuClient()) || options.value.liste_prix || ''
			// Préremplis : ce n'est pas une saisie, la fermeture ne demande pas de confirmation.
			initial.date = form.date
			initial.taxes = form.taxes
			initial.liste = form.liste
		}
	} catch (e) {
		loadError.value = (e as Error).message
	}
})

/** Client déjà choisi à l'ouverture (depuis sa fiche) : sa propre liste de vente, s'il en a une active. */
async function listeDuClient() {
	if (!props.client?.name) return ''
	try {
		const found = (await searchClients(props.client.label)).find((item) => item.name === props.client?.name)
		return found?.liste_prix && options.value?.listes_prix.includes(found.liste_prix) ? found.liste_prix : ''
	} catch {
		return ''
	}
}

const findClients = async (query: string) => (await searchClients(query || ' ')).filter((client) => !client.disabled).map((client) => ({ ...client, hint: client.wilaya }))
const findArticles = (query: string) => searchDevisArticles(query, form.liste, form.client)

// Autre liste ou autre client : les prix du tarif changent. Une seule réponse compte, celle du dernier changement.
const tarifsError = ref('')
let lastTarifs = 0
async function refreshTarifs() {
	const articles = [...new Set(form.lignes.map((line) => line.article).filter(Boolean))]
	tarifsError.value = ''
	if (!articles.length || linesLocked) return
	const request = ++lastTarifs
	try {
		const prix = await getPrixVente(articles, form.liste, form.client)
		if (request === lastTarifs) applyTarifs(form.lignes, tarifs, prix)
	} catch (e) {
		if (request === lastTarifs) tarifsError.value = (e as Error).message
	}
}
function changeListe(liste: string) {
	if (liste === form.liste) return
	form.liste = liste
	refreshTarifs()
}

// Client absent de la recherche : il se crée par-dessus la pièce, qui garde sa saisie, puis il est choisi.
const newClient = ref<string | null>(null)
const createdClient = ref('')
function pickClient(choice: { name: string; label: string; liste_prix?: string | null }) {
	form.client = choice.name
	form.clientLabel = choice.label
	delete errors.value.client
	// Le client a sa liste : elle s'applique. Sinon la liste en cours reste, avec les prix propres à ce client.
	if (choice.liste_prix && options.value?.listes_prix.includes(choice.liste_prix) && choice.liste_prix !== form.liste) changeListe(choice.liste_prix)
	else refreshTarifs()
}
async function onClientCreated(name: string, client: ClientChoice) {
	createdClient.value = name
	pickClient(client)
	await nextTick()
	document.querySelector<HTMLElement>('#vente-date')?.focus()
}
// Stock de chaque article ajouté par la barre : affiché sous sa désignation.
const stocks = reactive<Record<string, number | null | undefined>>({})
const highlighted = ref<number | null>(null)
let highlightTimer: ReturnType<typeof setTimeout> | null = null

/** Ajout par la barre : un article déjà présent voit sa quantité augmenter, et sa ligne s'éclaire un instant. */
function onAdd(choice: DevisArticleChoice, quantite: number) {
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

// Prix saisis à la main : un article absent de la liste y est ajouté ; un prix autre que celui de la liste attend le
// choix de la personne (mettre la liste à jour, ou garder ce prix pour cette pièce). `null` : retour à la saisie.
const ecarts = ref<ReturnType<typeof prixManuels> | null>(null)
let choixEcarts: ((choice: 'liste' | 'piece' | null) => void) | null = null
async function tarifsAReporter(): Promise<string[] | null> {
	if (linesLocked || !form.liste || !canCreate('Item Price')) return []
	const found = prixManuels(form.lignes, tarifs, prixAvant)
	if (!found.differents.length) return found.nouveaux
	ecarts.value = found
	const choice = await new Promise<'liste' | 'piece' | null>((resolve) => (choixEcarts = resolve))
	ecarts.value = null
	if (!choice) return null
	return choice === 'liste' ? [...found.nouveaux, ...found.differents.map((item) => item.article)] : found.nouveaux
}
function choisirEcarts(choice: 'liste' | 'piece' | null) {
	choixEcarts?.(choice)
	choixEcarts = null
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
	const reportes = await tarifsAReporter()
	if (!reportes) return
	busy.value = true
	try {
		if (isDevis) {
			const values = { valable: form.date, taxes: form.taxes, liste_prix: form.liste || undefined, tarifs: reportes, lignes }
			if (devis) emit('saved', await updateDevis(devis, values))
			else emit('created', (await createDevis({ ...values, client: form.client })).name)
		} else {
			const values = { livraison: form.date, taxes: form.taxes, liste_prix: form.liste || undefined, tarifs: reportes, reference: form.reference.trim(), lignes }
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
					:create-label="canCreate('Customer') ? 'Créer le client' : undefined"
					@pick="pickClient"
					@clear="(form.client = ''), (form.clientLabel = '')"
					@create="(query) => (newClient = query)"
				/>
				<p v-if="errors.client" class="field-error" role="alert">{{ errors.client }}</p>
				<p v-else-if="form.client && form.client === createdClient" class="field-note">
					<LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" />
					<span>Client créé. <a class="ref-link" :href="`/bureau/clients/${encodeURIComponent(createdClient)}`" target="_blank" rel="noopener noreferrer">Compléter la fiche</a></span>
				</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="vente-date">{{ isDevis ? "Valable jusqu'au" : 'Livraison prévue le' }} <span class="req">obligatoire</span></label>
				<input id="vente-date" v-model="form.date" class="field-input tabular-nums" type="date" :min="dayFromToday(0)" :aria-invalid="Boolean(errors.valable)" @input="delete errors.valable" />
				<p v-if="errors.valable" class="field-error" role="alert">{{ errors.valable }}</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="vente-taxes">TVA</label>
				<select v-search id="vente-taxes" v-model="form.taxes" class="field-input">
					<option value="">Sans TVA</option>
					<option v-for="item in options?.taxes" :key="item.value" :value="item.value">{{ item.label }}</option>
				</select>
			</div>
			<div class="form-field">
				<label class="field-label" for="vente-liste">Liste de prix</label>
				<select v-search id="vente-liste" :value="form.liste" class="field-input" :disabled="linesLocked" @change="changeListe(($event.target as HTMLSelectElement).value)">
					<option v-if="!listes.length" value="">Aucune liste de vente active</option>
					<option v-for="item in listes" :key="item" :value="item">{{ item }}</option>
				</select>
				<p v-if="tarifsError" class="field-error" role="alert">{{ tarifsError }}</p>
				<p v-else-if="linesLocked" class="field-note"><span>Reprise du devis : elle se change sur le Desk.</span></p>
			</div>
			<div v-if="!isDevis" class="form-field">
				<label class="field-label" for="vente-reference">Référence client</label>
				<input id="vente-reference" v-model="form.reference" class="field-input" placeholder="Bon de commande du client" autocomplete="off" />
			</div>
		</div>

		<h3 class="form-section">Lignes</h3>
		<p v-if="linesLocked" class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Les lignes reprises d'un devis se modifient sur le Desk, pour garder le lien au devis.</span></p>
		<QuickAddBar v-if="!linesLocked" :search="findArticles" input-id="vente-ajout" :invalid="Boolean(errors.lignes)" @add="onAdd" />
		<div class="devis-lines" role="table" :aria-label="`Lignes ${isDevis ? 'du devis' : 'de la commande'}`">
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
			<template v-else>
				<div v-for="(item, index) in form.lignes" :key="item.key" class="devis-line" :class="highlighted === item.key && 'devis-line-new'" role="row">
					<div role="cell" class="devis-line-article">
						<strong class="block truncate" :title="item.designation">{{ item.designation }}</strong>
						<small class="block truncate text-ink-gray-6">
							{{ item.article }}<template v-if="stocks[item.article] !== undefined && stocks[item.article] !== null"> · <span :class="(stocks[item.article] ?? 0) <= 0 && 'text-tone-red'">{{ (stocks[item.article] ?? 0) <= 0 ? 'rupture de stock' : `${formatQty(stocks[item.article] ?? 0)} en stock` }}</span></template>
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
		<p v-if="!linesLocked" class="field-note"><span>Un prix laissé vide reprend celui de la liste « {{ form.liste || 'de vente' }} »<template v-if="form.liste && canCreate('Item Price')"> ; un prix saisi pour un article absent de la liste y est ajouté</template>. Une ligne sans prix empêche la validation {{ isDevis ? 'du devis' : 'de la commande' }}.</span><a v-if="sansPrix && form.liste && canRead('Item Price')" :href="`/bureau/tarifs/${encodeURIComponent(form.liste)}`" target="_blank" rel="noopener" class="font-medium underline">Ajouter les prix manquants au tarif</a></p>

		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>

		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Enregistrement…' : editing ? 'Enregistrer' : `Créer ${isDevis ? 'le devis' : 'la commande'}` }}</button>
		</template>
		<Teleport to="body">
			<ClientDialog v-if="newClient !== null" quick :name="newClient" @close="newClient = null" @created="onClientCreated" @pick="pickClient" />
			<PrixTarifDialog v-if="ecarts" :liste="form.liste" :piece="isDevis ? 'ce devis' : 'cette commande'" :lignes="ecarts.differents" :nouveaux="ecarts.nouveaux.length" @close="choisirEcarts(null)" @choose="choisirEcarts" />
		</Teleport>
	</FormDialog>
</template>
