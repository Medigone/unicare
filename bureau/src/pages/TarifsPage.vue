<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LucideChevronRight from '~icons/lucide/chevron-right'
import LucidePencil from '~icons/lucide/pencil'
import LucidePlus from '~icons/lucide/plus'
import LucideSearch from '~icons/lucide/search'
import LucideTrash2 from '~icons/lucide/trash-2'
import { closeRealtime, connectRealtime, isForeignChange, throttledReload, type RealtimeEvent } from '@shared/realtime'
import ListPager from '@shared/components/ListPager.vue'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import NouveauTarifDialog from '@/components/NouveauTarifDialog.vue'
import PrixLigneDialog from '@/components/PrixLigneDialog.vue'
import TarifCalcule from '@/components/TarifCalcule.vue'
import { deleteLigne, deleteTarif, getLignes, getPrix, getTarifs, reprendreDerniersPrix, setPrix, setTarifActif, setTarifDefaut } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'
import {
	formatDate,
	formatEcart,
	formatPeriode,
	formatPrix,
	joursAvant,
	parsePrix,
	PRIX_VUES,
	prixChange,
	STATUT_LABELS,
	validite,
	type LignePrix,
	type LignesArticle,
	type PrixLigne,
	type PrixResponse,
	type PrixVue,
	type Tarif,
	type TarifSens,
	type TarifsReglages,
} from '@/lib/tarifs'

/**
 * Réglages › Tarifs et prix : les tarifs de vente et d'achat, et les prix des articles dans le tarif ouvert.
 * La case de prix modifie le prix général en vigueur aujourd'hui (enregistré en quittant la case ou sur Entrée) ;
 * la flèche d'une ligne ouvre tous les prix de l'article : périodes, prix d'un client ou d'un fournisseur, historique.
 * Lecture seule sans droit, sur un tarif désactivé, ou quand la page montre les prix d'une autre date.
 */
const props = defineProps<{ liste?: string }>()
const route = useRoute()
const router = useRouter()

const aujourdhui = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10)

const reglages = ref<TarifsReglages | null>(null)
const reponse = ref<PrixResponse | null>(null)
const error = ref('')
const actionError = ref('')
const notice = ref('')
const busy = ref(false)

const search = ref(typeof route.query.q === 'string' ? route.query.q : '')
const vue = ref<PrixVue>('tous')
const date = ref(aujourdhui)
const page = ref(0)

const tarif = computed(() => reglages.value?.tarifs.find((row) => row.name === props.liste) ?? null)
const achat = computed(() => tarif.value?.sens === 'achat')
const groupes = computed(() => {
	const tarifs = reglages.value?.tarifs ?? []
	return [
		{ key: 'vente', label: 'Vente', tarifs: tarifs.filter((row) => row.actif && row.sens === 'vente') },
		{ key: 'achat', label: 'Achat', tarifs: tarifs.filter((row) => row.actif && row.sens === 'achat') },
		{ key: 'off', label: 'Désactivés', tarifs: tarifs.filter((row) => !row.actif) },
	].filter((groupe) => groupe.tarifs.length)
})
const vues = computed(() => PRIX_VUES.filter((item) => !item.achat || achat.value))
const autreDate = computed(() => date.value !== aujourdhui)
const canEdit = computed(() => Boolean(reglages.value?.can_edit_prix && tarif.value?.actif))
const canEditCase = computed(() => canEdit.value && !autreDate.value)

function couverture(row: Tarif) {
	return row.total ? Math.round((row.prix * 100) / row.total) : 0
}
const SENS_MOT: Record<TarifSens, string> = { vente: 'de vente', achat: "d'achat" }

