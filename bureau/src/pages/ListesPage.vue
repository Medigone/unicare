<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import LucideChevronRight from '~icons/lucide/chevron-right'
import LucideCombine from '~icons/lucide/combine'
import LucideFolder from '~icons/lucide/folder'
import LucideFolderInput from '~icons/lucide/folder-input'
import LucideFolderPlus from '~icons/lucide/folder-plus'
import LucidePencil from '~icons/lucide/pencil'
import LucidePlus from '~icons/lucide/plus'
import LucideSearch from '~icons/lucide/search'
import LucideTrash2 from '~icons/lucide/trash-2'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import DeplacerDialog from '@/components/DeplacerDialog.vue'
import FusionDialog from '@/components/FusionDialog.vue'
import { createValeur, deleteValeur, desactiverUnitesInutilisees, getDoublons, getListes, getValeurs, renameValeur, setUnite } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'
import { construireArbre, dansVue, detailLabel, dossiersPossibles, filtrerValeurs, lienFiches, MODULES, usagesLabel, vuesDe, type Doublon, type LigneArbre, type ListeCode, type ListeResume, type ListeValeur, type ValeurVue } from '@/lib/listes'

/**
 * Réglages › Listes de choix : les valeurs proposées par les listes déroulantes du bureau (raisons de perte,
 * catégories de clients et de fournisseurs, groupes d'articles, unités), rangées par module. Ajouter, renommer,
 * fusionner un doublon, supprimer une valeur inutilisée ; pour les unités, les retirer des listes. Catégories et
 * groupes sont des arbres : leurs valeurs se rangent dans des dossiers, qui ne se choisissent pas sur une fiche.
 * Selon les droits ERP.
 */
const props = defineProps<{ code?: string }>()
const router = useRouter()

const listes = ref<ListeResume[] | null>(null)
const valeurs = ref<ListeValeur[] | null>(null)
const error = ref('')
const actionError = ref('')
const notice = ref('')
const busy = ref(false)

const liste = computed(() => listes.value?.find((row) => row.code === props.code) ?? null)
const groupes = computed(() => MODULES.map((module) => ({ ...module, listes: (listes.value ?? []).filter((row) => row.module === module.key) })).filter((groupe) => groupe.listes.length))

async function loadListes() {
	try {
		listes.value = await getListes()
		error.value = ''
		if (!liste.value && listes.value.length) router.replace({ name: 'Liste', params: { code: listes.value[0].code } })
	} catch (e) {
		if (!listes.value) error.value = (e as Error).message
	}
}
async function loadValeurs() {
	if (!liste.value) return
	const code = liste.value.code
	try {
		const fresh = await getValeurs(code)
		if (liste.value?.code === code) valeurs.value = fresh
	} catch (e) {
		actionError.value = (e as Error).message
	}
	loadDoublons()
}
watch(liste, (next, prev) => {
	if (next?.code === prev?.code) return
	valeurs.value = null
	doublons.value = []
	recherche.value = ''
	editing.value = null
	nouveau.value = ''
	actionError.value = ''
	vue.value = next?.code === 'unites' ? 'proposees' : 'toutes'
	dossierAjout.value = ''
	for (const key of Object.keys(ouverts)) delete ouverts[key]
	loadValeurs()
})

const recherche = ref('')
const vue = ref<ValeurVue>('toutes')
const estUnites = computed(() => liste.value?.code === 'unites')
const vues = computed(() => (liste.value ? vuesDe(liste.value.code) : []))
const visibles = computed(() => filtrerValeurs(valeurs.value ?? [], recherche.value, vue.value))
const compte = (key: ValeurVue) => (valeurs.value ?? []).filter((row) => !row.dossier && dansVue(row, key)).length

