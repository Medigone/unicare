<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideCircleAlert from '~icons/lucide/circle-alert'
import LucideLayers from '~icons/lucide/layers'
import LucidePlus from '~icons/lucide/plus'
import LucidePrinter from '~icons/lucide/printer'
import LucideTrash2 from '~icons/lucide/trash-2'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FormDialog from '@shared/components/FormDialog.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import ChoicePicker from './ChoicePicker.vue'
import OrdreClotureDialog from './OrdreClotureDialog.vue'
import OrdreSteps from './OrdreSteps.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import {
	addComplement,
	addRebut,
	deleteOrdre,
	dupliquerOrdre,
	genererLot,
	getLotsArticle,
	getOrdreOptions,
	ordreActivity,
	ordrePrintUrl,
	removeRebut,
	runOrdreStep,
	saisirOrdre,
	searchStockArticles,
	setControle,
	updateOrdre,
} from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { confirmAction } from '@/lib/confirm'
import { deskUrl } from '@/lib/display'
import type { LotChoice } from '@/lib/livraisons'
import type { StockArticleChoice } from '@/lib/mouvements'
import { dureeText, echeanceText, ETAPE_TONES, parseQty, type OrdreDetail, type OrdreMatiere, type OrdreOptions, type OrdreValues } from '@/lib/ordres'
import { useOrdre } from '@/lib/useOrdre'

/**
 * Fiche d'un ordre, guidée : le bandeau des étapes, un seul bouton principal qui dit ce qu'il fait, et à l'étape
 * « À planifier » la liste de ce qui manque. Les champs se règlent sur place et s'enregistrent aussitôt.
 */
const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: []; deleted: [] }>()

const { ordre, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useOrdre(
	() => props.id,
	() => emit('changed'),
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => ordreActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, ordre })

const options = ref<OrdreOptions | null>(null)
onMounted(async () => {
	try {
		options.value = await getOrdreOptions()
	} catch {
		// Sans les choix, la planification reste lisible ; le serveur refusera ce qui ne va pas.
	}
})

const can = (action: string) => Boolean(ordre.value?.actions.includes(action as never))
const state = computed(() => ordre.value?.state)
const planning = computed(() => can('modifier'))
const recettes = computed(() => (options.value?.recettes ?? []).filter((item) => item.produit === ordre.value?.produit))
const unite = computed(() => ordre.value?.unite ?? '')

/** Une écriture, avec son message de réussite. */
async function save(action: (current: OrdreDetail) => Promise<OrdreDetail>, message = '') {
	const current = ordre.value
	if (!current) return false
	const done = await perform(() => action(current))
	if (done && message) notice.value = message
	return done
}

