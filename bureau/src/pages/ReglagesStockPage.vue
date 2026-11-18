<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import LucideSearch from '~icons/lucide/search'
import ListPager from '@shared/components/ListPager.vue'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import { getReglagesStock, getSeuils, saveParametresStock, setSeuil } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { confirmAction } from '@/lib/confirm'
import { SEUIL_VUES, seuilChange, seuilDraft, seuilErreur, VALORISATION, type ReglagesStock, type SeuilDraft, type SeuilLigne, type SeuilsResponse, type SeuilVue } from '@/lib/reglagesStock'

/**
 * Réglages › Stock et seuils : les paramètres de stock repris par le bureau, et le seuil de réapprovisionnement de
 * chaque article par dépôt. Un seuil se saisit dans sa ligne ; il est enregistré en quittant la ligne ou sur Entrée.
 */
const reglages = ref<ReglagesStock | null>(null)
const error = ref('')
const actionError = ref('')
const notice = ref('')
const busy = ref(false)

// Paramètres : copie de travail.
const parametres = ref({ default_warehouse: '', stock_uom: '', allow_negative_stock: false, auto_indent: false })
const parametresBase = ref(JSON.stringify(parametres.value))
const parametresDirty = computed(() => JSON.stringify(parametres.value) !== parametresBase.value)

function apply(fresh: ReglagesStock) {
	reglages.value = fresh
	if (!parametresDirty.value) {
		const p = fresh.parametres
		parametres.value = { default_warehouse: p.default_warehouse ?? '', stock_uom: p.stock_uom ?? '', allow_negative_stock: p.allow_negative_stock, auto_indent: p.auto_indent }
		parametresBase.value = JSON.stringify(parametres.value)
	}
	if (!depot.value || !fresh.depots.includes(depot.value)) depot.value = fresh.parametres.default_warehouse && fresh.depots.includes(fresh.parametres.default_warehouse) ? fresh.parametres.default_warehouse : fresh.depots[0] ?? ''
}
async function load() {
	try {
		apply(await getReglagesStock())
		error.value = ''
	} catch (e) {
		if (!reglages.value) error.value = (e as Error).message
	}
}

async function enregistrerParametres() {
	if (busy.value || !reglages.value) return
	const avant = reglages.value.parametres
	if (parametres.value.allow_negative_stock && !avant.allow_negative_stock) {
		const ok = await confirmAction({ title: 'Autoriser le stock négatif', message: "Une sortie pourra être validée même sans stock suffisant. Le stock affiché et sa valeur deviennent faux jusqu'à la régularisation. À n'utiliser que le temps d'une reprise de stock.", confirmLabel: 'Autoriser', danger: true })
		if (!ok) return
	}
	busy.value = true
	actionError.value = ''
	try {
		apply(await saveParametresStock(avant.modified, parametres.value).then((fresh) => ((parametresBase.value = JSON.stringify(parametres.value)), fresh)))
		notice.value = 'Paramètres enregistrés.'
	} catch (e) {
		actionError.value = (e as Error).message
		await load()
	} finally {
		busy.value = false
	}
}

// Seuils.
const depot = ref('')
const search = ref('')
const vue = ref<SeuilVue>('tous')
const page = ref(0)
const reponse = ref<SeuilsResponse | null>(null)
const drafts = reactive<Record<string, SeuilDraft>>({})
const rowErrors = reactive<Record<string, string>>({})
const saving = reactive<Record<string, boolean>>({})
const highlighted = ref<string | null>(null)
const canEdit = computed(() => reglages.value?.droits.seuils ?? false)

let requestId = 0
async function loadSeuils() {
	if (!depot.value) return
	const id = ++requestId
	try {
		const fresh = await getSeuils(depot.value, { search: search.value.trim(), vue: vue.value, start: page.value * 50 })
		if (id !== requestId) return
		reponse.value = fresh
		for (const ligne of fresh.lignes) if (!rowErrors[ligne.article]) drafts[ligne.article] = seuilDraft(ligne)
	} catch (e) {
		if (id === requestId) actionError.value = (e as Error).message
	}
}
watch(depot, () => {
	page.value = 0
	reponse.value = null
	loadSeuils()
})
let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(search, () => {
	if (searchTimer) clearTimeout(searchTimer)
	searchTimer = setTimeout(() => {
		page.value = 0
		loadSeuils()
	}, 250)
})
watch(vue, () => {
	page.value = 0
	loadSeuils()
})
watch(page, loadSeuils)

