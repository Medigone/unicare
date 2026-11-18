<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LucidePlus from '~icons/lucide/plus'
import LucideSearch from '~icons/lucide/search'
import { closeRealtime, connectRealtime, isForeignChange, throttledReload, type RealtimeEvent } from '@shared/realtime'
import FormDialog from '@shared/components/FormDialog.vue'
import ListPager from '@shared/components/ListPager.vue'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import { createTarif, getPrix, getTarifs, setPrix, setTarifDefaut } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'
import { formatPrix, parsePrix, PRIX_VUES, prixChange, SENS_LABELS, type PrixLigne, type PrixResponse, type PrixVue, type TarifSens, type TarifsReglages } from '@/lib/tarifs'

/**
 * Réglages › Tarifs et prix : les tarifs de vente et d'achat, et le prix de chaque article dans le tarif ouvert.
 * Le prix se modifie dans sa case : il est enregistré en quittant la case ou sur Entrée. Lecture seule sans droit.
 */
const props = defineProps<{ liste?: string }>()
const route = useRoute()
const router = useRouter()

const reglages = ref<TarifsReglages | null>(null)
const reponse = ref<PrixResponse | null>(null)
const error = ref('')
const actionError = ref('')
const notice = ref('')
const busy = ref(false)

const search = ref(typeof route.query.q === 'string' ? route.query.q : '')
const vue = ref<PrixVue>('tous')
const page = ref(0)

const tarif = computed(() => reglages.value?.tarifs.find((row) => row.name === props.liste) ?? null)
const groupes = computed(() => (['vente', 'achat'] as TarifSens[]).map((sens) => ({ sens, tarifs: reglages.value?.tarifs.filter((row) => row.sens === sens) ?? [] })).filter((groupe) => groupe.tarifs.length))
const canEdit = computed(() => reglages.value?.can_edit_prix ?? false)

/** Sans tarif dans l'adresse (ou un tarif disparu) : le tarif de vente par défaut, sinon le premier. */
function openDefault(fresh: TarifsReglages) {
	if (fresh.tarifs.some((row) => row.name === props.liste)) return false
	const target = fresh.defauts.vente ?? fresh.tarifs[0]?.name
	if (target) router.replace({ name: 'Tarif', params: { liste: target }, query: route.query })
	return Boolean(target)
}

async function loadTarifs() {
	try {
		reglages.value = await getTarifs()
		error.value = ''
		if (!openDefault(reglages.value)) await loadPrix()
	} catch (e) {
		if (!reglages.value) error.value = (e as Error).message
	}
}

// Saisie en cours, par article ; une ligne enregistrée s'éclaire un instant.
const drafts = reactive<Record<string, string>>({})
const rowErrors = reactive<Record<string, string>>({})
const saving = reactive<Record<string, boolean>>({})
const highlighted = ref<string | null>(null)
let highlightTimer: ReturnType<typeof setTimeout> | null = null

function resetDraft(ligne: PrixLigne) {
	drafts[ligne.article] = formatPrix(ligne.prix)
	delete rowErrors[ligne.article]
}

let requestId = 0
async function loadPrix() {
	if (!props.liste) return
	const id = ++requestId
	try {
		const fresh = await getPrix(props.liste, { search: search.value.trim(), vue: vue.value, start: page.value * 50 })
		if (id !== requestId) return
		reponse.value = fresh
		// Une case en cours de saisie garde ce qui est tapé ; les autres reprennent le prix enregistré.
		for (const ligne of fresh.lignes) if (!rowErrors[ligne.article]) resetDraft(ligne)
		error.value = ''
	} catch (e) {
		if (id === requestId) error.value = (e as Error).message
	}
}

watch(
	() => props.liste,
	() => {
		page.value = 0
		reponse.value = null
		loadPrix()
	},
)
let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(search, () => {
	if (searchTimer) clearTimeout(searchTimer)
	searchTimer = setTimeout(() => {
		page.value = 0
		loadPrix()
	}, 250)
})
watch(vue, () => {
	page.value = 0
	loadPrix()
})
watch(page, loadPrix)