// À planifier : recette, quantité, date et checklist s'enregistrent dès qu'on quitte le champ.
const plan = ref({ recette: '', quantite: '', date_prevue: '', checklist: '' })
watch(
	() => ordre.value?.modified,
	() => {
		const current = ordre.value
		if (!current) return
		plan.value = { recette: current.recette ?? '', quantite: String(current.qty_prevue).replace('.', ','), date_prevue: current.date_prevue ?? '', checklist: current.modele_checklist ?? '' }
		utilises.value = Object.fromEntries(current.matieres.map((line) => [line.name, String(line.utilise).replace('.', ',')]))
	},
	{ immediate: true },
)
async function savePlan(field: keyof typeof plan.value) {
	const current = ordre.value
	if (!current) return
	const values: OrdreValues = {}
	if (field === 'quantite') {
		const quantite = parseQty(plan.value.quantite)
		if (!(quantite > 0)) {
			actionError.value = 'Indiquez une quantité supérieure à zéro.'
			return
		}
		if (quantite === current.qty_prevue) return
		values.quantite = quantite
	} else if (field === 'recette') {
		if (plan.value.recette === current.recette) return
		values.recette = plan.value.recette
	} else if (field === 'date_prevue') {
		if (!plan.value.date_prevue || plan.value.date_prevue === current.date_prevue) return
		values.date_prevue = plan.value.date_prevue
	} else {
		if (plan.value.checklist === current.modele_checklist) return
		values.checklist = plan.value.checklist
	}
	const recalcul = field === 'quantite' || field === 'recette'
	await save((fresh) => updateOrdre(fresh, values), recalcul ? 'Matières recalculées d\'après la recette.' : 'Enregistré.')
}
async function saveLine(line: OrdreMatiere, change: { quantite?: string; depot?: string; lot?: string }) {
	const ligne: NonNullable<OrdreValues['lignes']>[number] = { name: line.name }
	if (change.quantite !== undefined) {
		const quantite = parseQty(change.quantite)
		if (!(quantite > 0)) {
			actionError.value = `Indiquez une quantité de ${line.designation} supérieure à zéro.`
			return
		}
		if (quantite === line.prevu) return
		ligne.quantite = quantite
	}
	if (change.depot !== undefined) ligne.depot = change.depot
	if (change.lot !== undefined) ligne.lot = change.lot || null
	await save((fresh) => updateOrdre(fresh, { lignes: [ligne] }))
}
async function removeLine(line: OrdreMatiere) {
	if (!(await confirmAction({ title: 'Retirer la matière', message: `${line.designation} ne sera plus envoyée à l'atelier pour cet ordre.`, confirmLabel: 'Retirer', danger: true }))) return
	await save((fresh) => updateOrdre(fresh, { retirer: [line.name] }), 'Matière retirée.')
}
function lotLabel(lot: LotChoice) {
	const peremption = lot.peremption ? ` · périme ${new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${lot.peremption}T00:00:00`))}` : ''
	return `${lot.lot} · ${formatQty(lot.qty)}${peremption}`
}
function lineStatus(line: OrdreMatiere): { text: string; tone: string } {
	if (line.avec_lot && !line.lot) return { text: line.lots.length ? 'lot à choisir' : 'aucun lot en stock', tone: 'tone-amber' }
	if ((line.disponible ?? 0) + 0.0001 < line.prevu) return { text: `manque ${formatQty(line.prevu - (line.disponible ?? 0))}`, tone: 'tone-red' }
	return { text: 'OK', tone: 'tone-green' }
}

// Ajout d'une matière hors recette.
const adding = ref(false)
const ajout = ref({ article: '', label: '', quantite: '' })
const ajoutError = ref('')
const findArticles = async (query: string) => (await searchStockArticles(query)).map((item) => ({ ...item, hint: item.uom ?? '' }))
async function addLine() {
	const quantite = parseQty(ajout.value.quantite)
	ajoutError.value = !ajout.value.article ? 'Choisissez la matière.' : !(quantite > 0) ? 'Indiquez la quantité.' : ''
	if (ajoutError.value) return
	if (await save((fresh) => updateOrdre(fresh, { ajouts: [{ article: ajout.value.article, quantite }] }), 'Matière ajoutée.')) {
		adding.value = false
		ajout.value = { article: '', label: '', quantite: '' }
	}
}

// Checklist : un contrôle se coche d'un clic ; la remarque s'enregistre en quittant le champ.
const remarques = ref<Record<string, boolean>>({})
async function toggleControle(ligne: string, conforme: boolean) {
	await save((fresh) => setControle(fresh, ligne, { conforme }))
}
async function saveObservation(ligne: string, value: string) {
	const current = ordre.value?.checklist.find((row) => row.name === ligne)
	if (!current || (current.observation ?? '') === value.trim()) return
	await save((fresh) => setControle(fresh, ligne, { observation: value }), 'Remarque enregistrée.')
}

// En production : quantités réellement utilisées, enregistrées en quittant le champ.
const utilises = ref<Record<string, string>>({})
async function saveUtilise(line: OrdreMatiere) {
	const value = parseQty(utilises.value[line.name] ?? '')
	if (!(value >= 0)) {
		actionError.value = `Quantité utilisée de ${line.designation} illisible.`
		return
	}
	if (value === line.utilise) return
	await save((fresh) => saisirOrdre(fresh, [{ name: line.name, utilise: value }]))
}
function rebutOf(line: OrdreMatiere) {
	return (ordre.value?.rebuts ?? []).filter((row) => row.article === line.article && (row.lot ?? null) === (line.lot ?? null)).reduce((sum, row) => sum + row.quantite, 0)
}
function resteOf(line: OrdreMatiere) {
	const utilise = parseQty(utilises.value[line.name] ?? line.utilise)
	return Math.round((line.prevu + line.complement - (Number.isFinite(utilise) ? utilise : 0) - rebutOf(line)) * 1000) / 1000
}

// Rebuts et compléments : chacun dans sa petite fenêtre.
const articles = computed(() => {
	const seen = new Map<string, OrdreMatiere>()
	for (const line of ordre.value?.matieres ?? []) if (!seen.has(line.article)) seen.set(line.article, line)
	return [...seen.values()]
})
const rebut = ref<{ open: boolean; article: string; quantite: string; error: string }>({ open: false, article: '', quantite: '', error: '' })
async function submitRebut() {
	const quantite = parseQty(rebut.value.quantite)
	rebut.value.error = !rebut.value.article ? 'Choisissez la matière.' : !(quantite > 0) ? 'Indiquez la quantité.' : ''
	if (rebut.value.error) return
	const line = articles.value.find((item) => item.article === rebut.value.article)
	if (await save((fresh) => addRebut(fresh, { article: rebut.value.article, quantite, lot: line?.lot ?? undefined }), 'Rebut ajouté : il ira au dépôt des rebuts à la clôture.')) rebut.value = { open: false, article: '', quantite: '', error: '' }
}
async function deleteRebut(ligne: string, label: string) {
	if (!(await confirmAction({ title: 'Retirer le rebut', message: `Le rebut de ${label} sera retiré de l'ordre.`, confirmLabel: 'Retirer', danger: true }))) return
	await save((fresh) => removeRebut(fresh, ligne), 'Rebut retiré.')
}