async function save(ligne: SeuilLigne) {
	const draft = drafts[ligne.article]
	if (!draft || !canEdit.value || saving[ligne.article] || !seuilChange(draft, ligne)) return
	const erreur = seuilErreur(draft)
	if (erreur) {
		rowErrors[ligne.article] = erreur
		return
	}
	saving[ligne.article] = true
	delete rowErrors[ligne.article]
	try {
		const fresh = await setSeuil(depot.value, ligne, draft.seuil, draft.quantite)
		const rows = reponse.value?.lignes ?? []
		const index = rows.findIndex((row) => row.article === fresh.article)
		if (index >= 0) rows[index] = fresh
		drafts[fresh.article] = seuilDraft(fresh)
		notice.value = fresh.seuil ? 'Seuil enregistré.' : 'Seuil retiré.'
		highlighted.value = fresh.article
		setTimeout(() => highlighted.value === fresh.article && (highlighted.value = null), 1500)
		refreshCounts()
	} catch (e) {
		rowErrors[ligne.article] = (e as Error).message
	} finally {
		saving[ligne.article] = false
	}
}
/** Enregistre quand le focus quitte la ligne (pas en passant du seuil à la quantité). */
function onRowFocusOut(event: FocusEvent, ligne: SeuilLigne) {
	const row = event.currentTarget as HTMLElement
	if (event.relatedTarget instanceof Node && row.contains(event.relatedTarget)) return
	save(ligne)
}
function onKey(event: KeyboardEvent, ligne: SeuilLigne) {
	if (event.key === 'Enter') {
		event.preventDefault()
		save(ligne)
	} else if (event.key === 'Escape') {
		drafts[ligne.article] = seuilDraft(ligne)
		delete rowErrors[ligne.article]
		;(event.target as HTMLInputElement).blur()
	}
}
async function refreshCounts() {
	try {
		if (reponse.value) reponse.value.compte = (await getSeuils(depot.value, { search: search.value.trim(), vue: vue.value, start: page.value * 50 })).compte
	} catch {
		// Les compteurs se remettront à jour au prochain chargement.
	}
}