/** Sans tarif dans l'adresse (ou un tarif disparu) : le tarif de vente par défaut, sinon le premier. */
function openDefault(fresh: TarifsReglages) {
	if (fresh.tarifs.some((row) => row.name === props.liste)) return false
	const target = fresh.defauts.vente ?? fresh.tarifs.find((row) => row.actif)?.name ?? fresh.tarifs[0]?.name
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

const params = () => ({ search: search.value.trim(), vue: vue.value, start: page.value * 50, date: date.value })
let requestId = 0
async function loadPrix() {
	if (!props.liste) return
	const id = ++requestId
	try {
		const fresh = await getPrix(props.liste, params())
		if (id !== requestId) return
		reponse.value = fresh
		// Une case en cours de saisie garde ce qui est tapé ; les autres reprennent le prix enregistré.
		for (const ligne of fresh.lignes) if (!rowErrors[ligne.article]) resetDraft(ligne)
		error.value = ''
		for (const article of Object.keys(details)) if (ouverts[article]) loadDetail(article)
	} catch (e) {
		if (id === requestId) error.value = (e as Error).message
	}
}

function resetListe() {
	page.value = 0
	loadPrix()
}
watch(
	() => props.liste,
	() => {
		reponse.value = null
		vue.value = 'tous'
		for (const key of Object.keys(ouverts)) delete ouverts[key]
		for (const key of Object.keys(details)) delete details[key]
		resetListe()
	},
)
let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(search, () => {
	if (searchTimer) clearTimeout(searchTimer)
	searchTimer = setTimeout(resetListe, 250)
})
watch([vue, date], resetListe)
watch(page, loadPrix)

async function save(ligne: PrixLigne) {
	const liste = props.liste
	const text = drafts[ligne.article] ?? ''
	if (!liste || !canEditCase.value || saving[ligne.article] || !prixChange(text, ligne.prix)) return
	const parsed = parsePrix(text)
	if ('error' in parsed) {
		rowErrors[ligne.article] = parsed.error
		return
	}
	if (
		parsed.value === null &&
		!(await confirmAction({
			title: 'Retirer le prix',
			message: `Le prix en vigueur de ${ligne.designation} sera supprimé du tarif « ${liste} ». Les nouvelles pièces demanderont de le saisir.`,
			confirmLabel: 'Retirer le prix',
			danger: true,
		}))
	) {
		resetDraft(ligne)
		return
	}
	saving[ligne.article] = true
	delete rowErrors[ligne.article]
	try {
		replaceLigne(await setPrix(liste, ligne, text))
		notice.value = parsed.value === null ? 'Prix retiré.' : 'Prix enregistré.'
		refreshCounts()
	} catch (e) {
		rowErrors[ligne.article] = (e as Error).message
	} finally {
		saving[ligne.article] = false
	}
}
function replaceLigne(fresh: PrixLigne) {
	const rows = reponse.value?.lignes ?? []
	const index = rows.findIndex((row) => row.article === fresh.article)
	if (index >= 0) rows[index] = fresh
	resetDraft(fresh)
	highlighted.value = fresh.article
	if (highlightTimer) clearTimeout(highlightTimer)
	highlightTimer = setTimeout(() => (highlighted.value = null), 1500)
	if (ouverts[fresh.article]) loadDetail(fresh.article)
}
function onKey(event: KeyboardEvent, ligne: PrixLigne) {
	if (event.key === 'Enter') (event.target as HTMLInputElement).blur()
	if (event.key === 'Escape') {
		resetDraft(ligne)
		;(event.target as HTMLInputElement).blur()
	}
}
// Compteurs des vues et couverture des tarifs, sans recharger les lignes affichées.
async function refreshCounts() {
	try {
		reglages.value = await getTarifs()
		if (props.liste && reponse.value) {
			const fresh = await getPrix(props.liste, params())
			reponse.value.compte = fresh.compte
			reponse.value.reprenables = fresh.reprenables
		}
	} catch {
		// Les compteurs se remettront à jour au prochain chargement.
	}
}

// Tous les prix d'un article, sous sa ligne.
const ouverts = reactive<Record<string, boolean>>({})
const details = reactive<Record<string, LignesArticle>>({})
const detailErrors = reactive<Record<string, string>>({})
async function loadDetail(article: string) {
	if (!props.liste) return
	try {
		details[article] = await getLignes(props.liste, article, date.value)
		delete detailErrors[article]
	} catch (e) {
		detailErrors[article] = (e as Error).message
	}
}
function toggle(ligne: PrixLigne) {
	ouverts[ligne.article] = !ouverts[ligne.article]
	if (ouverts[ligne.article]) loadDetail(ligne.article)
}
function statutBadge(row: LignePrix) {
	if (row.statut === 'vigueur') return { label: STATUT_LABELS.vigueur, tone: 'tone-green' }
	if (row.statut === 'a_venir') return { label: STATUT_LABELS.a_venir, tone: 'tone-blue' }
	if (row.statut === 'tiers') return { label: achat.value ? 'Fournisseur' : 'Client', tone: 'tone-violet' }
	if (row.statut === 'lot') return { label: STATUT_LABELS.lot, tone: 'tone-gray' }
	return { label: STATUT_LABELS[row.statut], tone: 'tone-gray' }
}

// Fenêtre d'un prix : nouveau (général ou d'un tiers) ou modifié.
const dialogue = ref<{ detail: LignesArticle; ligne: LignePrix | null; pourTiers: boolean } | null>(null)
function ouvrirPrix(article: string, ligne: LignePrix | null = null, pourTiers = false) {
	const detail = details[article]
	if (detail) dialogue.value = { detail, ligne, pourTiers }
}
function onSaved(detail: LignesArticle) {
	details[detail.article] = detail
	dialogue.value = null
	notice.value = 'Prix enregistré.'
	loadPrix()
	refreshCounts()
}
async function supprimer(article: string, row: LignePrix) {
	if (!props.liste) return
	const ok = await confirmAction({
		title: 'Supprimer ce prix',
		message: `${formatPrix(row.prix)} ${details[article]?.devise ?? ''} (${formatPeriode(row.debut, row.fin)}) sera supprimé du tarif. Les pièces déjà créées gardent leurs prix.`,
		confirmLabel: 'Supprimer le prix',
		danger: true,
	})
	if (!ok) return
	try {
		details[article] = await deleteLigne(props.liste, row)
		notice.value = 'Prix supprimé.'
		loadPrix()
		refreshCounts()
	} catch (e) {
		detailErrors[article] = (e as Error).message
	}
}

// Tarif d'achat : le dernier prix payé devient le prix du tarif, dès aujourd'hui.
async function reprendre(articles?: string[]) {
	if (!props.liste || busy.value) return
	const n = articles?.length ?? reponse.value?.reprenables ?? 0
	if (!articles && !(await confirmAction({ title: 'Reprendre les derniers prix payés', message: `${n} article${n > 1 ? 's' : ''} sans prix recevront leur dernier prix payé, valable dès aujourd'hui.`, confirmLabel: 'Reprendre les prix' }))) return
	busy.value = true
	actionError.value = ''
	try {
		const { crees } = await reprendreDerniersPrix(props.liste, articles)
		notice.value = crees ? `${crees} prix repris.` : 'Aucun prix à reprendre.'
		await loadPrix()
		refreshCounts()
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}

async function makeDefault() {
	const current = tarif.value
	if (!current || busy.value) return
	const label = current.sens === 'vente' ? 'les ventes' : 'les achats'
	if (!(await confirmAction({ title: 'Tarif par défaut', message: `Les nouveaux ${current.sens === 'vente' ? 'devis et commandes clients' : "devis fournisseur et commandes d'achat"} reprendront les prix du tarif « ${current.name} ». Les pièces déjà créées ne changent pas.`, confirmLabel: `Utiliser pour ${label}` }))) return
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

async function toggleActif() {
	const current = tarif.value
	if (!current || busy.value || current.defaut) return
	const actif = !current.actif
	if (!actif && !(await confirmAction({ title: 'Désactiver le tarif', message: `« ${current.name} » ne pourra plus être choisi sur une pièce et ses prix ne seront plus proposés. Les pièces déjà créées gardent leurs prix.`, confirmLabel: 'Désactiver' }))) return
	busy.value = true
	actionError.value = ''
	try {
		reglages.value = await setTarifActif(current.name, actif)
		notice.value = actif ? `« ${current.name} » est de nouveau actif.` : `« ${current.name} » est désactivé.`
		await loadPrix()
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}

async function supprimerTarif() {
	const current = tarif.value
	if (!current || busy.value || current.defaut) return
	const derives = reglages.value?.tarifs.filter((row) => row.base === current.name).map((row) => `« ${row.name} »`) ?? []
	const message = [
		`« ${current.name} » et tous ses prix (${current.prix} article${current.prix > 1 ? 's' : ''} chiffré${current.prix > 1 ? 's' : ''}, avec les prix à venir, passés et par ${current.sens === 'vente' ? 'client' : 'fournisseur'}) seront supprimés. Cette action est définitive.`,
		derives.length ? `${derives.join(', ')} ${derives.length > 1 ? 'gardent leurs prix mais ne suivront' : 'garde ses prix mais ne suivra'} plus ce tarif.` : '',
		'Les pièces déjà créées gardent leurs prix. Pour seulement arrêter de le proposer, désactivez-le.',
	].filter(Boolean).join(' ')
	if (!(await confirmAction({ title: 'Supprimer le tarif', message, confirmLabel: 'Supprimer le tarif et ses prix', danger: true }))) return
	busy.value = true
	actionError.value = ''
	try {
		const fresh = await deleteTarif(current.name)
		reglages.value = fresh
		notice.value = `Tarif « ${current.name} » supprimé avec ${fresh.supprimes} prix.`
		openDefault(fresh)
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}

// Nouveau tarif, vide ou calculé depuis un autre (`base`).
const creating = ref<{ base: string | null } | null>(null)
function startCreate(base: string | null = null) {
	creating.value = { base }
}
function onCreated(nom: string, fresh: TarifsReglages & { crees: number }) {
	reglages.value = fresh
	creating.value = null
	notice.value = fresh.crees ? `Tarif « ${nom} » créé avec ${fresh.crees} prix.` : `Tarif « ${nom} » créé.`
	router.push({ name: 'Tarif', params: { liste: nom } })
}
function onCalculChanged(message: string) {
	notice.value = message
	loadPrix()
	refreshCounts()
}
function onDetached(fresh: TarifsReglages) {
	reglages.value = fresh
	notice.value = 'Le tarif ne suit plus son tarif de base.'
	loadPrix()
}

const reload = throttledReload(loadPrix, { delayMs: 1000, minIntervalMs: 4000 })
onMounted(() => {
	loadTarifs()
	connectRealtime<RealtimeEvent>(
		'unicare_bureau_update',
		(event) => {
			if (isForeignChange(event, window.user) && (event.doctype === 'Item Price' || event.doctype === 'Price List')) reload()
		},
		loadTarifs,
	)
})
onBeforeUnmount(closeRealtime)
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Tarifs et prix' }]" active="tarifs">
		<div class="bureau-work tdb">
			<div class="flex flex-wrap items-end gap-3">
				<div class="min-w-0 flex-auto">
					<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Tarifs et prix</h1>
					<p class="text-sm text-ink-gray-6">Un article peut avoir plusieurs prix dans un même tarif : une période de validité, une unité, un client ou un fournisseur. Les pièces reprennent le prix en vigueur à leur date.</p>
				</div>
				<button v-if="reglages?.can_create_tarif" type="button" class="btn-primary" :disabled="busy" @click="startCreate()"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Nouveau tarif</button>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!reglages" class="card p-4 text-ink-gray-6">Chargement des tarifs…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<div v-if="reglages" class="tarifs-layout">
				<nav class="card tarifs-liste" aria-labelledby="t-tarifs">
					<h2 id="t-tarifs" class="px-2.5 pt-1 text-base font-semibold">Tarifs</h2>
					<p v-if="!reglages.tarifs.length" class="px-2.5 text-ink-gray-6">Aucun tarif : créez-en un pour donner des prix aux articles.</p>
					<div v-for="groupe in groupes" :key="groupe.key" class="tarifs-groupe">
						<span class="px-2.5 text-xs font-semibold uppercase tracking-wide text-ink-gray-6">{{ groupe.label }}</span>
						<RouterLink v-for="row in groupe.tarifs" :key="row.name" :to="{ name: 'Tarif', params: { liste: row.name } }" class="tarif-item" :class="!row.actif && 'tarif-item-off'" :aria-current="row.name === liste ? 'page' : undefined">
							<span class="flex items-center gap-1.5">
								<span class="min-w-0 flex-auto truncate font-medium">{{ row.name }}</span>
								<span v-if="row.defaut" class="badge tone-green">Par défaut</span>
								<span v-if="groupe.key === 'off'" class="badge tone-gray">{{ row.sens === 'vente' ? 'Vente' : 'Achat' }}</span>
							</span>
							<span class="flex items-center gap-2">
								<span class="tarif-bar" aria-hidden="true"><span :class="!row.actif ? 'is-off' : couverture(row) < 50 ? 'is-low' : ''" :style="{ width: `${couverture(row)}%` }"></span></span>
								<span class="text-xs tabular-nums text-ink-gray-6">{{ row.prix }} / {{ row.total }}</span>
							</span>
						</RouterLink>
					</div>
				</nav>

				<section v-if="tarif" class="card tarifs-detail" aria-labelledby="t-prix">
					<div class="tarifs-head">
						<div class="flex flex-wrap items-start gap-3">
							<div class="min-w-0 flex-auto">
								<h2 id="t-prix" class="text-lg font-semibold">{{ tarif.name }}</h2>
								<div class="mt-1 flex flex-wrap items-center gap-1.5">
									<span class="badge tone-gray">Tarif {{ SENS_MOT[tarif.sens] }}</span>
									<span class="badge tone-gray">{{ tarif.devise }} · hors taxes</span>
									<span v-if="tarif.defaut" class="badge tone-green">Repris par les nouvelles pièces {{ SENS_MOT[tarif.sens] }}</span>
								</div>
							</div>
							<div class="flex flex-wrap items-center gap-2">
								<label v-if="reglages.can_toggle_tarif" class="flex items-center gap-2 text-sm font-medium" :title="tarif.defaut ? 'Le tarif par défaut reste actif' : undefined">
									<input type="checkbox" role="switch" class="table-panel-switch" :checked="tarif.actif" :disabled="busy || tarif.defaut" @change="toggleActif" />
									{{ tarif.actif ? 'Actif' : 'Désactivé' }}
								</label>
								<button v-if="!tarif.defaut && tarif.actif && reglages.can_set_defaut[tarif.sens]" type="button" class="btn-secondary" :disabled="busy" @click="makeDefault">Utiliser par défaut pour {{ tarif.sens === 'vente' ? 'les ventes' : 'les achats' }}</button>
								<button v-if="reglages.can_create_tarif" type="button" class="btn-secondary" :disabled="busy" @click="startCreate(tarif.name)">Créer un tarif à partir de celui-ci</button>
								<button v-if="reglages.can_delete_tarif" type="button" class="btn-danger" :disabled="busy || tarif.defaut" :title="tarif.defaut ? 'Le tarif par défaut ne se supprime pas' : undefined" @click="supprimerTarif">Supprimer</button>
							</div>
						</div>
						<p v-if="tarif.defaut && reglages.can_toggle_tarif" class="text-xs text-ink-gray-6">Le tarif par défaut reste actif : pour le désactiver, choisissez d'abord un autre tarif par défaut.</p>
						<TarifCalcule
							v-if="reponse?.tarif.regle && reponse.tarif.name === tarif.name"
							:liste="tarif.name"
							:regle="reponse.tarif.regle"
							:sens="tarif.sens"
							:devise="tarif.devise"
							:can-edit="canEdit"
							@changed="onCalculChanged"
							@detached="onDetached"
						/>
						<div v-if="!tarif.actif" role="status" class="tarifs-bandeau tone-gray">
							<span class="flex-auto">Ce tarif est désactivé : on ne peut plus le choisir sur une pièce, et ses prix ne sont plus proposés. Les pièces déjà créées gardent leurs prix. Ses prix restent consultables.</span>
							<button v-if="reglages.can_toggle_tarif" type="button" class="btn-secondary" :disabled="busy" @click="toggleActif">Réactiver le tarif</button>
						</div>

						<div class="tarifs-couverture">
							<div class="min-w-0 flex-[1_1_18rem]">
								<div class="flex flex-wrap items-baseline gap-2">
									<span class="text-xl font-semibold tabular-nums">{{ couverture(tarif) }} %</span>
									<span class="text-ink-gray-7">des articles {{ tarif.sens === 'vente' ? 'vendus' : 'achetés' }} ont un prix en vigueur aujourd'hui — {{ tarif.prix }} sur {{ tarif.total }}</span>
								</div>
								<span class="tarif-bar tarif-bar-lg" aria-hidden="true"><span :class="!tarif.actif && 'is-off'" :style="{ width: `${couverture(tarif)}%` }"></span></span>
							</div>
							<div v-if="reponse" class="flex flex-wrap gap-2">
								<button v-if="reponse.compte.sans_prix" type="button" class="btn-secondary tarifs-raccourci tone-amber" @click="vue = 'sans_prix'">{{ reponse.compte.sans_prix }} sans prix</button>
								<button v-if="reponse.compte.expire" type="button" class="btn-secondary tarifs-raccourci tone-orange" @click="vue = 'expire'">{{ reponse.compte.expire }} expire{{ reponse.compte.expire > 1 ? 'nt' : '' }} sous 45 jours</button>
								<button v-if="reponse.compte.a_venir" type="button" class="btn-secondary tarifs-raccourci tone-blue" @click="vue = 'a_venir'">{{ reponse.compte.a_venir }} changement{{ reponse.compte.a_venir > 1 ? 's' : '' }} à venir</button>
								<button v-if="achat && reponse.compte.ecart" type="button" class="btn-secondary tarifs-raccourci" @click="vue = 'ecart'">{{ reponse.compte.ecart }} écart{{ reponse.compte.ecart > 1 ? 's' : '' }} &gt; 5 %</button>
							</div>
						</div>

						<div v-if="achat && canEdit && reponse?.reprenables" class="tarifs-bandeau tone-blue">
							<span class="flex-auto">{{ reponse.reprenables }} article{{ reponse.reprenables > 1 ? 's' : '' }} sans prix en vigueur {{ reponse.reprenables > 1 ? 'ont' : 'a' }} déjà été acheté{{ reponse.reprenables > 1 ? 's' : '' }}. Sans prix ici, les pièces d'achat reprennent le dernier prix payé : vous pouvez le figer dans le tarif, dès aujourd'hui.</span>
							<button type="button" class="btn-secondary" :disabled="busy" @click="reprendre()">Reprendre les {{ reponse.reprenables }} derniers prix payés</button>
						</div>
					</div>

					<div class="tarifs-outils">
						<label class="bureau-search">
							<LucideSearch class="h-3.5 w-3.5" aria-hidden="true" />
							<input id="tarifs-recherche" v-model="search" class="field-input" type="search" aria-label="Chercher un article" placeholder="Article ou code" />
						</label>
						<div class="seg flex-wrap" role="group" aria-label="Afficher">
							<button v-for="item in vues" :key="item.key" type="button" :aria-pressed="vue === item.key" @click="vue = item.key">
								{{ item.label }}<span v-if="reponse" class="ml-1 tabular-nums text-ink-gray-6">{{ reponse.compte[item.key] ?? 0 }}</span>
							</button>
						</div>
						<span class="flex-auto"></span>
						<label class="flex items-center gap-1.5 text-sm text-ink-gray-7">
							Prix au
							<input v-model="date" type="date" class="field-input w-auto" aria-label="Date des prix affichés" @change="date = date || aujourdhui" />
						</label>
					</div>
					<p class="field-note px-4">
						<template v-if="autreDate">Prix en vigueur le {{ formatDate(date) }}. Revenez à aujourd'hui pour modifier un prix dans sa case ; la flèche d'un article reste disponible.</template>
						<template v-else-if="!reglages.can_edit_prix">Lecture seule : votre rôle ne modifie pas les prix.</template>
						<template v-else-if="tarif.actif">Entrée enregistre le prix en vigueur · Échap annule · case vide = sans prix. La flèche d'un article gère ses prix à venir, par {{ achat ? 'fournisseur' : 'client' }} et passés.</template>
					</p>

					<p v-if="!reponse" class="px-4 pb-4 text-ink-gray-6">Chargement des prix…</p>
					<div v-else-if="reponse.lignes.length" class="overflow-x-auto">
						<table class="ref-table tarifs-table">
							<thead>
								<tr>
									<th class="tarifs-chev"><span class="sr-only">Tous les prix</span></th>
									<th>Article</th>
									<th>Unité</th>
									<th class="end">Prix en vigueur HT ({{ tarif.devise }})</th>
									<th>Validité</th>
									<th v-if="achat" class="end">Dernier prix payé</th>
									<th v-if="achat" class="end">Écart</th>
									<th>Autres prix</th>
								</tr>
							</thead>
							<tbody>
								<template v-for="ligne in reponse.lignes" :key="ligne.article">
									<tr :class="[highlighted === ligne.article && 'devis-line-new', ouverts[ligne.article] && 'tarifs-ouvert', ligne.prix === null && 'tarifs-sans-prix']">
										<td class="tarifs-chev">
											<button v-if="ligne.nb_lignes || canEdit" type="button" class="app-icon-bare" :aria-expanded="Boolean(ouverts[ligne.article])" :aria-label="`Tous les prix de ${ligne.designation}`" @click="toggle(ligne)">
												<LucideChevronRight class="h-3.5 w-3.5 transition-transform" :class="ouverts[ligne.article] && 'rotate-90'" aria-hidden="true" />
											</button>
										</td>
										<td>
											<RouterLink :to="{ name: 'Article', params: { id: ligne.article } }" class="font-medium">{{ ligne.designation }}</RouterLink>
											<small class="block text-ink-gray-6">{{ ligne.article }}</small>
										</td>
										<td>
											{{ ligne.unite }}
											<small v-if="ligne.unite_prix && ligne.unite_prix !== ligne.unite" class="block text-tone-amber">prix par {{ ligne.unite_prix }}</small>
										</td>
										<td class="end">
											<div class="flex items-center justify-end gap-2">
												<button v-if="achat && canEditCase && ligne.prix === null && ligne.dernier_achat" type="button" class="btn-secondary btn-sm" :disabled="busy" :aria-label="`Reprendre le dernier prix payé, ${ligne.designation}`" @click="reprendre([ligne.article])">Reprendre</button>
												<input
													v-if="canEditCase"
													v-model="drafts[ligne.article]"
													class="field-input tarifs-prix end tabular-nums"
													:class="ligne.prix === null && 'tarifs-prix-vide'"
													inputmode="decimal"
													:placeholder="achat && ligne.dernier_achat ? formatPrix(ligne.dernier_achat) : 'Sans prix'"
													:aria-label="`Prix en vigueur, ${ligne.designation}`"
													:aria-invalid="Boolean(rowErrors[ligne.article])"
													:disabled="saving[ligne.article]"
													@blur="save(ligne)"
													@keydown="onKey($event, ligne)"
												/>
												<span v-else class="tabular-nums" :class="ligne.prix === null && 'text-ink-gray-6'">{{ ligne.prix === null ? 'Sans prix' : formatPrix(ligne.prix) }}</span>
											</div>
											<p v-if="rowErrors[ligne.article]" class="field-error text-left" role="alert">{{ rowErrors[ligne.article] }}</p>
										</td>
										<td>
											<span :class="ligne.prix === null ? 'font-medium text-tone-amber' : 'text-ink-gray-8'">{{ validite(ligne) }}</span>
											<small v-if="ligne.expire_bientot && ligne.fin" class="block font-medium tarifs-expire-note">expire dans {{ joursAvant(ligne.fin, reponse.date) }} jour{{ joursAvant(ligne.fin, reponse.date) > 1 ? 's' : '' }}</small>
											<small v-else-if="ligne.dernier_expire" class="block text-ink-gray-6">dernier prix {{ formatPrix(ligne.dernier_expire.prix) }}, expiré le {{ formatDate(ligne.dernier_expire.fin, true) }}</small>
										</td>
										<td v-if="achat" class="end tabular-nums text-ink-gray-7">{{ formatPrix(ligne.dernier_achat) || '—' }}</td>
										<td v-if="achat" class="end">
											<span v-if="ligne.ecart" class="badge tabular-nums" :class="Math.abs(ligne.ecart) > 0.05 ? 'tone-orange' : 'tone-gray'">{{ formatEcart(ligne.ecart) }}</span>
											<span v-else class="text-ink-gray-6">{{ formatEcart(ligne.ecart) }}</span>
										</td>
										<td>
											<div class="flex flex-wrap gap-1">
												<span v-if="ligne.a_venir" class="badge tone-blue">{{ ligne.prix !== null ? `${formatPrix(ligne.prix)} → ` : '' }}{{ formatPrix(ligne.a_venir.prix) }} au {{ formatDate(ligne.a_venir.debut, true) }}</span>
												<span v-if="ligne.nb_tiers" class="badge tone-violet">{{ ligne.nb_tiers }} prix {{ achat ? 'fournisseur' : 'client' }}{{ ligne.nb_tiers > 1 ? 's' : '' }}</span>
												<span v-if="ligne.nb_anciens" class="badge tone-gray">{{ ligne.nb_anciens }} ancien{{ ligne.nb_anciens > 1 ? 's' : '' }}</span>
											</div>
										</td>
									</tr>
									<tr v-if="ouverts[ligne.article]" class="tarifs-ouvert">
										<td :colspan="achat ? 8 : 6" class="tarifs-sous-cell">
											<div class="tarifs-sous">
												<div class="flex flex-wrap items-center gap-2 border-b border-[var(--line-soft)] px-3 py-2">
													<span class="flex-auto text-sm font-semibold text-ink-gray-8">Prix de cet article dans « {{ tarif.name }} »</span>
													<template v-if="canEdit && details[ligne.article]">
														<button type="button" class="btn-secondary btn-sm" @click="ouvrirPrix(ligne.article)"><LucidePlus class="h-3 w-3" aria-hidden="true" />Nouveau prix à partir d'une date</button>
														<button type="button" class="btn-secondary btn-sm" @click="ouvrirPrix(ligne.article, null, true)">Prix pour un {{ achat ? 'fournisseur' : 'client' }}</button>
													</template>
												</div>
												<p v-if="detailErrors[ligne.article]" role="alert" class="px-3 py-2 text-sm text-tone-red">{{ detailErrors[ligne.article] }}</p>
												<p v-else-if="!details[ligne.article]" class="px-3 py-2 text-sm text-ink-gray-6">Chargement…</p>
												<p v-else-if="!details[ligne.article].lignes.length" class="px-3 py-2 text-sm text-ink-gray-6">Aucun prix dans ce tarif.</p>
												<div v-else class="overflow-x-auto">
													<table class="ref-table tarifs-sous-table">
														<thead>
															<tr>
																<th>Statut</th>
																<th>Période</th>
																<th class="end">Prix HT</th>
																<th>Unité</th>
																<th>{{ achat ? 'Fournisseur' : 'Client' }}</th>
																<th v-if="achat" class="end">Délai</th>
																<th>Note</th>
																<th v-if="canEdit"><span class="sr-only">Actions</span></th>
															</tr>
														</thead>
														<tbody>
															<tr v-for="row in details[ligne.article].lignes" :key="row.ligne" :class="row.statut === 'expire' && 'text-ink-gray-6'">
																<td><span class="badge" :class="statutBadge(row).tone">{{ statutBadge(row).label }}</span></td>
																<td class="whitespace-nowrap">{{ formatPeriode(row.debut, row.fin) }}</td>
																<td class="end font-medium tabular-nums">{{ formatPrix(row.prix) }}</td>
																<td>{{ row.unite }}<small v-if="row.lot" class="block text-ink-gray-6">lot {{ row.lot }}</small></td>
																<td>{{ row.tiers || 'Tous' }}</td>
																<td v-if="achat" class="end whitespace-nowrap">{{ row.delai ? `${row.delai} j` : '—' }}</td>
																<td class="text-ink-gray-6">{{ row.note || '—' }}</td>
																<td v-if="canEdit" class="end whitespace-nowrap">
																	<button type="button" class="app-icon-bare" :aria-label="`Modifier le prix ${formatPeriode(row.debut, row.fin)}`" @click="ouvrirPrix(ligne.article, row)"><LucidePencil class="h-3.5 w-3.5" aria-hidden="true" /></button>
																	<button type="button" class="app-icon-bare text-tone-red" :aria-label="`Supprimer le prix ${formatPeriode(row.debut, row.fin)}`" @click="supprimer(ligne.article, row)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button>
																</td>
															</tr>
														</tbody>
													</table>
												</div>
											</div>
										</td>
									</tr>
								</template>
							</tbody>
						</table>
					</div>
					<p v-else class="px-4 pb-4 text-ink-gray-6">{{ vue === 'sans_prix' ? 'Tous les articles ont un prix en vigueur dans ce tarif.' : 'Aucun article ne correspond.' }}</p>
					<div class="px-4 pb-3">
						<ListPager v-if="reponse && reponse.total > reponse.page" :total="reponse.total" :page="page" :page-size="reponse.page" :sizes="[reponse.page]" sort-label="Par désignation" @update:page="(value) => (page = value)" />
					</div>
				</section>
			</div>
		</div>

		<PrixLigneDialog v-if="dialogue && liste" :liste="liste" :detail="dialogue.detail" :ligne="dialogue.ligne" :pour-tiers="dialogue.pourTiers" :aujourdhui="aujourdhui" @close="dialogue = null" @saved="onSaved" />

		<NouveauTarifDialog v-if="creating && reglages" :tarifs="reglages.tarifs" :sens="tarif?.sens ?? 'vente'" :base="creating.base" :aujourdhui="aujourdhui" @close="creating = null" @created="onCreated" />
		<AppToast :message="notice" tone="success" @close="notice = ''" />
	</BureauShell>
</template>
