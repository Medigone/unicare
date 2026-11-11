<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideArrowDown from '~icons/lucide/arrow-down'
import LucideArrowUp from '~icons/lucide/arrow-up'
import LucidePlus from '~icons/lucide/plus'
import LucideTrash2 from '~icons/lucide/trash-2'
import { closeRealtime, connectRealtime, isForeignChange, throttledReload, type RealtimeEvent } from '@shared/realtime'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import { deleteChecklist, getReglagesProduction, saveChecklist, saveParametresProduction } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'
import { DEPOT_FIELDS, moveLine, type ChecklistLigne, type DepotField, type ReglagesProduction } from '@/lib/reglages'
import { parseQty } from '@/lib/ordres'

/**
 * Réglages de la production : les checklists avant production (modèles copiés dans chaque nouvel ordre) et les
 * paramètres (dépôts par défaut, écart de rendement toléré). Lecture seule pour qui n'a pas le droit d'écrire.
 */
const reglages = ref<ReglagesProduction | null>(null)
const error = ref('')
const actionError = ref('')
const notice = ref('')
const busy = ref(false)

async function load() {
	try {
		apply(await getReglagesProduction())
		error.value = ''
	} catch (e) {
		if (!reglages.value) error.value = (e as Error).message
	}
}

// Checklist ouverte et sa copie de travail ; `nouvelle` : une checklist pas encore créée.
const selected = ref<string | null>(null)
const draft = ref<{ titre: string; actif: boolean; lignes: ChecklistLigne[] }>({ titre: '', actif: true, lignes: [] })
const nouvelle = ref(false)
// Modifié : la copie de travail diffère de ce qui a été chargé.
const draftBase = ref('')
const checklistDirty = computed(() => JSON.stringify(draft.value) !== draftBase.value)
const current = computed(() => reglages.value?.checklists.find((row) => row.name === selected.value) ?? null)
function openChecklist(name: string | null) {
	nouvelle.value = false
	selected.value = name
	const row = reglages.value?.checklists.find((item) => item.name === name)
	draft.value = { titre: row?.name ?? '', actif: row?.actif ?? true, lignes: (row?.lignes ?? []).map((line) => ({ ...line })) }
	draftBase.value = JSON.stringify(draft.value)
}
function startNew() {
	nouvelle.value = true
	selected.value = null
	draft.value = { titre: '', actif: true, lignes: [{ controle: '', obligatoire: true }] }
	draftBase.value = JSON.stringify(draft.value)
}

// Paramètres : copie de travail.
const parametres = ref<Record<DepotField, string> & { tolerance: string }>({ warehouse_mp: '', warehouse_conditionnement: '', warehouse_atelier: '', warehouse_pf: '', warehouse_rebuts: '', tolerance: '' })
const parametresBase = ref('')
const parametresDirty = computed(() => JSON.stringify(parametres.value) !== parametresBase.value)

function apply(fresh: ReglagesProduction) {
	reglages.value = fresh
	if (!checklistDirty.value && !nouvelle.value) openChecklist(fresh.checklists.some((row) => row.name === selected.value) ? selected.value : fresh.checklists[0]?.name ?? null)
	if (!parametresDirty.value) {
		const p = fresh.parametres
		parametres.value = {
			warehouse_mp: p.warehouse_mp ?? '',
			warehouse_conditionnement: p.warehouse_conditionnement ?? '',
			warehouse_atelier: p.warehouse_atelier ?? '',
			warehouse_pf: p.warehouse_pf ?? '',
			warehouse_rebuts: p.warehouse_rebuts ?? '',
			tolerance: String(p.tolerance).replace('.', ','),
		}
		parametresBase.value = JSON.stringify(parametres.value)
	}
}

const canChecklist = computed(() => (nouvelle.value ? reglages.value?.can_create_checklists : reglages.value?.can_edit_checklists) ?? false)