// Arbre : dossiers ouverts, lignes à plat ; une liste simple donne une ligne par valeur.
const estArbre = computed(() => Boolean(liste.value?.arbre))
const ouverts = reactive<Record<string, boolean>>({})
const lignes = computed<LigneArbre[]>(() =>
	estArbre.value ? construireArbre(valeurs.value ?? [], ouverts, recherche.value, vue.value) : visibles.value.map((valeur) => ({ valeur, niveau: 1, ouvert: false, contenu: 0, enfants: 0, usagesTotal: valeur.usages })),
)
const nbVisibles = computed(() => lignes.value.filter((ligne) => !ligne.valeur.dossier).length)
const dossiers = computed(() => (estArbre.value ? dossiersPossibles(valeurs.value ?? []) : []))
const filtreActif = computed(() => Boolean(recherche.value.trim()) || vue.value !== 'toutes')
function toutOuvrir(ouvrir: boolean) {
	for (const key of Object.keys(ouverts)) delete ouverts[key]
	if (ouvrir) for (const row of valeurs.value ?? []) if (row.dossier) ouverts[row.name] = true
}
function ouvrirChemin(nom: string | null | undefined) {
	let courant = nom ?? null
	while (courant) {
		ouverts[courant] = true
		courant = valeurs.value?.find((row) => row.name === courant)?.parent ?? null
	}
}
const motFiches = computed(() => (estUnites.value ? 'fiches' : (liste.value?.lien.fiches ?? 'fiches')))
const maxUsages = computed(() => Math.max(1, ...(valeurs.value ?? []).map((row) => row.usages)))
const inutiliseesProposees = computed(() => (valeurs.value ?? []).filter((row) => row.actif && !row.usages).length)

// Doublons repérés par le serveur ; « Ignorer » est retenu dans ce navigateur.
const doublons = ref<Doublon[]>([])
const IGNORES = 'unicare.listes.doublons-ignores'
function ignores(): string[] {
	try {
		return JSON.parse(localStorage.getItem(IGNORES) || '[]')
	} catch {
		return []
	}
}
const cleDoublon = (code: string, paire: Doublon) => `${code}:${paire.source}>${paire.cible}`
const doublon = computed(() => doublons.value[0] ?? null)
async function loadDoublons() {
	const current = liste.value
	if (!current?.fusion || !current.droits.modifier) {
		doublons.value = []
		return
	}
	try {
		const vus = ignores()
		const fresh = await getDoublons(current.code)
		if (liste.value?.code === current.code) doublons.value = fresh.filter((paire) => !vus.includes(cleDoublon(current.code, paire)))
	} catch {
		doublons.value = []
	}
}
function ignorerDoublon() {
	const paire = doublon.value
	if (!paire || !liste.value) return
	try {
		localStorage.setItem(IGNORES, JSON.stringify([...ignores(), cleDoublon(liste.value.code, paire)]))
	} catch {
		// Sans stockage, la suggestion reviendra au prochain chargement.
	}
	doublons.value = doublons.value.slice(1)
}

async function run(action: () => Promise<ListeValeur[]>, message: string) {
	if (busy.value) return false
	busy.value = true
	actionError.value = ''
	try {
		valeurs.value = await action()
		notice.value = message
		loadListes()
		loadDoublons()
		return true
	} catch (e) {
		actionError.value = (e as Error).message
		await loadValeurs()
		return false
	} finally {
		busy.value = false
	}
}

// Ajout rapide en tête du tableau ; la valeur ajoutée s'éclaire.
const nouveau = ref('')
const nouveauInput = ref<HTMLInputElement | null>(null)
const dossierAjout = ref('')
const ajoutee = ref<string | null>(null)
async function ajouter() {
	const code = liste.value?.code as ListeCode
	const nom = nouveau.value.trim()
	if (!nom) return
	const dossier = estArbre.value ? dossierAjout.value || null : null
	if (await run(() => createValeur(code, nom, dossier), `« ${nom} » ajoutée${dossier ? ` dans « ${dossier} »` : ''}.`)) {
		nouveau.value = ''
		ajoutee.value = nom
		ouvrirChemin(dossier)
		if (!dansVue({ name: nom, modified: '', usages: 0, actif: true }, vue.value)) vue.value = estUnites.value ? 'proposees' : 'toutes'
	}
}

