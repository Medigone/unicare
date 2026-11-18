<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import LucidePlus from '~icons/lucide/plus'
import LucideSearch from '~icons/lucide/search'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import { createValeur, deleteValeur, desactiverUnitesInutilisees, getListes, getValeurs, renameValeur, setUnite } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'
import { filtrerValeurs, usagesLabel, type ListeCode, type ListeResume, type ListeValeur, type UniteVue } from '@/lib/listes'

/**
 * Réglages › Listes de choix : les valeurs proposées par les listes déroulantes du bureau (raisons de perte,
 * catégories de clients et de fournisseurs, groupes d'articles, unités). Ajouter, renommer, supprimer une valeur
 * inutilisée ; pour les unités, les retirer des listes. Selon les droits ERP du rôle.
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
}
watch(liste, (next, prev) => {
	if (next?.code === prev?.code) return
	valeurs.value = null
	recherche.value = ''
	editing.value = null
	nouveau.value = ''
	actionError.value = ''
	loadValeurs()
})

const recherche = ref('')
const vue = ref<UniteVue>('actives')
const estUnites = computed(() => liste.value?.code === 'unites')
const visibles = computed(() => filtrerValeurs(valeurs.value ?? [], recherche.value, estUnites.value ? vue.value : undefined))

async function run(action: () => Promise<ListeValeur[]>, message: string) {
	if (busy.value) return false
	busy.value = true
	actionError.value = ''
	try {
		valeurs.value = await action()
		notice.value = message
		loadListes()
		return true
	} catch (e) {
		actionError.value = (e as Error).message
		await loadValeurs()
		return false
	} finally {
		busy.value = false
	}
}

// Ajout rapide en tête du tableau.
const nouveau = ref('')
async function ajouter() {
	const code = liste.value?.code as ListeCode
	const nom = nouveau.value.trim()
	if (!nom) return
	if (await run(() => createValeur(code, nom), `« ${nom} » ajoutée.`)) nouveau.value = ''
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
	if (row.usages && !(await confirmAction({ title: 'Renommer', message: `« ${row.name} » devient « ${nom} » sur les ${row.usages} fiches qui l'utilisent.`, confirmLabel: 'Renommer' }))) return
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
	const inutilisees = (valeurs.value ?? []).filter((row) => row.actif && !row.usages).length
	if (!inutilisees) {
		notice.value = 'Toutes les unités proposées sont utilisées.'
		return
	}
	const ok = await confirmAction({
		title: 'Retirer les unités inutilisées',
		message: `${inutilisees} unité${inutilisees > 1 ? 's' : ''} qu'aucun article, prix ni recette n'utilise ne ser${inutilisees > 1 ? 'ont' : 'a'} plus proposée${inutilisees > 1 ? 's' : ''}. Vous pourrez en réactiver une à tout moment dans « Toutes ».`,
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
	<BureauShell :crumbs="[{ label: 'Réglages' }, { label: 'Listes de choix' }]" active="listes">
		<div class="bureau-work tdb">
			<div>
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Listes de choix</h1>
				<p class="text-sm text-ink-gray-6">Les valeurs proposées par les listes déroulantes du bureau. Une valeur utilisée se renomme partout, mais ne se supprime pas.</p>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!listes" class="card p-4 text-ink-gray-6">Chargement des listes…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<section v-if="listes" class="card reglages-card" aria-labelledby="t-listes">
				<h2 id="t-listes" class="sr-only">Listes</h2>
				<div class="flex flex-wrap gap-1.5" role="group" aria-label="Listes">
					<RouterLink v-for="row in listes" :key="row.code" :to="{ name: 'Liste', params: { code: row.code } }" class="reglages-tab" :aria-current="row.code === code ? 'page' : undefined">
						{{ row.label }}<span class="text-xs tabular-nums text-ink-gray-6"> {{ row.actifs ?? row.total }}</span>
					</RouterLink>
				</div>
			</section>

			<section v-if="liste" class="card reglages-card" aria-labelledby="t-valeurs">
				<div>
					<h2 id="t-valeurs" class="text-base font-semibold">{{ liste.label }}</h2>
					<p class="text-sm text-ink-gray-6">{{ liste.aide }}</p>
				</div>
				<div class="flex flex-wrap items-center gap-2">
					<label class="bureau-search">
						<LucideSearch class="h-3.5 w-3.5" aria-hidden="true" />
						<input v-model="recherche" class="field-input" type="search" :aria-label="`Chercher dans ${liste.label}`" placeholder="Chercher" />
					</label>
					<div v-if="estUnites" class="seg" role="group" aria-label="Afficher">
						<button type="button" :aria-pressed="vue === 'actives'" @click="vue = 'actives'">Proposées</button>
						<button type="button" :aria-pressed="vue === 'toutes'" @click="vue = 'toutes'">Toutes</button>
					</div>
					<span class="flex-auto"></span>
					<button v-if="estUnites && liste.droits.modifier" type="button" class="btn-secondary" :disabled="busy || !valeurs" @click="nettoyerUnites">Retirer les unités inutilisées</button>
				</div>
				<form v-if="liste.droits.creer" class="flex flex-wrap items-center gap-2" @submit.prevent="ajouter">
					<input v-model="nouveau" class="field-input max-w-sm flex-auto" :aria-label="`Nouvelle valeur pour ${liste.label}`" placeholder="Nouvelle valeur" autocomplete="off" :disabled="busy" />
					<button type="submit" class="btn-secondary" :disabled="busy || !nouveau.trim()"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Ajouter</button>
				</form>
				<p v-if="!liste.droits.creer && !liste.droits.modifier" class="field-note">Lecture seule pour votre rôle.</p>

				<p v-if="!valeurs" class="text-ink-gray-6">Chargement…</p>
				<p v-else-if="!valeurs.length" class="text-ink-gray-6">Aucune valeur : ajoutez-en une pour qu'elle soit proposée.</p>
				<p v-else-if="!visibles.length" class="text-ink-gray-6">Aucune valeur ne correspond.</p>
				<div v-else class="overflow-x-auto">
					<table class="ref-table compta-table">
						<thead>
							<tr>
								<th>Valeur</th>
								<th>Utilisée par</th>
								<template v-if="estUnites"><th>Proposée</th><th>Entière</th></template>
								<th><span class="sr-only">Actions</span></th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="row in visibles" :key="row.name" :class="!row.actif && 'text-ink-gray-5'">
								<td>
									<input v-if="editing?.name === row.name" ref="editInput" v-model="editing.nom" class="field-input max-w-xs" :aria-label="`Nouveau nom pour ${row.name}`" :disabled="busy" @keydown="onEditKey($event, row)" @blur="confirmRename(row)" />
									<span v-else>{{ row.name }}</span>
								</td>
								<td class="text-sm" :class="!row.usages && 'text-ink-gray-6'">{{ usagesLabel(row.usages) }}</td>
								<template v-if="estUnites">
									<td><input type="checkbox" :checked="row.actif" :disabled="!liste.droits.modifier || busy" :aria-label="`Proposer ${row.name}`" @change="changerUnite(row, { actif: ($event.target as HTMLInputElement).checked })" /></td>
									<td><input type="checkbox" :checked="row.entier" :disabled="!liste.droits.modifier || busy" :aria-label="`${row.name} : quantités entières seulement`" @change="changerUnite(row, { entier: ($event.target as HTMLInputElement).checked })" /></td>
								</template>
								<td class="whitespace-nowrap text-right">
									<button v-if="peutRenommer(row) && editing?.name !== row.name" type="button" class="btn-ghost" :disabled="busy" @click="startRename(row)">Renommer</button>
									<button v-if="liste.droits.supprimer && !row.usages" type="button" class="btn-ghost text-tone-red" :disabled="busy" @click="supprimer(row)">Supprimer</button>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
				<p v-if="estUnites" class="field-note">« Entière » : la quantité doit être un nombre entier (pièces, cartons). Une unité retirée reste sur les fiches qui l'ont déjà.</p>
			</section>
		</div>
		<AppToast :message="notice" tone="success" @close="notice = ''" />
	</BureauShell>
</template>