async function run(action: () => Promise<ReglagesProduction>, message: string, after?: () => void) {
	if (busy.value) return
	busy.value = true
	actionError.value = ''
	try {
		const fresh = await action()
		after?.()
		apply(fresh)
		notice.value = message
	} catch (e) {
		actionError.value = (e as Error).message
		await load()
	} finally {
		busy.value = false
	}
}
async function saveCurrentChecklist() {
	const lignes = draft.value.lignes.filter((line) => line.controle.trim())
	if (nouvelle.value && !draft.value.titre.trim()) {
		actionError.value = 'Donnez un nom à la checklist.'
		return
	}
	if (!lignes.length) {
		actionError.value = 'Une checklist doit avoir au moins un contrôle.'
		return
	}
	const target = nouvelle.value ? {} : { name: current.value?.name, modified: current.value?.modified }
	const titre = draft.value.titre.trim()
	await run(
		() => saveChecklist(target, { titre: nouvelle.value ? titre : undefined, actif: draft.value.actif, lignes }),
		nouvelle.value ? 'Checklist créée.' : 'Checklist enregistrée. Les nouveaux ordres recevront ces contrôles.',
		() => {
			draftBase.value = JSON.stringify(draft.value)
			if (nouvelle.value) {
				nouvelle.value = false
				selected.value = titre
			}
		},
	)
}
async function removeChecklist() {
	const row = current.value
	if (!row) return
	if (!(await confirmAction({ title: 'Supprimer la checklist', message: `La checklist « ${row.name} » sera supprimée définitivement.`, confirmLabel: 'Supprimer', danger: true }))) return
	await run(() => deleteChecklist(row), 'Checklist supprimée.', () => {
		draftBase.value = JSON.stringify(draft.value)
		selected.value = null
	})
}
async function saveParametres() {
	const tolerance = parseQty(parametres.value.tolerance)
	if (!(tolerance > 0 && tolerance <= 100)) {
		actionError.value = "L'écart toléré est un pourcentage entre 1 et 100."
		return
	}
	const modified = reglages.value?.parametres.modified ?? ''
	await run(() => saveParametresProduction(modified, { ...parametres.value, tolerance }), 'Paramètres enregistrés.', () => (parametresBase.value = JSON.stringify(parametres.value)))
}