// Renommer en place.
const editing = ref<{ name: string; nom: string } | null>(null)
const editInput = ref<HTMLInputElement[] | HTMLInputElement | null>(null)
function peutRenommer(row: ListeValeur) {
	return Boolean(liste.value?.droits.modifier && (liste.value.droits.renommer_utilisee || !row.usages))
}
async function startRename(row: ListeValeur) {
	editing.value = { name: row.name, nom: row.name }
	await nextTick()
	const input = Array.isArray(editInput.value) ? editInput.value[0] : editInput.value
	input?.select()
}
async function confirmRename(row: ListeValeur) {
	const edit = editing.value
	if (!edit || !liste.value) return
	const nom = edit.nom.trim()
	if (!nom || nom === row.name) {
		editing.value = null
		return
	}
	const code = liste.value.code
	if (row.usages && !(await confirmAction({ title: 'Renommer', message: `« ${row.name} » devient « ${nom} » partout où elle est utilisée (${usagesLabel(row.usages, motFiches.value)}).`, confirmLabel: 'Renommer' }))) return
	if (await run(() => renameValeur(code, row, nom), `« ${row.name} » renommée en « ${nom} ».`)) editing.value = null
}
function onEditKey(event: KeyboardEvent, row: ListeValeur) {
	if (event.key === 'Enter') {
		event.preventDefault()
		confirmRename(row)
	} else if (event.key === 'Escape') {
		event.preventDefault()
		editing.value = null
	}
}

/** « + » d'un dossier : prépare l'ajout d'une valeur dedans. */
function ajouterDans(dossier: string) {
	dossierAjout.value = dossier
	ouvrirChemin(dossier)
	nouveauInput.value?.focus()
}

// Déplacer une valeur ou un dossier ; sans valeur, créer un dossier.
const rangement = ref<{ valeur: ListeValeur | null; dossier: string | null } | null>(null)
function onRangement(fresh: ListeValeur[], message: string) {
	const cible = rangement.value
	valeurs.value = fresh
	rangement.value = null
	notice.value = message
	const moved = cible?.valeur ? fresh.find((row) => row.name === cible.valeur!.name) : null
	ouvrirChemin(moved ? moved.parent : cible?.dossier)
	loadListes()
}

const peutFusionner = computed(() => Boolean(liste.value?.fusion && liste.value.droits.modifier && liste.value.droits.supprimer && (valeurs.value ?? []).filter((row) => !row.dossier).length > 1))
const fusion = ref<{ valeur: ListeValeur; cible: string | null } | null>(null)
function ouvrirFusion(row: ListeValeur, cible: string | null = null) {
	fusion.value = { valeur: row, cible }
}
function fusionDepuisDoublon() {
	const paire = doublon.value
	const row = valeurs.value?.find((item) => item.name === paire?.source)
	if (paire && row) ouvrirFusion(row, paire.cible)
}
function onFusion(fresh: ListeValeur[], cible: string) {
	const source = fusion.value?.valeur.name
	valeurs.value = fresh
	fusion.value = null
	notice.value = `« ${source} » fusionnée dans « ${cible} ».`
	loadListes()
	loadDoublons()
}

async function supprimer(row: ListeValeur) {
	const code = liste.value?.code as ListeCode
	if (!(await confirmAction({ title: 'Supprimer', message: `« ${row.name} » ne sera plus proposée.`, confirmLabel: 'Supprimer', danger: true }))) return
	await run(() => deleteValeur(code, row), `« ${row.name} » supprimée.`)
}

async function changerUnite(row: ListeValeur, changes: { actif?: boolean; entier?: boolean }) {
	const message = changes.actif === undefined ? `« ${row.name} » enregistrée.` : changes.actif ? `« ${row.name} » est de nouveau proposée.` : `« ${row.name} » n'est plus proposée.`
	await run(() => setUnite(row, changes), message)
}
async function nettoyerUnites() {
	const inutilisees = inutiliseesProposees.value
	if (!inutilisees) {
		notice.value = 'Toutes les unités proposées sont utilisées.'
		return
	}
	const ok = await confirmAction({
		title: 'Retirer les unités inutilisées',
		message: `${inutilisees} unité${inutilisees > 1 ? 's' : ''} qu'aucun article, prix ni recette n'utilise ne ser${inutilisees > 1 ? 'ont' : 'a'} plus proposée${inutilisees > 1 ? 's' : ''}. Vous pourrez en réactiver une à tout moment dans « Retirées ».`,
		confirmLabel: 'Retirer',
	})
	if (!ok) return
	await run(async () => {
		const reponse = await desactiverUnitesInutilisees()
		return reponse.valeurs
	}, `${inutilisees} unité${inutilisees > 1 ? 's' : ''} retirée${inutilisees > 1 ? 's' : ''} des listes.`)
}