const complement = ref<{ open: boolean; article: string; quantite: string; depot: string; lot: string; lots: LotChoice[]; error: string }>({ open: false, article: '', quantite: '', depot: '', lot: '', lots: [], error: '' })
const complementLine = computed(() => articles.value.find((item) => item.article === complement.value.article))
function openComplement() {
	const first = articles.value[0]
	complement.value = { open: true, article: first?.article ?? '', quantite: '', depot: first?.depot ?? '', lot: '', lots: [], error: '' }
}
watch([() => complement.value.article, () => complement.value.depot], async ([article, depot], [previous]) => {
	const line = complementLine.value
	if (article !== previous && line) complement.value.depot = line.depot ?? complement.value.depot
	complement.value.lots = []
	complement.value.lot = ''
	if (!line?.avec_lot || !complement.value.depot) return
	try {
		complement.value.lots = await getLotsArticle(line.article, complement.value.depot)
		complement.value.lot = complement.value.lots.find((lot) => lot.lot === line.lot)?.lot ?? complement.value.lots[0]?.lot ?? ''
	} catch (e) {
		complement.value.error = (e as Error).message
	}
})
async function submitComplement() {
	const quantite = parseQty(complement.value.quantite)
	const line = complementLine.value
	complement.value.error = !line ? 'Choisissez la matière.' : !(quantite > 0) ? 'Indiquez la quantité.' : !complement.value.depot ? 'Choisissez le dépôt de départ.' : line.avec_lot && !complement.value.lot ? 'Choisissez le lot.' : ''
	if (complement.value.error || !line) return
	const atelier = ordre.value?.depots.atelier ?? "l'atelier"
	if (!(await confirmAction({ title: 'Envoyer un complément', message: `${formatQty(quantite)} ${line.unite ?? ''} de ${line.designation}${complement.value.lot ? ` (lot ${complement.value.lot})` : ''} partent tout de suite de ${complement.value.depot} vers ${atelier}.`, confirmLabel: "Envoyer à l'atelier" }))) return
	if (await save((fresh) => addComplement(fresh, { article: line.article, quantite, depot: complement.value.depot, lot: complement.value.lot || undefined }), 'Complément envoyé à l\'atelier.')) complement.value.open = false
}

// Étapes : chacune demande confirmation en disant ce qui va bouger.
async function preparer() {
	const current = ordre.value
	if (!current) return
	const lignes = current.matieres.map((line) => `• ${formatQty(line.prevu)} ${line.unite ?? ''} ${line.designation}${line.lot ? ` (lot ${line.lot})` : ''} depuis ${line.depot ?? '—'}`).join('\n')
	if (!(await confirmAction({ title: 'Préparer l\'ordre', message: `Les matières partent maintenant vers ${current.depots.atelier ?? "l'atelier"} :\n${lignes}\nElles restent réservées à cet ordre jusqu'à la clôture.`, confirmLabel: "Envoyer les matières à l'atelier" }))) return
	await save((fresh) => runOrdreStep(fresh, 'preparer'), "Matières envoyées à l'atelier : l'ordre est prêt à démarrer.")
}
async function demarrer() {
	if (!(await confirmAction({ title: 'Démarrer la production', message: "L'heure de démarrage est notée pour calculer la durée de production. Vous saisirez ensuite les quantités utilisées et les rebuts.", confirmLabel: 'Démarrer la production' }))) return
	await save((fresh) => runOrdreStep(fresh, 'demarrer'), 'Production démarrée.')
}
const closing = ref(false)
async function annuler() {
	const current = ordre.value
	if (!current) return
	const retour = current.mouvements.length ? ' Les mouvements de stock déjà faits sont annulés : les matières reviennent à leur dépôt de départ.' : ''
	if (!(await confirmAction({ title: "Annuler l'ordre", message: `L'ordre ${current.name} sera annulé et ne pourra plus avancer.${retour}`, confirmLabel: "Annuler l'ordre", danger: true }))) return
	await save((fresh) => runOrdreStep(fresh, 'annuler'), 'Ordre annulé.')
}
async function generer() {
	const current = ordre.value
	if (!current) return
	if (current.lot_pf && !(await confirmAction({ title: 'Nouveau lot', message: `Le lot ${current.lot_pf} sera remplacé par un nouveau lot pour cet ordre.`, confirmLabel: 'Générer un nouveau lot' }))) return
	await save((fresh) => genererLot(fresh), 'Lot du produit fini créé.')
}