const reload = throttledReload(load, { delayMs: 1000, minIntervalMs: 4000 })
onMounted(() => {
	load()
	connectRealtime<RealtimeEvent>(
		'unicare_bureau_update',
		(event) => {
			if (isForeignChange(event, window.user) && event.doctype === 'Checklist Ordre Conditionnement') reload()
		},
		load,
	)
})
onBeforeUnmount(closeRealtime)
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Checklists et paramètres' }]" active="reglages-production">
		<div class="bureau-work tdb">
			<div>
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Réglages de la production</h1>
				<p class="text-sm text-ink-gray-6">Modifiables par le Responsable Conditionnement ; les autres rôles les voient en lecture seule.</p>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!reglages" class="card p-4 text-ink-gray-6">Chargement des réglages…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<div v-if="reglages" class="reglages-grid">
				<section class="card reglages-card" aria-labelledby="t-checklists">
					<div class="flex items-center gap-2">
						<h2 id="t-checklists" class="flex-auto text-base font-semibold">Checklists avant production</h2>
						<button v-if="reglages.can_create_checklists" type="button" class="btn-secondary" :disabled="busy" @click="startNew"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Nouvelle checklist</button>
					</div>
					<p class="text-sm text-ink-gray-6">Les contrôles à cocher avant d'envoyer les matières à l'atelier. Chaque ordre en reçoit une copie à sa création.</p>
					<div class="flex flex-wrap gap-1.5" role="group" aria-label="Checklists">
						<button v-for="row in reglages.checklists" :key="row.name" type="button" class="reglages-tab" :aria-pressed="!nouvelle && selected === row.name" @click="openChecklist(row.name)">
							{{ row.name }}<span v-if="!row.actif" class="text-xs text-ink-gray-6"> · inactive</span>
						</button>
						<span v-if="nouvelle" class="reglages-tab" aria-pressed="true">Nouvelle checklist</span>
					</div>

					<template v-if="nouvelle || current">
						<div v-if="nouvelle" class="form-field">
							<label class="field-label" for="checklist-titre">Nom de la checklist <span class="req">obligatoire</span></label>
							<input id="checklist-titre" v-model="draft.titre" class="field-input" placeholder="Ex. Ligne flacons 250 ml" />
						</div>
						<div class="reglages-lines">
							<div class="reglages-line reglages-line-head"><span class="flex-auto">Contrôle</span><span class="w-24">Obligatoire</span><span class="w-[92px]"></span></div>
							<div v-for="(line, index) in draft.lignes" :key="index" class="reglages-line">
								<input v-model="line.controle" class="field-input flex-auto" :disabled="!canChecklist" :aria-label="`Contrôle ${index + 1}`" />
								<label class="flex w-24 items-center gap-1.5 text-sm"><input v-model="line.obligatoire" type="checkbox" :disabled="!canChecklist" /> oui</label>
								<span v-if="canChecklist" class="flex w-[92px] gap-0.5">
									<button type="button" class="icon-btn" :disabled="index === 0" :aria-label="`Monter le contrôle ${index + 1}`" @click="draft.lignes = moveLine(draft.lignes, index, -1)"><LucideArrowUp class="h-3.5 w-3.5" aria-hidden="true" /></button>
									<button type="button" class="icon-btn" :disabled="index === draft.lignes.length - 1" :aria-label="`Descendre le contrôle ${index + 1}`" @click="draft.lignes = moveLine(draft.lignes, index, 1)"><LucideArrowDown class="h-3.5 w-3.5" aria-hidden="true" /></button>
									<button type="button" class="icon-btn" :disabled="draft.lignes.length === 1" :aria-label="`Retirer le contrôle ${index + 1}`" @click="draft.lignes.splice(index, 1)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button>
								</span>
							</div>
						</div>
						<div class="flex flex-wrap items-center gap-2.5">
							<button v-if="canChecklist" type="button" class="btn-secondary" @click="draft.lignes.push({ controle: '', obligatoire: true })"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Ajouter un contrôle</button>
							<label class="flex items-center gap-1.5 text-sm"><input v-model="draft.actif" type="checkbox" :disabled="!canChecklist" /> Active (proposée pour les nouveaux ordres)</label>
							<span class="flex-auto"></span>
							<span v-if="current && current.ordres" class="text-xs text-ink-gray-6">reprise par {{ current.ordres }} ordre{{ current.ordres > 1 ? 's' : '' }}</span>
							<button v-if="current && !current.ordres && reglages.can_edit_checklists && !nouvelle" type="button" class="btn-ghost text-tone-red" :disabled="busy" @click="removeChecklist">Supprimer</button>
							<button v-if="nouvelle" type="button" class="btn-ghost" :disabled="busy" @click="openChecklist(reglages.checklists[0]?.name ?? null)">Annuler</button>
							<button v-if="canChecklist" type="button" class="btn-primary" :disabled="busy || (!checklistDirty && !nouvelle)" @click="saveCurrentChecklist">{{ nouvelle ? 'Créer la checklist' : 'Enregistrer' }}</button>
						</div>
					</template>
					<p v-else class="text-ink-gray-6">Aucune checklist : créez-en une pour pouvoir préparer des ordres.</p>
				</section>

				<section class="card reglages-card" aria-labelledby="t-parametres">
					<div>
						<h2 id="t-parametres" class="text-base font-semibold">Dépôts utilisés par défaut</h2>
						<p class="text-sm text-ink-gray-6">Repris à chaque nouvel ordre ; modifiables ordre par ordre.</p>
					</div>
					<div class="form-grid">
						<div v-for="field in DEPOT_FIELDS" :key="field.key" class="form-field">
							<label class="field-label" :for="`param-${field.key}`">{{ field.label }}</label>
							<select :id="`param-${field.key}`" v-model="parametres[field.key]" class="field-input" :disabled="!reglages.can_edit_parametres">
								<option value="">—</option>
								<option v-if="parametres[field.key] && !reglages.depots.includes(parametres[field.key])" :value="parametres[field.key]">{{ parametres[field.key] }}</option>
								<option v-for="depot in reglages.depots" :key="depot" :value="depot">{{ depot }}</option>
							</select>
							<p v-if="field.help" class="field-note">{{ field.help }}</p>
						</div>
					</div>
					<div class="border-t border-[var(--line-soft)] pt-3.5">
						<h2 class="text-base font-semibold">Rendement</h2>
						<div class="mt-2 flex items-center gap-2">
							<label for="param-tolerance" class="text-sm font-semibold">Écart toléré</label>
							<span class="text-sm">±</span>
							<input id="param-tolerance" v-model="parametres.tolerance" class="field-input w-20 text-right tabular-nums" inputmode="decimal" :disabled="!reglages.can_edit_parametres" />
							<span class="text-sm">%</span>
						</div>
						<p class="field-note">Au-delà, la clôture demande une explication et l'ordre apparaît dans « Rendements hors tolérance » du tableau de bord.</p>
					</div>
					<div v-if="reglages.can_edit_parametres" class="flex justify-end"><button type="button" class="btn-primary" :disabled="busy || !parametresDirty" @click="saveParametres">Enregistrer</button></div>
				</section>
			</div>
		</div>
		<AppToast :message="notice" tone="success" @close="notice = ''" />
	</BureauShell>
</template>