onMounted(loadListes)
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Listes de choix' }]" active="listes">
		<div class="bureau-work tdb">
			<div>
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Listes de choix</h1>
				<p class="text-sm text-ink-gray-6">Les valeurs proposées par les listes déroulantes du bureau. Une valeur utilisée se renomme ou se fusionne partout, mais ne se supprime pas.</p>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!listes" class="card p-4 text-ink-gray-6">Chargement des listes…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<div v-if="listes" class="tarifs-layout">
				<nav class="card tarifs-liste" aria-labelledby="t-listes">
					<h2 id="t-listes" class="px-2.5 pt-1 text-base font-semibold">Listes</h2>
					<div v-for="groupe in groupes" :key="groupe.key" class="tarifs-groupe">
						<span class="px-2.5 text-xs font-semibold uppercase tracking-wide text-ink-gray-6">{{ groupe.label }}</span>
						<RouterLink v-for="row in groupe.listes" :key="row.code" :to="{ name: 'Liste', params: { code: row.code } }" class="tarif-item" :aria-current="row.code === code ? 'page' : undefined">
							<span class="font-medium">{{ row.label }}</span>
							<span class="flex flex-wrap items-center gap-1.5 text-xs tabular-nums text-ink-gray-6">
								{{ row.code === 'unites' ? `${row.actifs} proposée${(row.actifs ?? 0) > 1 ? 's' : ''}` : `${row.total} valeur${row.total > 1 ? 's' : ''}` }}
								<span v-if="row.inutilisees && (row.droits.supprimer || row.droits.modifier)" class="badge tone-amber">{{ row.inutilisees }} {{ row.code === 'unites' ? 'à retirer' : `inutilisée${row.inutilisees > 1 ? 's' : ''}` }}</span>
							</span>
						</RouterLink>
					</div>
				</nav>

				<section v-if="liste" class="card tarifs-detail" aria-labelledby="t-valeurs">
					<div class="tarifs-head">
						<div class="flex flex-wrap items-start gap-3">
							<div class="min-w-0 flex-[1_1_20rem]">
								<h2 id="t-valeurs" class="text-lg font-semibold">{{ liste.label }}</h2>
								<p class="text-sm text-ink-gray-6">{{ liste.aide }}<template v-if="estArbre"> Les <b class="font-semibold text-ink-gray-8">dossiers</b> rangent les valeurs : sur une fiche, on choisit une valeur, jamais un dossier.</template></p>
							</div>
							<div class="flex flex-wrap gap-1.5">
								<template v-if="estUnites">
									<span class="badge tone-green">{{ liste.actifs }} proposée{{ (liste.actifs ?? 0) > 1 ? 's' : '' }}</span>
									<span class="badge tone-gray">{{ liste.total - (liste.actifs ?? 0) }} retirée{{ liste.total - (liste.actifs ?? 0) > 1 ? 's' : '' }}</span>
								</template>
								<template v-else>
									<span v-if="estArbre && liste.dossiers" class="badge tone-gray">{{ liste.dossiers }} dossier{{ liste.dossiers > 1 ? 's' : '' }}</span>
									<span class="badge tone-gray">{{ liste.total }} valeur{{ liste.total > 1 ? 's' : '' }}</span>
									<span v-if="liste.fiches" class="badge tone-gray">{{ usagesLabel(liste.fiches, liste.lien.fiches) }} classé{{ liste.fiches > 1 ? 's' : '' }}</span>
								</template>
							</div>
						</div>
						<div v-if="doublon && peutFusionner" role="status" class="tarifs-bandeau tone-blue">
							<span class="flex-auto"><b>« {{ doublon.source }} »</b> ressemble à <b>« {{ doublon.cible }} »</b>. Fusionner reclasse {{ doublon.usages ? `ses ${usagesLabel(doublon.usages, liste.lien.fiches)}` : 'ses fiches' }} dans « {{ doublon.cible }} » puis supprime « {{ doublon.source }} ».</span>
							<button type="button" class="btn-secondary" :disabled="busy" @click="fusionDepuisDoublon">Fusionner…</button>
							<button type="button" class="btn-ghost" @click="ignorerDoublon">Ignorer</button>
						</div>
						<div v-if="estUnites && liste.droits.modifier && inutiliseesProposees" class="tarifs-bandeau tone-amber">
							<span class="flex-auto"><b>{{ inutiliseesProposees }} unité{{ inutiliseesProposees > 1 ? 's' : '' }} proposée{{ inutiliseesProposees > 1 ? 's' : '' }}</b> ne {{ inutiliseesProposees > 1 ? 'servent' : 'sert' }} à aucun article, prix ni recette. Les retirer allège toutes les listes déroulantes ; elles restent réactivables ici.</span>
							<button type="button" class="btn-secondary" :disabled="busy || !valeurs" @click="nettoyerUnites">Retirer les {{ inutiliseesProposees }} unités inutilisées</button>
						</div>
					</div>

					<div class="tarifs-outils pb-3">
						<form v-if="liste.droits.creer" class="flex min-w-0 flex-[1_1_18rem] flex-wrap gap-2" :class="!estArbre && 'sm:max-w-md'" @submit.prevent="ajouter">
							<input ref="nouveauInput" v-model="nouveau" class="field-input min-w-0 flex-[1_1_10rem]" :aria-label="`Nouvelle valeur pour ${liste.label}`" :placeholder="estUnites ? 'Nouvelle unité, ex. Palette' : 'Nouvelle valeur'" autocomplete="off" :disabled="busy" />
							<label v-if="estArbre" class="flex items-center gap-1.5 text-sm text-ink-gray-7">
								dans
								<select v-model="dossierAjout" class="field-input w-auto max-w-[14rem]" aria-label="Dossier de la nouvelle valeur">
									<option value="">la racine</option>
									<option v-for="dossier in dossiers" :key="dossier.name" :value="dossier.name">{{ '\u00a0\u00a0'.repeat(dossier.niveau - 1) }}{{ dossier.name }}</option>
								</select>
							</label>
							<button type="submit" class="btn-primary" :disabled="busy || !nouveau.trim()"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Ajouter</button>
							<button v-if="estArbre" type="button" class="btn-secondary" :disabled="busy" @click="rangement = { valeur: null, dossier: dossierAjout || null }"><LucideFolderPlus class="h-3.5 w-3.5" aria-hidden="true" />Nouveau dossier</button>
						</form>
						<p v-else-if="!liste.droits.modifier" class="field-note">Lecture seule pour votre rôle.</p>
						<span class="flex-auto"></span>
						<label class="bureau-search">
							<LucideSearch class="h-3.5 w-3.5" aria-hidden="true" />
							<input v-model="recherche" class="field-input" type="search" :aria-label="`Chercher dans ${liste.label}`" placeholder="Chercher" />
						</label>
						<template v-if="estArbre && !filtreActif">
							<button type="button" class="btn-ghost btn-sm" @click="toutOuvrir(true)">Tout déplier</button>
							<button type="button" class="btn-ghost btn-sm" @click="toutOuvrir(false)">Tout replier</button>
						</template>
						<div class="seg" role="group" aria-label="Afficher">
							<button v-for="item in vues" :key="item.key" type="button" :aria-pressed="vue === item.key" @click="vue = item.key">
								{{ item.label }}<span v-if="valeurs" class="ml-1 tabular-nums text-ink-gray-6">{{ compte(item.key) }}</span>
							</button>
						</div>
					</div>

					<p v-if="!valeurs" class="px-4 pb-4 text-ink-gray-6">Chargement…</p>
					<p v-else-if="!valeurs.length" class="px-4 pb-4 text-ink-gray-6">Aucune valeur : ajoutez-en une pour qu'elle soit proposée.</p>
					<p v-else-if="filtreActif && !nbVisibles" class="px-4 pb-4 text-ink-gray-6">Aucune valeur ne correspond.</p>
					<div v-else class="overflow-x-auto border-t border-[var(--line-soft)]">
						<table class="ref-table tarifs-table listes-table">
							<thead>
								<tr>
									<th>{{ estUnites ? 'Unité' : estArbre ? 'Nom' : 'Valeur' }}</th>
									<th>Utilisée par</th>
									<template v-if="estUnites"><th>Quantités</th><th>Proposée</th></template>
									<th><span class="sr-only">Actions</span></th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="ligne in lignes" :key="ligne.valeur.name" :class="[ajoutee === ligne.valeur.name && 'devis-line-new', !ligne.valeur.actif && 'text-ink-gray-6', editing?.name === ligne.valeur.name && 'tarifs-ouvert', ligne.valeur.dossier && 'listes-dossier', estUnites && ligne.valeur.actif && !ligne.valeur.usages && 'tarifs-sans-prix']" :aria-level="estArbre ? ligne.niveau : undefined">
									<td>
										<div class="flex items-center gap-1.5" :style="estArbre ? { paddingLeft: `${(ligne.niveau - 1) * 1.5}rem` } : undefined">
											<template v-if="estArbre">
												<button v-if="ligne.valeur.dossier" type="button" class="app-icon-bare flex-none" :aria-expanded="ligne.ouvert" :aria-label="`${ligne.ouvert ? 'Replier' : 'Déplier'} ${ligne.valeur.name}`" :disabled="filtreActif" @click="ouverts[ligne.valeur.name] = !ligne.ouvert">
													<LucideChevronRight class="h-3.5 w-3.5 transition-transform" :class="ligne.ouvert && 'rotate-90'" aria-hidden="true" />
												</button>
												<span v-else class="listes-puce" aria-hidden="true"></span>
												<LucideFolder v-if="ligne.valeur.dossier" class="h-4 w-4 flex-none text-[var(--accent)]" aria-hidden="true" />
											</template>
											<div v-if="editing?.name === ligne.valeur.name" class="flex flex-wrap items-center gap-2">
												<input ref="editInput" v-model="editing.nom" class="field-input max-w-xs" :aria-label="`Nouveau nom pour ${ligne.valeur.name}`" :disabled="busy" @keydown="onEditKey($event, ligne.valeur)" @blur="confirmRename(ligne.valeur)" />
												<span class="text-xs text-ink-gray-6">Entrée pour renommer{{ ligne.valeur.usages ? ` sur ${usagesLabel(ligne.valeur.usages, motFiches)}` : '' }} · Échap annule</span>
											</div>
											<template v-else>
												<span :class="[ligne.valeur.dossier ? 'font-semibold' : 'font-medium', ligne.valeur.actif ? 'text-ink-gray-9' : 'text-ink-gray-6']">{{ ligne.valeur.name }}</span>
												<span v-if="ligne.valeur.dossier" class="text-xs text-ink-gray-6">{{ ligne.enfants ? `${ligne.contenu} valeur${ligne.contenu > 1 ? 's' : ''}` : 'vide' }}</span>
												<span v-if="ajoutee === ligne.valeur.name" class="badge tone-green">ajoutée</span>
											</template>
										</div>
									</td>
									<td>
										<template v-if="ligne.valeur.dossier">
											<span class="text-ink-gray-7">{{ ligne.usagesTotal ? `${usagesLabel(ligne.usagesTotal, liste.lien.fiches)} au total` : '—' }}</span>
										</template>
										<template v-else-if="ligne.valeur.usages">
											<div class="flex items-center gap-2.5">
												<span v-if="!estUnites" class="tarif-bar listes-bar" aria-hidden="true"><span :style="{ width: `${Math.max(3, Math.round((ligne.valeur.usages * 100) / maxUsages))}%` }"></span></span>
												<RouterLink v-if="!estUnites" :to="lienFiches(liste, ligne.valeur.name)" class="font-medium">{{ usagesLabel(ligne.valeur.usages, liste.lien.fiches) }}</RouterLink>
												<span v-else class="font-medium text-ink-gray-8">{{ usagesLabel(ligne.valeur.usages) }}</span>
											</div>
											<small v-if="estUnites && detailLabel(ligne.valeur.detail)" class="block text-ink-gray-6">{{ detailLabel(ligne.valeur.detail) }}</small>
										</template>
										<span v-else class="text-ink-gray-6">Inutilisée</span>
									</td>
									<template v-if="estUnites">
										<td>
											<label class="flex items-center gap-2 text-sm">
												<input type="checkbox" role="switch" class="table-panel-switch" :checked="ligne.valeur.entier" :disabled="!liste.droits.modifier || busy" :aria-label="`${ligne.valeur.name} : quantités entières seulement`" @change="changerUnite(ligne.valeur, { entier: ($event.target as HTMLInputElement).checked })" />
												{{ ligne.valeur.entier ? 'Entières' : 'Décimales' }}
											</label>
										</td>
										<td>
											<label class="flex items-center gap-2 text-sm">
												<input type="checkbox" role="switch" class="table-panel-switch" :checked="ligne.valeur.actif" :disabled="!liste.droits.modifier || busy" :aria-label="`Proposer ${ligne.valeur.name} dans les listes`" @change="changerUnite(ligne.valeur, { actif: ($event.target as HTMLInputElement).checked })" />
												{{ ligne.valeur.actif ? 'Proposée' : 'Retirée' }}
											</label>
										</td>
									</template>
									<td class="whitespace-nowrap text-right">
										<button v-if="ligne.valeur.dossier && liste.droits.creer" type="button" class="app-icon-bare" :disabled="busy" :aria-label="`Ajouter une valeur dans ${ligne.valeur.name}`" title="Ajouter une valeur dans ce dossier" @click="ajouterDans(ligne.valeur.name)"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" /></button>
										<button v-if="peutRenommer(ligne.valeur) && editing?.name !== ligne.valeur.name" type="button" class="app-icon-bare" :disabled="busy" :aria-label="`Renommer ${ligne.valeur.name}`" title="Renommer" @click="startRename(ligne.valeur)"><LucidePencil class="h-3.5 w-3.5" aria-hidden="true" /></button>
										<button v-if="estArbre && liste.droits.modifier" type="button" class="app-icon-bare" :disabled="busy" :aria-label="`Déplacer ${ligne.valeur.name}`" title="Déplacer dans un autre dossier" @click="rangement = { valeur: ligne.valeur, dossier: null }"><LucideFolderInput class="h-3.5 w-3.5" aria-hidden="true" /></button>
										<button v-if="peutFusionner && !ligne.valeur.dossier" type="button" class="app-icon-bare" :disabled="busy" :aria-label="`Fusionner ${ligne.valeur.name} dans une autre valeur`" title="Fusionner dans une autre valeur" @click="ouvrirFusion(ligne.valeur)"><LucideCombine class="h-3.5 w-3.5" aria-hidden="true" /></button>
										<button
											v-if="liste.droits.supprimer"
											type="button"
											class="app-icon-bare text-tone-red"
											:disabled="busy || ligne.valeur.usages > 0 || ligne.enfants > 0"
											:aria-label="`Supprimer ${ligne.valeur.name}`"
											:title="ligne.enfants ? 'Un dossier se supprime seulement vide' : ligne.valeur.usages ? (estUnites ? 'Utilisée : retirez-la des listes plutôt' : `Utilisée par ${usagesLabel(ligne.valeur.usages, liste.lien.fiches)} : fusionnez-la plutôt`) : 'Supprimer'"
											@click="supprimer(ligne.valeur)"
										>
											<LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" />
										</button>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
					<p class="field-note px-4 py-3">
						<template v-if="estUnites">« Entières » : la quantité doit être un nombre entier (pièces, cartons, flacons). Une unité retirée reste sur les fiches qui l'ont déjà, mais n'est plus proposée.</template>
						<template v-else>Une valeur utilisée ne se supprime pas : renommez-la, ou fusionnez-la dans une autre pour reclasser ses fiches.<template v-if="estArbre"> Un dossier se supprime seulement vide ; déplacer une valeur ne change rien aux fiches qui l'utilisent.</template></template>
					</p>
				</section>
			</div>
		</div>
		<DeplacerDialog v-if="rangement && liste && valeurs" :liste="liste" :valeurs="valeurs" :valeur="rangement.valeur" :dossier="rangement.dossier" @close="rangement = null" @done="onRangement" />
		<FusionDialog v-if="fusion && liste && valeurs" :liste="liste" :valeur="fusion.valeur" :valeurs="valeurs" :cible="fusion.cible" @close="fusion = null" @done="onFusion" />
		<AppToast :message="notice" tone="success" @close="notice = ''" />
	</BureauShell>
</template>