onMounted(load)
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Réglages' }, { label: 'Stock et seuils' }]" active="reglages-stock">
		<div class="bureau-work tdb">
			<div>
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Stock et seuils</h1>
				<p class="text-sm text-ink-gray-6">Les paramètres de stock repris par le bureau, et le seuil sous lequel chaque article est à recommander.</p>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!reglages" class="card p-4 text-ink-gray-6">Chargement des réglages…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<section v-if="reglages" class="card reglages-card" aria-labelledby="t-parametres">
				<div>
					<h2 id="t-parametres" class="text-base font-semibold">Paramètres</h2>
					<p v-if="!reglages.droits.parametres" class="text-sm text-ink-gray-6">Lecture seule pour votre rôle.</p>
				</div>
				<div class="form-grid">
					<div class="form-field">
						<label class="field-label" for="stock-depot">Dépôt de réception par défaut</label>
						<select v-search id="stock-depot" v-model="parametres.default_warehouse" class="field-input" :disabled="!reglages.droits.parametres">
							<option value="">—</option>
							<option v-for="d in reglages.depots" :key="d" :value="d">{{ d }}</option>
						</select>
						<p class="field-note">Proposé sur chaque nouvelle commande d'achat.</p>
					</div>
					<div class="form-field">
						<label class="field-label" for="stock-unite">Unité des nouveaux articles</label>
						<select v-search id="stock-unite" v-model="parametres.stock_uom" class="field-input" :disabled="!reglages.droits.parametres">
							<option value="">—</option>
							<option v-for="u in reglages.unites" :key="u" :value="u">{{ u }}</option>
						</select>
						<p class="field-note">Présélectionnée à la création d'un article.</p>
					</div>
					<div class="form-field">
						<span class="field-label">Valorisation du stock</span>
						<p class="text-sm">{{ VALORISATION[reglages.parametres.valuation_method ?? ''] ?? reglages.parametres.valuation_method ?? '—' }}</p>
						<p class="field-note">Fixée à la mise en route ; à ne changer qu'avec votre comptable, sur le Desk.</p>
					</div>
				</div>
				<label class="flex items-start gap-2 text-sm">
					<input v-model="parametres.auto_indent" type="checkbox" class="mt-0.5" :disabled="!reglages.droits.parametres" />
					<span><b>Demandes d'achat automatiques</b> — chaque nuit, ERPNext crée une demande d'achat pour les articles passés sous leur seuil. Ces demandes ne s'affichent que sur le Desk ; dans le bureau, suivez plutôt la vue « Sous le seuil » de l'état du stock.</span>
				</label>
				<label class="flex items-start gap-2 text-sm">
					<input v-model="parametres.allow_negative_stock" type="checkbox" class="mt-0.5" :disabled="!reglages.droits.parametres" />
					<span><b>Autoriser le stock négatif</b> — <span class="text-tone-red">déconseillé</span> : une sortie passe même sans stock, et le stock affiché devient faux.</span>
				</label>
				<div v-if="reglages.droits.parametres" class="flex justify-end"><button type="button" class="btn-primary" :disabled="busy || !parametresDirty" @click="enregistrerParametres">Enregistrer</button></div>
			</section>

			<section v-if="reglages" class="card reglages-card" aria-labelledby="t-seuils">
				<div>
					<h2 id="t-seuils" class="text-base font-semibold">Seuils de réapprovisionnement</h2>
					<p class="text-sm text-ink-gray-6">Sous son seuil, l'article apparaît dans la vue « Sous le seuil » de l'état du stock et sur le tableau de bord. La quantité à commander est indicative ; vide, c'est le seuil.</p>
				</div>
				<div class="flex flex-wrap gap-1.5" role="group" aria-label="Dépôts">
					<button v-for="d in reglages.depots" :key="d" type="button" class="reglages-tab" :aria-pressed="d === depot" @click="depot = d">{{ d }}</button>
				</div>
				<div class="flex flex-wrap items-center gap-2">
					<label class="bureau-search">
						<LucideSearch class="h-3.5 w-3.5" aria-hidden="true" />
						<input v-model="search" class="field-input" type="search" aria-label="Chercher un article" placeholder="Article ou code" />
					</label>
					<div class="seg" role="group" aria-label="Afficher">
						<button v-for="item in SEUIL_VUES" :key="item.key" type="button" :aria-pressed="vue === item.key" @click="vue = item.key">
							{{ item.label }}<span v-if="reponse" class="tabular-nums text-ink-gray-6"> {{ reponse.compte[item.key] }}</span>
						</button>
					</div>
				</div>
				<p v-if="!reponse" class="text-ink-gray-6">Chargement des articles…</p>
				<p v-else-if="!reponse.lignes.length" class="text-ink-gray-6">Aucun article ne correspond.</p>
				<div v-else class="overflow-x-auto">
					<table class="ref-table tarifs-table">
						<thead>
							<tr>
								<th>Article</th>
								<th class="end">En stock</th>
								<th class="end">Seuil</th>
								<th class="end">À commander</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="ligne in reponse.lignes" :key="ligne.article" :class="highlighted === ligne.article && 'devis-line-new'" @focusout="onRowFocusOut($event, ligne)">
								<td>
									<RouterLink :to="{ name: 'Article', params: { id: ligne.article } }" class="font-medium">{{ ligne.designation }}</RouterLink>
									<small class="block text-ink-gray-6">{{ ligne.article }}</small>
									<small v-if="rowErrors[ligne.article]" role="alert" class="block text-tone-red">{{ rowErrors[ligne.article] }}</small>
								</td>
								<td class="end tabular-nums" :class="ligne.seuil !== null && ligne.stock < ligne.seuil ? 'font-semibold text-tone-red' : ''">{{ formatQty(ligne.stock) }} <small class="text-ink-gray-6">{{ ligne.unite }}</small></td>
								<template v-if="canEdit && drafts[ligne.article]">
									<td class="end"><input v-model="drafts[ligne.article].seuil" class="field-input tarifs-prix end tabular-nums" inputmode="decimal" placeholder="Aucun" :aria-label="`Seuil, ${ligne.designation}`" :aria-invalid="Boolean(rowErrors[ligne.article])" :disabled="saving[ligne.article]" @keydown="onKey($event, ligne)" /></td>
									<td class="end"><input v-model="drafts[ligne.article].quantite" class="field-input tarifs-prix end tabular-nums" inputmode="decimal" :placeholder="drafts[ligne.article].seuil || '—'" :aria-label="`Quantité à commander, ${ligne.designation}`" :disabled="saving[ligne.article] || !drafts[ligne.article].seuil.trim()" @keydown="onKey($event, ligne)" /></td>
								</template>
								<template v-else>
									<td class="end tabular-nums" :class="!ligne.seuil && 'text-ink-gray-6'">{{ ligne.seuil ? formatQty(ligne.seuil) : 'Aucun' }}</td>
									<td class="end tabular-nums">{{ ligne.quantite ? formatQty(ligne.quantite) : '—' }}</td>
								</template>
							</tr>
						</tbody>
					</table>
				</div>
				<ListPager v-if="reponse && reponse.total > reponse.page" :total="reponse.total" :page="page" :page-size="reponse.page" :sizes="[reponse.page]" sort-label="Par désignation" @update:page="(value) => (page = value)" />
			</section>
		</div>
		<AppToast :message="notice" tone="success" @close="notice = ''" />
	</BureauShell>
</template>