async function save(ligne: PrixLigne) {
	const liste = props.liste
	const text = drafts[ligne.article] ?? ''
	if (!liste || !canEdit.value || saving[ligne.article] || !prixChange(text, ligne.prix)) return
	const parsed = parsePrix(text)
	if ('error' in parsed) {
		rowErrors[ligne.article] = parsed.error
		return
	}
	if (parsed.value === null && !(await confirmAction({ title: 'Retirer le prix', message: `${ligne.designation} n'aura plus de prix dans le tarif « ${liste} ». Les nouvelles pièces demanderont de le saisir.`, confirmLabel: 'Retirer le prix', danger: true }))) {
		resetDraft(ligne)
		return
	}
	saving[ligne.article] = true
	delete rowErrors[ligne.article]
	try {
		const fresh = await setPrix(liste, ligne, text)
		const rows = reponse.value?.lignes ?? []
		const index = rows.findIndex((row) => row.article === fresh.article)
		if (index >= 0) rows[index] = fresh
		resetDraft(fresh)
		notice.value = fresh.prix === null ? 'Prix retiré.' : 'Prix enregistré.'
		highlighted.value = fresh.article
		if (highlightTimer) clearTimeout(highlightTimer)
		highlightTimer = setTimeout(() => (highlighted.value = null), 1500)
		refreshCounts()
	} catch (e) {
		rowErrors[ligne.article] = (e as Error).message
	} finally {
		saving[ligne.article] = false
	}
}
function onKey(event: KeyboardEvent, ligne: PrixLigne) {
	if (event.key === 'Enter') (event.target as HTMLInputElement).blur()
	if (event.key === 'Escape') {
		resetDraft(ligne)
		;(event.target as HTMLInputElement).blur()
	}
}
// Compteurs des vues et nombre de prix par tarif, sans recharger les lignes affichées.
async function refreshCounts() {
	try {
		reglages.value = await getTarifs()
		if (props.liste && reponse.value) reponse.value.compte = (await getPrix(props.liste, { search: search.value.trim(), vue: vue.value, start: page.value * 50 })).compte
	} catch {
		// Les compteurs se remettront à jour au prochain chargement.
	}
}

