<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import LucideFolder from '~icons/lucide/folder'
import LucideFolderPlus from '~icons/lucide/folder-plus'
import LucideLock from '~icons/lucide/lock'
import LucidePlus from '~icons/lucide/plus'
import LucideTrash2 from '~icons/lucide/trash-2'
import FormDialog from '@shared/components/FormDialog.vue'
import LucideSearch from '~icons/lucide/search'
import ListPager from '@shared/components/ListPager.vue'
import AchatDialog from '@/components/AchatDialog.vue'
import AppToast from '@/components/AppToast.vue'
import DepotDialog from '@/components/DepotDialog.vue'
import BureauShell from '@/components/BureauShell.vue'
import { creerDossierDepots, deplacerDepot, getACommander, getReglagesStock, getSeuils, saveParametresStock, setSeuil, supprimerDepot, supprimerDossierDepots } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { confirmAction } from '@/lib/confirm'
import { canCreate } from '@/lib/droits'
import { arbreDepots, etatSeuil, jaugeSeuil, SEUIL_VUES, seuilChange, seuilDraft, seuilErreur, VALORISATION, type ACommander, type ReglagesStock, type SeuilDraft, type SeuilLigne, type SeuilsResponse, type SeuilVue } from '@/lib/reglagesStock'

/**
 * Réglages › Stock et seuils : les paramètres de stock repris par le bureau, et le seuil de réapprovisionnement de
 * chaque article par dépôt. À gauche, « Paramètres » puis un dépôt par ligne avec ses articles sous le seuil.
 * Un seuil se saisit dans sa ligne ; il est enregistré en quittant la ligne ou sur Entrée. Les articles sous leur
 * seuil se reprennent dans une commande d'achat préparée pour ce dépôt.
 */
const router = useRouter()
/** Ce qui est affiché à droite : les paramètres, ou les seuils d'un dépôt. */
const section = ref<'parametres' | 'seuils'>('seuils')
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

function annulerParametres() {
	parametres.value = JSON.parse(parametresBase.value)
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
		const fresh = await getReglagesStock()
		if (reglages.value) reglages.value.resume = fresh.resume
	} catch {
		// Les compteurs se remettront à jour au prochain chargement.
	}
}

// Arbre des dépôts : dossiers (groupes) et dépôts, toujours dépliés.
const arbre = computed(() => arbreDepots(reglages.value?.arbre ?? []))
const dossiers = computed(() => arbre.value.filter((n) => n.dossier))
const noeudDepot = computed(() => reglages.value?.arbre.find((n) => n.name === depot.value) ?? null)

async function action(appel: () => Promise<ReglagesStock>, message: string) {
	if (busy.value) return false
	busy.value = true
	actionError.value = ''
	try {
		apply(await appel())
		notice.value = message
		return true
	} catch (e) {
		actionError.value = (e as Error).message
		await load()
		return false
	} finally {
		busy.value = false
	}
}

const nouveauDepot = ref<{ parent: string | null } | null>(null)
async function onDepotCree(name: string) {
	nouveauDepot.value = null
	await load()
	notice.value = `Dépôt « ${name} » créé.`
	ouvrirDepot(name)
}

const nouveauDossier = ref<{ nom: string; dossier: string; error: string } | null>(null)
async function creerDossier() {
	const form = nouveauDossier.value
	if (!form) return
	if (!form.nom.trim()) {
		form.error = 'Donnez un nom au dossier.'
		return
	}
	if (await action(() => creerDossierDepots(form.nom.trim(), form.dossier || null), `Dossier « ${form.nom.trim()} » créé.`)) nouveauDossier.value = null
}

async function ranger(dossier: string) {
	const noeud = noeudDepot.value
	if (!noeud || (noeud.parent ?? '') === dossier) return
	await action(() => deplacerDepot(noeud, dossier || null), `« ${noeud.label} » rangé dans ${dossier ? `« ${dossiers.value.find((d) => d.name === dossier)?.label ?? dossier} »` : 'la racine'}.`)
}

async function supprimerLeDepot() {
	const nom = depot.value
	if (!nom || !reglages.value) return
	const seuils = reglages.value.resume[nom]?.seuils ?? 0
	const ok = await confirmAction({
		title: 'Supprimer le dépôt',
		message: `« ${nom} » sera supprimé${seuils ? `, avec ses ${seuils} seuil${seuils > 1 ? 's' : ''}` : ''}. Seul un dépôt qui n'a jamais eu de stock ni de mouvement peut l'être ; sinon, désactivez-le depuis sa fiche.`,
		confirmLabel: 'Supprimer le dépôt',
		danger: true,
	})
	if (!ok) return
	if (await action(() => supprimerDepot(nom), `Dépôt « ${nom} » supprimé.`)) section.value = 'parametres'
}