const router = useRouter()
async function dupliquer() {
	const current = ordre.value
	if (!current) return
	if (!(await confirmAction({ title: 'Refaire cet ordre', message: `Un nouvel ordre à planifier sera créé : ${formatQty(current.qty_prevue)} ${unite.value} de ${current.designation}, même recette et mêmes contrôles, pour aujourd'hui.`, confirmLabel: 'Créer le nouvel ordre' }))) return
	busy.value = true
	try {
		const created = await dupliquerOrdre(current)
		emit('changed')
		await router.push({ name: 'OrdreFiche', params: { id: created.name } })
		notice.value = `Ordre ${created.name} créé : il est à planifier.`
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
async function supprimer() {
	const current = ordre.value
	if (!current) return
	if (!(await confirmAction({ title: "Supprimer l'ordre", message: `L'ordre ${current.name}, encore à planifier, sera supprimé définitivement.`, confirmLabel: 'Supprimer', danger: true }))) return
	busy.value = true
	try {
		await deleteOrdre(current)
		emit('deleted')
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}
function onClosed(fresh: OrdreDetail) {
	ordre.value = fresh
	closing.value = false
	notice.value = 'Ordre clôturé : le stock est à jour.'
	emit('changed')
	feed.value?.refresh()
}
function focusTarget(cible: string | null) {
	if (!cible) return
	document.getElementById(`ordre-${cible}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
const percent = (value: number) => `${String(Math.round(value * 10) / 10).replace('.', ',')} %`
const controlesFaits = computed(() => ordre.value?.checklist.filter((row) => row.conforme).length ?? 0)
const horsTolerance = computed(() => (ordre.value ? Math.abs(ordre.value.rendement - ordre.value.rendement_vise) > ordre.value.tolerance : false))
</script>

<template>
	<main class="bureau-main">
		<div v-if="error" role="alert" class="card p-3.5 text-tone-red">
			{{ error }}
			<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
		</div>
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Cet ordre n'existe pas ou n'existe plus.</div>
		<div v-else-if="!ordre" class="card p-8 text-center text-ink-gray-6">Chargement de l'ordre…</div>

		<template v-else>
			<RecordHeader>
				<template #title>{{ ordre.designation }}</template>
				<template #flags><StatusPill :status="ordre.etape" :tone="ETAPE_TONES[ordre.state]" /></template>
				<template #sub>
					<span class="tabular-nums">{{ ordre.name }}</span>
					<span class="tabular-nums">{{ formatQty(ordre.qty_prevue) }} {{ unite }}</span>
					<span :class="ordre.retard && 'font-medium text-tone-red'">prévu {{ echeanceText(ordre.date_prevue, ordre.retard) }}</span>
					<div><TagEditor doctype="Ordre de Conditionnement" :name="ordre.name" :modified="ordre.modified" :tags="ordre.tags" :can-edit="true" @changed="(tags) => (ordre!.tags = tags)" /></div>
				</template>
				<template #actions>
					<button v-if="can('complement')" type="button" class="btn-secondary" :disabled="busy" @click="openComplement">Ajouter un complément</button>
					<button v-if="can('preparer')" type="button" class="btn-primary" :disabled="busy || ordre.manques.length > 0" :title="ordre.manques.length ? 'Réglez d\'abord ce qui manque' : undefined" @click="preparer">Préparer : envoyer les matières à l'atelier</button>
					<button v-if="can('demarrer')" type="button" class="btn-primary" :disabled="busy" @click="demarrer">Démarrer la production</button>
					<button v-if="can('cloturer') && state === 'En production'" type="button" class="btn-primary" :disabled="busy" @click="closing = true">Clôturer l'ordre…</button>
					<button v-if="state === 'Terminé' && can('dupliquer')" type="button" class="btn-secondary" :disabled="busy" @click="dupliquer">Refaire cet ordre</button>
					<MoreMenu>
						<a v-if="ordre.can_print" class="app-menu-item" role="menuitem" :href="ordrePrintUrl(ordre.name)" target="_blank" rel="noopener noreferrer"><LucidePrinter class="h-3.5 w-3.5" aria-hidden="true" />Imprimer la fiche</a>
						<button v-if="can('generer_lot')" type="button" class="app-menu-item" role="menuitem" @click="generer">{{ ordre.lot_pf ? 'Générer un nouveau lot' : 'Générer le lot du produit fini' }}</button>
						<button v-if="can('dupliquer') && state !== 'Terminé'" type="button" class="app-menu-item" role="menuitem" @click="dupliquer">Refaire cet ordre</button>
						<div class="app-menu-sep"></div>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Ordre de Conditionnement', ordre.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="can('annuler') || can('supprimer')">
							<div class="app-menu-sep"></div>
							<button v-if="can('annuler')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="annuler">Annuler l'ordre</button>
							<button v-if="can('supprimer')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="supprimer">Supprimer l'ordre</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<OrdreSteps :etapes="ordre.etapes" class="card" />
			<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<div class="bureau-detail">
				<div class="bureau-center">
					<!-- Terminé : le récapitulatif d'abord. -->
					<section v-if="state === 'Terminé'" class="card ordre-kpis" aria-label="Récapitulatif">
						<div><span>Prévu</span><strong>{{ formatQty(ordre.qty_prevue) }}</strong><small>{{ unite }}</small></div>
						<div><span>Produit</span><strong>{{ formatQty(ordre.qty_reelle) }}</strong><small>unités bonnes</small></div>
						<div><span>Rendement</span><strong :class="horsTolerance ? 'text-tone-red' : 'text-tone-green'">{{ percent(ordre.rendement) }}</strong><small>{{ horsTolerance ? 'hors tolérance' : 'dans la tolérance' }}</small></div>
						<div><span>Rebuts</span><strong>{{ formatQty(ordre.qty_rebut) }}</strong><small>au dépôt des rebuts</small></div>
						<div><span>Durée totale</span><strong>{{ dureeText(ordre.duree_totale) }}</strong><small>production {{ dureeText(ordre.etapes[2]?.duree) }}</small></div>
					</section>
					<div v-if="state === 'Annulé'" role="status" class="rounded-control tone-gray px-3.5 py-2.5">Ordre annulé : les mouvements de stock qu'il avait faits sont annulés, les matières sont revenues à leur dépôt.</div>

					<!-- À planifier -->
					<template v-if="state === 'Brouillon'">
						<section id="ordre-planning" class="card ordre-plan" aria-label="Planification">
							<div class="form-field ordre-plan-wide">
								<label class="field-label" for="plan-recette">Recette</label>
								<select id="plan-recette" v-model="plan.recette" class="field-input" :disabled="!planning || busy" @change="savePlan('recette')">
									<option v-if="!recettes.some((item) => item.value === plan.recette)" :value="plan.recette">{{ plan.recette }}</option>
									<option v-for="item in recettes" :key="item.value" :value="item.value">{{ item.label }}</option>
								</select>
							</div>
							<div class="form-field">
								<label class="field-label" for="plan-quantite">Quantité à produire</label>
								<span class="flex items-center gap-1.5"><input id="plan-quantite" v-model="plan.quantite" class="field-input text-right tabular-nums" inputmode="decimal" :disabled="!planning || busy" @change="savePlan('quantite')" /><span class="text-sm text-ink-gray-7">{{ unite }}</span></span>
							</div>
							<div class="form-field">
								<label class="field-label" for="plan-date">Prévu pour</label>
								<input id="plan-date" v-model="plan.date_prevue" type="date" class="field-input" :disabled="!planning || busy" @change="savePlan('date_prevue')" />
							</div>
							<div class="form-field">
								<label class="field-label" for="plan-checklist">Contrôles</label>
								<select id="plan-checklist" v-model="plan.checklist" class="field-input" :disabled="!planning || busy" @change="savePlan('checklist')">
									<option v-if="!(options?.checklists ?? []).includes(plan.checklist)" :value="plan.checklist">{{ plan.checklist }}</option>
									<option v-for="item in options?.checklists" :key="item" :value="item">{{ item }}</option>
								</select>
							</div>
						</section>

						<section id="ordre-matieres" class="card ref-card">
							<div class="ref-card-head">
								<h3>Matières à envoyer à l'atelier</h3>
								<span class="inline-flex items-center gap-2">
									<span class="text-xs text-ink-gray-6">pour {{ formatQty(ordre.qty_prevue) }} {{ unite }}</span>
									<button v-if="planning" type="button" class="btn-secondary" :disabled="busy" @click="adding = true"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Ajouter une matière</button>
								</span>
							</div>
							<div class="ref-scroll"><table class="ref-table livraison-prep">
								<thead><tr><th>Matière</th><th class="end">Quantité</th><th>Depuis</th><th>Lot</th><th class="end">Disponible</th><th></th><th v-if="planning"></th></tr></thead>
								<tbody>
									<tr v-for="line in ordre.matieres" :id="`ordre-${line.name}`" :key="line.name" :class="lineStatus(line).tone === 'tone-red' ? 'ordre-row-red' : lineStatus(line).tone === 'tone-amber' && 'ordre-row-amber'">
										<td><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: line.article } }">{{ line.designation }}</RouterLink><span class="block text-xs text-ink-gray-6">{{ line.type || line.article }}</span></td>
										<td class="end"><span class="inline-flex items-center gap-1"><input :value="String(line.prevu).replace('.', ',')" class="field-input w-24 text-right tabular-nums" inputmode="decimal" :disabled="!planning || busy" :aria-label="`Quantité de ${line.designation}`" @change="saveLine(line, { quantite: ($event.target as HTMLInputElement).value })" /><span class="text-xs text-ink-gray-6">{{ line.unite }}</span></span></td>
										<td>
											<select :value="line.depot ?? ''" class="field-input" :disabled="!planning || busy" :aria-label="`Dépôt de départ de ${line.designation}`" @change="saveLine(line, { depot: ($event.target as HTMLSelectElement).value })">
												<option v-if="line.depot && !(options?.depots ?? []).includes(line.depot)" :value="line.depot">{{ line.depot }}</option>
												<option v-for="depot in options?.depots" :key="depot" :value="depot">{{ depot }}</option>
											</select>
										</td>
										<td>
											<select v-if="line.avec_lot" :value="line.lot ?? ''" class="field-input" :disabled="!planning || busy" :aria-label="`Lot de ${line.designation}`" @change="saveLine(line, { lot: ($event.target as HTMLSelectElement).value })">
												<option value="">Choisir un lot…</option>
												<option v-if="line.lot && !line.lots.some((lot) => lot.lot === line.lot)" :value="line.lot">{{ line.lot }} · plus en stock</option>
												<option v-for="lot in line.lots" :key="lot.lot" :value="lot.lot">{{ lotLabel(lot) }}</option>
											</select>
											<span v-else class="text-ink-gray-6">sans lot</span>
										</td>
										<td class="end tabular-nums">{{ formatQty(line.disponible) }}</td>
										<td><span class="badge" :class="lineStatus(line).tone">{{ lineStatus(line).text }}</span></td>
										<td v-if="planning"><button type="button" class="icon-btn" :disabled="busy" :aria-label="`Retirer ${line.designation}`" @click="removeLine(line)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button></td>
									</tr>
								</tbody>
							</table></div>
							<p class="field-note">Lots proposés du plus proche de la péremption au plus lointain ; un lot périmé n'est jamais proposé.</p>
						</section>
					</template>

					<!-- Prêt à démarrer, en production, terminé : les matières de l'atelier. -->
					<section v-else class="card ref-card">
						<div class="ref-card-head">
							<h3>{{ state === 'En production' ? 'Matières utilisées' : state === 'Terminé' ? 'Matières : prévu et réel' : "Matières à l'atelier" }}</h3>
							<span v-if="state === 'En production'" class="text-xs text-ink-gray-6">à remplir pendant ou à la fin de la production</span>
						</div>
						<div class="ref-scroll"><table class="ref-table livraison-prep">
							<thead>
								<tr>
									<th>Matière</th><th>Lot</th><th class="end">Prévu</th><th class="end">Complément</th>
									<th v-if="state === 'Préparé'" class="end">À l'atelier</th>
									<template v-if="state === 'En production' || state === 'Terminé'"><th class="end">Utilisé</th><th class="end">Rebut</th><th class="end">Reste</th></template>
								</tr>
							</thead>
							<tbody>
								<tr v-for="line in ordre.matieres" :key="line.name">
									<td><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: line.article } }">{{ line.designation }}</RouterLink></td>
									<td class="tabular-nums"><RouterLink v-if="line.lot" class="ref-link" :to="{ name: 'Lot', params: { id: line.lot } }">{{ line.lot }}</RouterLink><span v-else class="text-ink-gray-6">sans lot</span></td>
									<td class="end tabular-nums">{{ formatQty(line.prevu) }} <span class="text-xs text-ink-gray-6">{{ line.unite }}</span></td>
									<td class="end tabular-nums" :class="!line.complement && 'text-ink-gray-6'">{{ line.complement ? `+ ${formatQty(line.complement)}` : '—' }}</td>
									<td v-if="state === 'Préparé'" class="end tabular-nums">{{ formatQty(line.disponible) }}</td>
									<template v-if="state === 'En production' || state === 'Terminé'">
										<td class="end">
											<input v-if="can('saisir')" v-model="utilises[line.name]" class="field-input w-24 text-right tabular-nums" inputmode="decimal" :disabled="busy" :aria-label="`Quantité utilisée de ${line.designation}`" @change="saveUtilise(line)" />
											<span v-else class="tabular-nums">{{ formatQty(line.utilise) }}</span>
										</td>
										<td class="end tabular-nums">{{ formatQty(rebutOf(line)) }}</td>
										<td class="end tabular-nums" :class="resteOf(line) < 0 ? 'font-semibold text-tone-red' : resteOf(line) === 0 && 'text-tone-green'">{{ formatQty(resteOf(line)) }}</td>
									</template>
								</tr>
							</tbody>
						</table></div>
						<p v-if="state === 'Préparé'" class="field-note">Il manque quelque chose à l'atelier ? « Ajouter un complément » envoie une quantité en plus, depuis le dépôt de votre choix.</p>
						<p v-else-if="state === 'En production'" class="field-note">Le reste n'est pas perdu : il reste au dépôt de l'atelier, pour un autre ordre ou un retour aux Magasins.</p>
					</section>

					<!-- Rebuts (en production) -->
					<section v-if="state === 'En production' || (state === 'Terminé' && ordre.rebuts.length)" class="card ref-card">
						<div class="ref-card-head">
							<h3>Rebuts</h3>
							<span class="inline-flex items-center gap-2">
								<span class="text-xs text-ink-gray-6">matières abîmées : elles iront au dépôt {{ ordre.depots.rebuts ?? 'des rebuts' }}</span>
								<button v-if="can('saisir')" type="button" class="btn-secondary" :disabled="busy" @click="rebut = { open: true, article: articles[0]?.article ?? '', quantite: '', error: '' }"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Ajouter un rebut</button>
							</span>
						</div>
						<p v-if="!ordre.rebuts.length" class="text-ink-gray-6">Aucun rebut pour l'instant.</p>
						<table v-else class="ref-table">
							<thead><tr><th>Matière</th><th>Lot</th><th class="end">Quantité</th><th v-if="can('saisir')"></th></tr></thead>
							<tbody>
								<tr v-for="row in ordre.rebuts" :key="row.name">
									<td>{{ row.designation }}</td>
									<td class="tabular-nums">{{ row.lot || 'sans lot' }}</td>
									<td class="end tabular-nums">{{ formatQty(row.quantite) }} <span class="text-xs text-ink-gray-6">{{ row.unite }}</span></td>
									<td v-if="can('saisir')"><button type="button" class="icon-btn" :disabled="busy" :aria-label="`Retirer le rebut de ${row.designation}`" @click="deleteRebut(row.name, row.designation)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button></td>
								</tr>
							</tbody>
						</table>
					</section>

					<!-- Compléments -->
					<section v-if="ordre.complements.length" class="card ref-card">
						<div class="ref-card-head"><h3>Compléments</h3><span class="text-xs text-ink-gray-6">envoyés à l'atelier en plus du prévu</span></div>
						<table class="ref-table">
							<tbody>
								<tr v-for="row in ordre.complements" :key="row.name">
									<td class="font-medium">{{ row.designation }}<span v-if="row.lot" class="text-xs text-ink-gray-6"> · {{ row.lot }}</span></td>
									<td class="tabular-nums">+ {{ formatQty(row.quantite) }} {{ row.unite }} depuis {{ row.depot }}</td>
									<td class="text-ink-gray-7">{{ row.par }}</td>
									<td class="end"><RouterLink v-if="row.mouvement" class="ref-link tabular-nums" :to="{ name: 'MouvementFiche', params: { id: row.mouvement } }">{{ row.mouvement }}</RouterLink></td>
								</tr>
							</tbody>
						</table>
					</section>

					<!-- Checklist -->
					<section v-if="state === 'Brouillon'" id="ordre-checklist" class="card ref-card">
						<div class="ref-card-head"><h3>Contrôles avant production</h3><span class="text-xs text-ink-gray-6">{{ ordre.modele_checklist }} · {{ controlesFaits }} sur {{ ordre.checklist.length }} faits</span></div>
						<div v-for="row in ordre.checklist" :key="row.name" class="ordre-check">
							<label class="ordre-check-main">
								<input type="checkbox" class="ordre-check-box" :checked="row.conforme" :disabled="!can('controler') || busy" @change="toggleControle(row.name, ($event.target as HTMLInputElement).checked)" />
								<span class="flex-auto font-medium">{{ row.controle }}</span>
								<span v-if="row.conforme && row.par" class="text-xs text-ink-gray-6">{{ row.par }}<template v-if="row.quand"> · {{ new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' }).format(new Date(row.quand.replace(' ', 'T'))) }}</template></span>
								<span v-else-if="row.obligatoire" class="badge tone-gray">obligatoire</span>
							</label>
							<button v-if="can('controler') && !row.observation && !remarques[row.name]" type="button" class="btn-ghost text-xs" @click="remarques[row.name] = true">Ajouter une remarque</button>
							<input v-if="row.observation || remarques[row.name]" :value="row.observation ?? ''" class="field-input ordre-check-note" placeholder="Remarque" :disabled="!can('controler') || busy" :aria-label="`Remarque sur ${row.controle}`" @change="saveObservation(row.name, ($event.target as HTMLInputElement).value)" />
						</div>
					</section>
					<section v-else-if="ordre.checklist.length" class="card flex items-center gap-2.5 px-4 py-3 text-sm">
						<span class="badge" :class="controlesFaits === ordre.checklist.length ? 'tone-green' : 'tone-amber'">{{ controlesFaits }} sur {{ ordre.checklist.length }}</span>
						<span class="flex-auto"><strong>Contrôles avant production</strong> : {{ controlesFaits === ordre.checklist.length ? 'tous conformes' : 'certains non cochés' }}.</span>
					</section>

					<!-- Mouvements de stock -->
					<section v-if="ordre.mouvements.length && state !== 'Brouillon'" class="card ref-card">
						<div class="ref-card-head"><h3>Mouvements de stock de cet ordre</h3><span class="text-xs text-ink-gray-6">aussi dans Stock › Mouvements</span></div>
						<table class="ref-table">
							<tbody>
								<tr v-for="row in ordre.mouvements" :key="row.name">
									<td><RouterLink class="ref-link tabular-nums" :to="{ name: 'MouvementFiche', params: { id: row.name } }">{{ row.name }}</RouterLink></td>
									<td>{{ row.label }}</td>
								</tr>
							</tbody>
						</table>
					</section>
				</div>

				<aside class="record-activity ordre-side" aria-label="Aide, lot et activité de l'ordre">
					<section v-if="ordre.manques.length" class="ordre-manques">
						<h3><LucideCircleAlert class="h-4 w-4" aria-hidden="true" />Ce qui manque pour préparer</h3>
						<p>Le bouton « Préparer » s'active quand tout est réglé.</p>
						<ol>
							<li v-for="(manque, index) in ordre.manques" :key="index">
								<button v-if="manque.cible" type="button" class="ordre-manque-link" @click="focusTarget(manque.cible)">{{ manque.texte }}</button>
								<span v-else>{{ manque.texte }}</span>
							</li>
						</ol>
					</section>
					<section v-else-if="state === 'Brouillon'" class="ordre-next">
						<h3>Tout est prêt</h3>
						<p>« Préparer » envoie les matières vers {{ ordre.depots.atelier ?? "l'atelier" }}. Elles restent réservées à cet ordre jusqu'à la clôture.</p>
					</section>
					<section v-else-if="state === 'Préparé'" class="ordre-next">
						<h3>Tout est prêt</h3>
						<p>Lancez la production quand la ligne démarre. L'heure est notée pour calculer la durée.</p>
					</section>
					<section v-else-if="state === 'En production'" class="ordre-next">
						<h3>Pour finir</h3>
						<p>Quand la production est faite, cliquez sur « Clôturer l'ordre… ». On vous demandera combien d'unités sont bonnes ; le stock se met à jour d'un coup.</p>
					</section>

					<section v-if="ordre.produit_avec_lot && state !== 'Annulé'" class="card ordre-lot">
						<span class="ordre-lot-icon" aria-hidden="true"><LucideLayers class="h-4 w-4" /></span>
						<div class="min-w-0 flex-auto">
							<h3 class="text-sm font-semibold">{{ state === 'Terminé' ? 'Lot produit' : 'Lot du produit fini' }}</h3>
							<p v-if="ordre.lot_pf" class="tabular-nums"><RouterLink class="ref-link" :to="{ name: 'Lot', params: { id: ordre.lot_pf } }">{{ ordre.lot_pf }}</RouterLink></p>
							<p v-else class="text-sm text-ink-gray-6">Créé tout seul à la clôture, ou dès maintenant.</p>
							<template v-if="ordre.tracabilite.length">
								<p class="mt-2 text-xs font-semibold text-ink-gray-7">Fabriqué avec</p>
								<p v-for="row in ordre.tracabilite" :key="row.lot" class="text-sm">{{ row.designation }}, lot <RouterLink class="ref-link" :to="{ name: 'Lot', params: { id: row.lot } }">{{ row.lot }}</RouterLink><span v-if="row.lot_fournisseur" class="text-ink-gray-6"> (fournisseur {{ row.lot_fournisseur }})</span></p>
							</template>
						</div>
						<button v-if="can('generer_lot') && !ordre.lot_pf" type="button" class="btn-secondary" :disabled="busy" @click="generer">Générer</button>
					</section>

					<ActivityFeed ref="feed" :api="activityApi" :version="ordre.modified" :user-name="userName" @changed="refresh()" />
				</aside>
			</div>
		</template>

		<FormDialog v-if="adding && ordre" title="Ajouter une matière" :dirty="Boolean(ajout.article)" :busy="busy" hint="Ctrl + Entrée pour ajouter" @close="adding = false" @submit="addLine">
			<div class="form-field">
				<label class="field-label" for="ordre-ajout-article">Matière <span class="req">obligatoire</span></label>
				<ChoicePicker :search="findArticles" :picked="ajout.label" input-id="ordre-ajout-article" placeholder="Article ou code" @pick="(choice: StockArticleChoice) => (ajout = { ...ajout, article: choice.name, label: choice.label })" @clear="ajout = { article: '', label: '', quantite: ajout.quantite }" />
			</div>
			<div class="form-field">
				<label class="field-label" for="ordre-ajout-quantite">Quantité <span class="req">obligatoire</span></label>
				<input id="ordre-ajout-quantite" v-model="ajout.quantite" class="field-input text-right tabular-nums" inputmode="decimal" />
			</div>
			<p v-if="ajoutError" class="field-error" role="alert">{{ ajoutError }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="addLine">Ajouter</button>
			</template>
		</FormDialog>

		<FormDialog v-if="rebut.open && ordre" title="Ajouter un rebut" :dirty="Boolean(rebut.quantite)" :busy="busy" hint="Ctrl + Entrée pour ajouter" @close="rebut.open = false" @submit="submitRebut">
			<div class="form-field">
				<label class="field-label" for="ordre-rebut-article">Matière abîmée</label>
				<select id="ordre-rebut-article" v-model="rebut.article" class="field-input">
					<option v-for="line in articles" :key="line.article" :value="line.article">{{ line.designation }}{{ line.lot ? ` · lot ${line.lot}` : '' }}</option>
				</select>
			</div>
			<div class="form-field">
				<label class="field-label" for="ordre-rebut-quantite">Quantité <span class="req">obligatoire</span></label>
				<input id="ordre-rebut-quantite" v-model="rebut.quantite" class="field-input text-right tabular-nums" inputmode="decimal" />
			</div>
			<p class="field-note">Le rebut part au dépôt {{ ordre.depots.rebuts ?? 'des rebuts' }} à la clôture de l'ordre.</p>
			<p v-if="rebut.error" class="field-error" role="alert">{{ rebut.error }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="submitRebut">Ajouter le rebut</button>
			</template>
		</FormDialog>

		<FormDialog v-if="complement.open && ordre" title="Ajouter un complément" :dirty="Boolean(complement.quantite)" :busy="busy" hint="Ctrl + Entrée pour envoyer" @close="complement.open = false" @submit="submitComplement">
			<p class="text-sm text-ink-gray-7">Envoie tout de suite une quantité en plus à l'atelier, pour une matière de l'ordre.</p>
			<div class="form-field">
				<label class="field-label" for="ordre-complement-article">Matière</label>
				<select id="ordre-complement-article" v-model="complement.article" class="field-input">
					<option v-for="line in articles" :key="line.article" :value="line.article">{{ line.designation }}</option>
				</select>
			</div>
			<div class="form-grid">
				<div class="form-field">
					<label class="field-label" for="ordre-complement-quantite">Quantité <span class="req">obligatoire</span></label>
					<span class="flex items-center gap-1.5"><input id="ordre-complement-quantite" v-model="complement.quantite" class="field-input text-right tabular-nums" inputmode="decimal" /><span class="text-sm text-ink-gray-7">{{ complementLine?.unite }}</span></span>
				</div>
				<div class="form-field">
					<label class="field-label" for="ordre-complement-depot">Depuis</label>
					<select id="ordre-complement-depot" v-model="complement.depot" class="field-input">
						<option v-for="depot in options?.depots" :key="depot" :value="depot">{{ depot }}</option>
					</select>
				</div>
			</div>
			<div v-if="complementLine?.avec_lot" class="form-field">
				<label class="field-label" for="ordre-complement-lot">Lot</label>
				<select id="ordre-complement-lot" v-model="complement.lot" class="field-input">
					<option value="">{{ complement.lots.length ? 'Choisir un lot…' : 'Aucun lot en stock dans ce dépôt' }}</option>
					<option v-for="lot in complement.lots" :key="lot.lot" :value="lot.lot">{{ lotLabel(lot) }}</option>
				</select>
			</div>
			<p v-if="complement.error" class="field-error" role="alert">{{ complement.error }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="submitComplement">Envoyer à l'atelier</button>
			</template>
		</FormDialog>

		<OrdreClotureDialog v-if="closing && ordre" :ordre="ordre" :utilises="utilises" @close="closing = false" @closed="onClosed" />

		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
	</main>
</template>