async function makeDefault() {
	const current = tarif.value
	if (!current || busy.value) return
	const label = current.sens === 'vente' ? 'les ventes' : 'les achats'
	if (!(await confirmAction({ title: 'Tarif par défaut', message: `Les nouveaux ${current.sens === 'vente' ? 'devis et commandes clients' : 'devis fournisseur et commandes d\'achat'} reprendront les prix du tarif « ${current.name} ». Les pièces déjà créées ne changent pas.`, confirmLabel: `Utiliser pour ${label}` }))) return
	busy.value = true
	actionError.value = ''
	try {
		reglages.value = await setTarifDefaut(current.sens, current.name)
		notice.value = `« ${current.name} » est le tarif par défaut pour ${label}.`
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}

// Nouveau tarif.
const creating = ref(false)
const nouveau = reactive({ nom: '', sens: 'vente' as TarifSens, error: '' })
function startCreate() {
	Object.assign(nouveau, { nom: '', sens: tarif.value?.sens ?? 'vente', error: '' })
	creating.value = true
}
async function submitCreate() {
	if (busy.value) return
	const nom = nouveau.nom.trim()
	if (!nom) {
		nouveau.error = 'Donnez un nom au tarif.'
		return
	}
	busy.value = true
	try {
		reglages.value = await createTarif(nom, nouveau.sens)
		creating.value = false
		notice.value = `Tarif « ${nom} » créé.`
		router.push({ name: 'Tarif', params: { liste: nom } })
	} catch (e) {
		nouveau.error = (e as Error).message
	} finally {
		busy.value = false
	}
}

const reload = throttledReload(loadPrix, { delayMs: 1000, minIntervalMs: 4000 })
onMounted(() => {
	loadTarifs()
	connectRealtime<RealtimeEvent>(
		'unicare_bureau_update',
		(event) => {
			if (isForeignChange(event, window.user) && event.doctype === 'Item Price') reload()
		},
		loadTarifs,
	)
})
onBeforeUnmount(closeRealtime)
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Tarifs et prix' }]" active="tarifs">
		<div class="bureau-work tdb">
			<div>
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Tarifs et prix</h1>
				<p class="text-sm text-ink-gray-6">Le prix d'un article dans le tarif par défaut est celui que proposent les nouveaux devis et commandes. Un article sans prix doit être chiffré à la main sur chaque pièce.</p>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!reglages" class="card p-4 text-ink-gray-6">Chargement des tarifs…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<section v-if="reglages" class="card reglages-card" aria-labelledby="t-tarifs">
				<div class="flex flex-wrap items-center gap-2">
					<h2 id="t-tarifs" class="flex-auto text-base font-semibold">Tarifs</h2>
					<button v-if="reglages.can_create_tarif" type="button" class="btn-secondary" :disabled="busy" @click="startCreate"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Nouveau tarif</button>
				</div>
				<div class="flex flex-wrap gap-x-6 gap-y-2.5">
					<div v-for="groupe in groupes" :key="groupe.sens" class="flex flex-wrap items-center gap-1.5" role="group" :aria-label="`Tarifs ${groupe.sens === 'vente' ? 'de vente' : 'd\'achat'}`">
						<span class="w-14 text-xs font-semibold uppercase tracking-wide text-ink-gray-6">{{ SENS_LABELS[groupe.sens] }}</span>
						<RouterLink v-for="row in groupe.tarifs" :key="row.name" :to="{ name: 'Tarif', params: { liste: row.name } }" class="reglages-tab" :aria-current="row.name === liste ? 'page' : undefined">
							{{ row.name }}<span v-if="row.defaut" class="text-xs text-ink-gray-6"> · par défaut</span>
						</RouterLink>
					</div>
				</div>
				<p v-if="!reglages.tarifs.length" class="text-ink-gray-6">Aucun tarif : créez-en un pour donner des prix aux articles.</p>
				<div v-if="tarif" class="flex flex-wrap items-center gap-2 border-t border-[var(--line-soft)] pt-3 text-sm">
					<span class="text-ink-gray-7">Tarif {{ tarif.sens === 'vente' ? 'de vente' : "d'achat" }} en {{ tarif.devise }} · {{ tarif.prix }} article{{ tarif.prix > 1 ? 's' : '' }} avec un prix</span>
					<span class="flex-auto"></span>
					<span v-if="tarif.defaut" class="font-semibold text-tone-green">Repris par les nouvelles pièces {{ tarif.sens === 'vente' ? 'de vente' : "d'achat" }}</span>
					<button v-else-if="reglages.can_set_defaut[tarif.sens]" type="button" class="btn-secondary" :disabled="busy" @click="makeDefault">Utiliser par défaut pour {{ tarif.sens === 'vente' ? 'les ventes' : 'les achats' }}</button>
				</div>
			</section>

			<section v-if="tarif" class="card reglages-card" aria-labelledby="t-prix">
				<div class="flex flex-wrap items-center gap-2">
					<h2 id="t-prix" class="sr-only">Prix du tarif {{ tarif.name }}</h2>
					<label class="bureau-search">
						<LucideSearch class="h-3.5 w-3.5" aria-hidden="true" />
						<input id="tarifs-recherche" v-model="search" class="field-input" type="search" aria-label="Chercher un article" placeholder="Article ou code" />
					</label>
					<div class="seg" role="group" aria-label="Afficher">
						<button v-for="item in PRIX_VUES" :key="item.key" type="button" :aria-pressed="vue === item.key" @click="vue = item.key">
							{{ item.label }}<span v-if="reponse" class="tabular-nums text-ink-gray-6"> {{ reponse.compte[item.key] }}</span>
						</button>
					</div>
					<span class="flex-auto"></span>
					<span v-if="!canEdit" class="text-xs text-ink-gray-6">Lecture seule : votre rôle ne modifie pas les prix.</span>
				</div>
				<p class="field-note">
					<span v-if="tarif.sens === 'vente'">Les articles vendus. Saisissez le prix hors taxes, puis Entrée ; videz la case pour retirer le prix.</span>
					<span v-else>Les articles achetés. Sans prix dans le tarif, les pièces d'achat reprennent le dernier prix payé.</span>
				</p>

				<p v-if="!reponse" class="text-ink-gray-6">Chargement des prix…</p>
				<div v-else-if="reponse.lignes.length" class="overflow-x-auto">
					<table class="ref-table tarifs-table">
						<thead>
							<tr>
								<th>Article</th>
								<th>Unité</th>
								<th class="end">Prix HT ({{ tarif.devise }})</th>
								<th v-if="tarif.sens === 'achat'" class="end">Dernier prix payé</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="ligne in reponse.lignes" :key="ligne.article" :class="highlighted === ligne.article && 'devis-line-new'">
								<td>
									<RouterLink :to="{ name: 'Article', params: { id: ligne.article } }" class="font-medium">{{ ligne.designation }}</RouterLink>
									<small class="block text-ink-gray-6">{{ ligne.article }}</small>
								</td>
								<td>
									{{ ligne.unite }}
									<small v-if="ligne.unite_prix && ligne.unite_prix !== ligne.unite" class="block text-tone-amber">prix donné par {{ ligne.unite_prix }}</small>
								</td>
								<td class="end">
									<input
										v-if="canEdit"
										v-model="drafts[ligne.article]"
										class="field-input tarifs-prix end tabular-nums"
										inputmode="decimal"
										:placeholder="tarif.sens === 'achat' && ligne.dernier_achat ? formatPrix(ligne.dernier_achat) : 'Sans prix'"
										:aria-label="`Prix, ${ligne.designation}`"
										:aria-invalid="Boolean(rowErrors[ligne.article])"
										:disabled="saving[ligne.article]"
										@blur="save(ligne)"
										@keydown="onKey($event, ligne)"
									/>
									<span v-else class="tabular-nums" :class="ligne.prix === null && 'text-ink-gray-6'">{{ ligne.prix === null ? 'Sans prix' : formatPrix(ligne.prix) }}</span>
									<p v-if="rowErrors[ligne.article]" class="field-error text-left" role="alert">{{ rowErrors[ligne.article] }}</p>
								</td>
								<td v-if="tarif.sens === 'achat'" class="end tabular-nums text-ink-gray-6">{{ formatPrix(ligne.dernier_achat) || '—' }}</td>
							</tr>
						</tbody>
					</table>
				</div>
				<p v-else class="text-ink-gray-6">{{ vue === 'sans_prix' ? 'Tous les articles ont un prix dans ce tarif.' : 'Aucun article ne correspond.' }}</p>
				<ListPager v-if="reponse && reponse.total > reponse.page" :total="reponse.total" :page="page" :page-size="reponse.page" :sizes="[reponse.page]" sort-label="Par désignation" @update:page="(value) => (page = value)" />
			</section>
		</div>

		<FormDialog v-if="creating" title="Nouveau tarif" :dirty="Boolean(nouveau.nom.trim())" :busy="busy" @close="creating = false" @submit="submitCreate">
			<div class="form-grid">
				<div class="form-field">
					<label class="field-label" for="tarif-nom">Nom du tarif <span class="req">obligatoire</span></label>
					<input id="tarif-nom" v-model="nouveau.nom" class="field-input" placeholder="Ex. Tarif grossistes" autocomplete="off" @input="nouveau.error = ''" />
				</div>
				<fieldset class="form-field">
					<legend class="field-label">Pour</legend>
					<div class="flex gap-4 text-sm">
						<label class="flex items-center gap-1.5"><input v-model="nouveau.sens" type="radio" value="vente" /> les ventes</label>
						<label class="flex items-center gap-1.5"><input v-model="nouveau.sens" type="radio" value="achat" /> les achats</label>
					</div>
				</fieldset>
			</div>
			<p class="field-note">Le tarif est créé vide, dans la devise de la société. Vous y saisirez ensuite les prix.</p>
			<p v-if="nouveau.error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ nouveau.error }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="submitCreate">{{ busy ? 'Création…' : 'Créer le tarif' }}</button>
			</template>
		</FormDialog>
		<AppToast :message="notice" tone="success" @close="notice = ''" />
	</BureauShell>
</template>