async function supprimerDossier(nom: string, label: string) {
	if (!(await confirmAction({ title: 'Supprimer le dossier', message: `Le dossier « ${label} » sera supprimé.`, confirmLabel: 'Supprimer', danger: true }))) return
	await action(() => supprimerDossierDepots(nom), `Dossier « ${label} » supprimé.`)
}

function ouvrirDepot(nom: string) {
	section.value = 'seuils'
	depot.value = nom
}

// Préparer une commande d'achat avec les articles sous le seuil du dépôt.
const peutCommander = computed(() => canCreate('Purchase Order'))
const commande = ref<ACommander | null>(null)
async function preparerCommande() {
	if (busy.value) return
	busy.value = true
	actionError.value = ''
	try {
		const fresh = await getACommander(depot.value)
		if (!fresh.lignes.length) notice.value = "Aucun article achetable n'est sous son seuil dans ce dépôt."
		else commande.value = fresh
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
function onCommandeCreee(name: string) {
	commande.value = null
	router.push({ name: 'CommandeAchatFiche', params: { id: name } })
}

onMounted(load)
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Réglages' }, { label: 'Stock et seuils' }]" active="reglages-stock">
		<div class="bureau-work tdb">
			<div>
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Stock et seuils</h1>
				<p class="text-sm text-ink-gray-6">Les paramètres de stock repris par le bureau, et, pour chaque dépôt, le seuil sous lequel un article est à recommander.</p>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!reglages" class="card p-4 text-ink-gray-6">Chargement des réglages…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<div v-if="reglages" class="tarifs-layout">
				<nav class="card tarifs-liste" aria-label="Sections">
					<div class="tarifs-groupe">
						<button type="button" class="tarif-item text-left" :aria-current="section === 'parametres' ? 'page' : undefined" @click="section = 'parametres'">
							<span class="font-semibold">Paramètres</span>
							<span class="text-xs text-ink-gray-6">Dépôt de réception, unité, stock négatif</span>
						</button>
					</div>
					<div class="tarifs-groupe">
						<span class="px-2.5 text-xs font-semibold uppercase tracking-wide text-ink-gray-6">Seuils par dépôt</span>
						<template v-for="noeud in arbre" :key="noeud.name">
							<div v-if="noeud.dossier" class="depot-dossier" :style="{ paddingLeft: `${0.625 + (noeud.niveau - 1) * 1}rem` }">
								<LucideFolder class="h-4 w-4 flex-none text-[var(--accent)]" aria-hidden="true" />
								<span class="min-w-0 flex-auto font-semibold">{{ noeud.label }}</span>
								<button v-if="reglages.droits.creer_depot" type="button" class="app-icon-bare" :disabled="busy" :aria-label="`Nouveau dépôt dans ${noeud.label}`" title="Nouveau dépôt dans ce dossier" @click="nouveauDepot = { parent: noeud.name }"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" /></button>
								<button v-if="reglages.droits.supprimer_depot && !noeud.enfants" type="button" class="app-icon-bare text-tone-red" :disabled="busy" :aria-label="`Supprimer le dossier ${noeud.label}`" title="Supprimer ce dossier vide" @click="supprimerDossier(noeud.name, noeud.label)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button>
							</div>
							<button v-else type="button" class="tarif-item text-left" :style="{ paddingLeft: `${0.625 + (noeud.niveau - 1) * 1}rem` }" :aria-current="section === 'seuils' && noeud.name === depot ? 'page' : undefined" @click="ouvrirDepot(noeud.name)">
								<span class="font-medium">{{ noeud.label }}</span>
								<span class="flex flex-wrap items-center gap-1.5 text-xs tabular-nums text-ink-gray-6">
									{{ reglages.resume[noeud.name]?.seuils ?? 0 }} seuil{{ (reglages.resume[noeud.name]?.seuils ?? 0) > 1 ? 's' : '' }}
									<span v-if="reglages.resume[noeud.name]?.sous" class="badge tone-red">{{ reglages.resume[noeud.name].sous }} sous le seuil</span>
								</span>
							</button>
						</template>
						<p v-if="!arbre.length" class="px-2.5 text-sm text-ink-gray-6">Aucun dépôt : créez-en un pour y poser des seuils.</p>
						<div v-if="reglages.droits.creer_depot" class="flex flex-wrap gap-1.5 px-1.5 pt-2">
							<button type="button" class="btn-secondary btn-sm" :disabled="busy" @click="nouveauDepot = { parent: null }"><LucidePlus class="h-3 w-3" aria-hidden="true" />Nouveau dépôt</button>
							<button type="button" class="btn-ghost btn-sm" :disabled="busy" @click="nouveauDossier = { nom: '', dossier: '', error: '' }"><LucideFolderPlus class="h-3 w-3" aria-hidden="true" />Nouveau dossier</button>
						</div>
					</div>
				</nav>

				<section v-if="section === 'parametres'" class="card tarifs-detail" aria-labelledby="t-parametres">
					<div class="tarifs-head border-b-0 pb-1">
						<h2 id="t-parametres" class="text-lg font-semibold">Paramètres</h2>
						<p class="text-sm text-ink-gray-6">Ce qui change dans le bureau : les valeurs proposées sur les nouvelles pièces et les règles des mouvements de stock.<template v-if="!reglages.droits.parametres"> Lecture seule pour votre rôle.</template></p>
					</div>
					<div class="flex flex-col px-4 pb-2">
						<h3 class="stock-groupe-titre">Valeurs proposées</h3>
						<div class="form-grid pb-4">
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
						</div>

						<h3 class="stock-groupe-titre">Règles de stock</h3>
						<div class="stock-reglage">
							<div class="min-w-0 flex-auto">
								<label for="stock-negatif" class="font-semibold">Autoriser le stock négatif</label>
								<p class="text-sm text-ink-gray-6">Une sortie passe même sans stock suffisant. Déconseillé : le stock affiché devient faux, et sa valeur aussi.</p>
								<p v-if="parametres.allow_negative_stock" role="alert" class="mt-1.5 rounded-control tone-red px-3 py-2 text-sm">Activé : livraisons et consommations de production passent même sans stock. À réserver au temps d'une reprise de stock, puis à désactiver.</p>
							</div>
							<input id="stock-negatif" v-model="parametres.allow_negative_stock" type="checkbox" role="switch" class="table-panel-switch stock-switch-danger" :disabled="!reglages.droits.parametres" />
						</div>
						<div class="stock-reglage">
							<div class="min-w-0 flex-auto">
								<span class="flex items-center gap-1.5 font-semibold"><LucideLock class="h-3.5 w-3.5 text-ink-gray-6" aria-hidden="true" />Valorisation du stock</span>
								<p class="text-sm text-ink-gray-6">Fixée à la mise en route. Elle ne se change qu'avec votre comptable, dans l'ERP.</p>
							</div>
							<span class="badge tone-gray flex-none">{{ VALORISATION[reglages.parametres.valuation_method ?? ''] ?? reglages.parametres.valuation_method ?? '—' }}</span>
						</div>

						<h3 class="stock-groupe-titre">Réapprovisionnement</h3>
						<div class="stock-reglage">
							<div class="min-w-0 flex-auto">
								<label for="stock-auto" class="font-semibold">Demandes d'achat automatiques</label>
								<p class="text-sm text-ink-gray-6">Chaque nuit, l'ERP crée une demande d'achat pour les articles passés sous leur seuil. Ces demandes ne s'affichent pas dans le bureau : suivez plutôt « Sous le seuil » de chaque dépôt.</p>
							</div>
							<input id="stock-auto" v-model="parametres.auto_indent" type="checkbox" role="switch" class="table-panel-switch" :disabled="!reglages.droits.parametres" />
						</div>
					</div>
					<div v-if="reglages.droits.parametres" class="stock-barre" :class="parametresDirty && 'is-dirty'">
						<span class="flex-auto text-sm" :class="parametresDirty ? 'font-medium text-tone-amber' : 'text-ink-gray-6'">{{ parametresDirty ? 'Modifications non enregistrées' : 'Aucune modification' }}</span>
						<button type="button" class="btn-ghost" :disabled="busy || !parametresDirty" @click="annulerParametres">Annuler</button>
						<button type="button" class="btn-primary" :disabled="busy || !parametresDirty" @click="enregistrerParametres">Enregistrer</button>
					</div>
				</section>

				<section v-else class="card tarifs-detail" aria-labelledby="t-seuils">
					<div class="tarifs-head">
						<div class="flex flex-wrap items-start gap-3">
							<div class="min-w-0 flex-[1_1_20rem]">
								<h2 id="t-seuils" class="text-lg font-semibold">Seuils — {{ depot }}</h2>
								<p class="text-sm text-ink-gray-6">Sous son seuil, l'article apparaît dans « Sous le seuil » de l'état du stock et sur le tableau de bord. La quantité à commander est indicative ; vide, c'est le seuil.</p>
							</div>
							<div v-if="reponse" class="flex flex-wrap gap-1.5">
								<span class="badge tone-gray">{{ reponse.compte.avec_seuil }} avec seuil</span>
								<span class="badge tone-gray">{{ reponse.compte.sans_seuil }} sans seuil</span>
							</div>
						</div>
						<div class="flex flex-wrap items-center gap-2 text-sm">
							<label v-if="noeudDepot && reglages.droits.creer_depot" class="flex items-center gap-1.5 text-ink-gray-7">
								Rangé dans
								<select class="field-input w-auto" :value="noeudDepot.parent ?? ''" :disabled="busy" aria-label="Dossier du dépôt" @change="ranger(($event.target as HTMLSelectElement).value)">
									<option value="">la racine</option>
									<option v-for="d in dossiers" :key="d.name" :value="d.name">{{ '\u00a0\u00a0'.repeat(d.niveau - 1) }}{{ d.label }}</option>
								</select>
							</label>
							<span class="flex-auto"></span>
							<RouterLink :to="{ name: 'Depot', params: { id: depot } }" class="btn-ghost btn-sm">Fiche du dépôt</RouterLink>
							<button v-if="reglages.droits.supprimer_depot" type="button" class="btn-danger btn-sm" :disabled="busy" @click="supprimerLeDepot"><LucideTrash2 class="h-3 w-3" aria-hidden="true" />Supprimer le dépôt</button>
						</div>
						<div v-if="reponse?.compte.sous_seuil" class="tarifs-bandeau tone-red">
							<span class="flex-auto"><b>{{ reponse.compte.sous_seuil }} article{{ reponse.compte.sous_seuil > 1 ? 's sont' : ' est' }} sous {{ reponse.compte.sous_seuil > 1 ? 'leur' : 'son' }} seuil</b> dans ce dépôt.</span>
							<button v-if="vue !== 'sous_seuil'" type="button" class="btn-secondary" @click="vue = 'sous_seuil'">Voir {{ reponse.compte.sous_seuil > 1 ? `les ${reponse.compte.sous_seuil} articles` : "l'article" }}</button>
							<button v-if="peutCommander" type="button" class="btn-primary" :disabled="busy" @click="preparerCommande">Préparer une commande d'achat</button>
						</div>
					</div>
					<div class="tarifs-outils pb-3">
						<label class="bureau-search">
							<LucideSearch class="h-3.5 w-3.5" aria-hidden="true" />
							<input v-model="search" class="field-input" type="search" aria-label="Chercher un article" placeholder="Article ou code" />
						</label>
						<div class="seg flex-wrap" role="group" aria-label="Afficher">
							<button v-for="item in SEUIL_VUES" :key="item.key" type="button" :aria-pressed="vue === item.key" @click="vue = item.key">
								{{ item.label }}<span v-if="reponse" class="ml-1 tabular-nums" :class="item.key === 'sous_seuil' && reponse.compte.sous_seuil ? 'text-tone-red' : 'text-ink-gray-6'">{{ reponse.compte[item.key] }}</span>
							</button>
						</div>
						<span class="flex-auto"></span>
						<span v-if="canEdit" class="text-xs text-ink-gray-6">Entrée enregistre · Échap annule · seuil vide = aucun</span>
						<span v-else class="text-xs text-ink-gray-6">Lecture seule : votre rôle ne modifie pas les articles.</span>
					</div>
					<p v-if="!reponse" class="px-4 pb-4 text-ink-gray-6">Chargement des articles…</p>
					<p v-else-if="!reponse.lignes.length" class="px-4 pb-4 text-ink-gray-6">{{ vue === 'sous_seuil' ? 'Aucun article sous son seuil dans ce dépôt.' : 'Aucun article ne correspond.' }}</p>
					<div v-else class="overflow-x-auto border-t border-[var(--line-soft)]">
						<table class="ref-table tarifs-table stock-table">
							<thead>
								<tr>
									<th>Article</th>
									<th>En stock</th>
									<th class="end">Seuil</th>
									<th class="end">À commander</th>
									<th>État</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="ligne in reponse.lignes" :key="ligne.article" :class="[highlighted === ligne.article && 'devis-line-new', etatSeuil(ligne).tone === 'red' && 'stock-sous']" @focusout="onRowFocusOut($event, ligne)">
									<td>
										<RouterLink :to="{ name: 'Article', params: { id: ligne.article } }" class="font-medium">{{ ligne.designation }}</RouterLink>
										<small class="block text-ink-gray-6">{{ ligne.article }}</small>
										<small v-if="rowErrors[ligne.article]" role="alert" class="block text-tone-red">{{ rowErrors[ligne.article] }}</small>
									</td>
									<td>
										<div class="flex items-center gap-2.5">
											<span class="whitespace-nowrap font-semibold tabular-nums" :class="etatSeuil(ligne).tone === 'red' ? 'text-tone-red' : 'text-ink-gray-9'">{{ formatQty(ligne.stock) }} <small class="font-normal text-ink-gray-6">{{ ligne.unite }}</small></span>
											<span v-if="ligne.seuil" class="stock-jauge" aria-hidden="true">
												<span class="stock-jauge-niveau" :class="etatSeuil(ligne).tone === 'red' && 'is-sous'" :style="{ width: `${jaugeSeuil(ligne.stock, ligne.seuil).stock}%` }"></span>
												<span class="stock-jauge-seuil" :style="{ left: `${jaugeSeuil(ligne.stock, ligne.seuil).seuil}%` }"></span>
											</span>
										</div>
									</td>
									<template v-if="canEdit && drafts[ligne.article]">
										<td class="end"><input v-model="drafts[ligne.article].seuil" class="field-input tarifs-prix end tabular-nums" inputmode="decimal" placeholder="Aucun" :aria-label="`Seuil, ${ligne.designation}`" :aria-invalid="Boolean(rowErrors[ligne.article])" :disabled="saving[ligne.article]" @keydown="onKey($event, ligne)" /></td>
										<td class="end"><input v-model="drafts[ligne.article].quantite" class="field-input tarifs-prix end tabular-nums" inputmode="decimal" :placeholder="drafts[ligne.article].seuil || '—'" :aria-label="`Quantité à commander, ${ligne.designation}`" :disabled="saving[ligne.article] || !drafts[ligne.article].seuil.trim()" @keydown="onKey($event, ligne)" /></td>
									</template>
									<template v-else>
										<td class="end tabular-nums" :class="!ligne.seuil && 'text-ink-gray-6'">{{ ligne.seuil ? formatQty(ligne.seuil) : 'Aucun' }}</td>
										<td class="end tabular-nums">{{ ligne.quantite ? formatQty(ligne.quantite) : '—' }}</td>
									</template>
									<td>
										<span v-if="etatSeuil(ligne).tone" class="badge" :class="etatSeuil(ligne).tone === 'red' ? 'tone-red' : 'tone-green'">{{ etatSeuil(ligne).label }}</span>
										<span v-else class="text-sm text-ink-gray-6">{{ etatSeuil(ligne).label }}</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
					<p v-if="reponse?.lignes.length" class="field-note px-4 pt-2">Le trait sur la barre marque le seuil.</p>
					<div class="px-4 pb-3">
						<ListPager v-if="reponse && reponse.total > reponse.page" :total="reponse.total" :page="page" :page-size="reponse.page" :sizes="[reponse.page]" sort-label="Par désignation" @update:page="(value) => (page = value)" />
					</div>
				</section>
			</div>
		</div>
		<DepotDialog v-if="nouveauDepot" :parent="nouveauDepot.parent" @close="nouveauDepot = null" @created="onDepotCree" />
		<FormDialog v-if="nouveauDossier" title="Nouveau dossier de dépôts" :dirty="Boolean(nouveauDossier.nom.trim())" :busy="busy" @close="nouveauDossier = null" @submit="creerDossier">
			<p class="text-sm text-ink-gray-7">Un dossier range des dépôts (par site, par usage…). Il ne reçoit pas de stock lui-même.</p>
			<div class="form-grid">
				<div class="form-field">
					<label class="field-label" for="dossier-depots-nom">Nom du dossier <span class="req">obligatoire</span></label>
					<input id="dossier-depots-nom" v-model="nouveauDossier.nom" class="field-input" autocomplete="off" placeholder="Ex. Usine de Batna" @input="nouveauDossier.error = ''" />
				</div>
				<div class="form-field">
					<label class="field-label" for="dossier-depots-parent">Dans</label>
					<select id="dossier-depots-parent" v-model="nouveauDossier.dossier" class="field-input">
						<option value="">la racine</option>
						<option v-for="d in dossiers" :key="d.name" :value="d.name">{{ '\u00a0\u00a0'.repeat(d.niveau - 1) }}{{ d.label }}</option>
					</select>
				</div>
			</div>
			<p v-if="nouveauDossier.error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ nouveauDossier.error }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="creerDossier">Créer le dossier</button>
			</template>
		</FormDialog>
		<AchatDialog v-if="commande" kind="commande" :fournisseur="commande.fournisseur" :lignes-initiales="commande.lignes" :depot="commande.depot" @close="commande = null" @created="onCommandeCreee" />
		<AppToast :message="notice" tone="success" @close="notice = ''" />
	</BureauShell>
</template>
