<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import OrdreDialog from './OrdreDialog.vue'
import RecetteDialog from './RecetteDialog.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import { deleteRecette, dupliquerRecette, recetteActivity, setRecetteActive } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { confirmAction } from '@/lib/confirm'
import { deskUrl, formatDay } from '@/lib/display'
import { ETAPE_TONES, parseQty } from '@/lib/ordres'
import { besoinsPour, type RecetteDetail } from '@/lib/recettes'
import { useRecette } from '@/lib/useRecette'

/** Fiche d'une recette : ses matières, un petit calculateur des besoins et les ordres qui l'utilisent. */
const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: []; deleted: [] }>()

const { recette, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useRecette(
	() => props.id,
	() => emit('changed'),
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => recetteActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, recette })

const can = (action: string) => Boolean(recette.value?.actions.includes(action as never))
const pct = (value: number) => `${String(value).replace('.', ',')} %`

// Calculateur : « combien faut-il pour… ».
const pour = ref('1000')
const besoins = computed(() => (recette.value ? besoinsPour(recette.value, parseQty(pour.value)) : []))

const editing = ref(false)
const ordering = ref(false)
function onSaved(fresh: RecetteDetail) {
	recette.value = fresh
	notice.value = 'Recette enregistrée.'
	emit('changed')
}
async function toggleActive() {
	const current = recette.value
	if (!current) return
	const actif = !current.actif
	if (!(await confirmAction({
		title: actif ? 'Activer la recette' : 'Rendre la recette inactive',
		message: actif ? `La recette sera de nouveau proposée pour les nouveaux ordres de ${current.designation}.` : `La recette ne sera plus proposée pour les nouveaux ordres. Les ordres déjà créés ne changent pas.`,
		confirmLabel: actif ? 'Activer' : 'Rendre inactive',
	}))) return
	if (await perform(() => setRecetteActive(current, actif))) notice.value = actif ? 'Recette active.' : 'Recette inactive.'
}

const router = useRouter()
async function dupliquer() {
	const current = recette.value
	if (!current) return
	if (!(await confirmAction({ title: 'Dupliquer la recette', message: `Une copie de ${current.name} sera créée, active, pour préparer une variante ou une nouvelle version.`, confirmLabel: 'Dupliquer' }))) return
	busy.value = true
	try {
		const created = await dupliquerRecette(current)
		emit('changed')
		await router.push({ name: 'RecetteFiche', params: { id: created.name } })
		notice.value = `Recette ${created.name} créée.`
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
async function supprimer() {
	const current = recette.value
	if (!current) return
	if (!(await confirmAction({ title: 'Supprimer la recette', message: `La recette ${current.name} sera supprimée définitivement.`, confirmLabel: 'Supprimer', danger: true }))) return
	busy.value = true
	try {
		await deleteRecette(current)
		emit('deleted')
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
function onOrdre(name: string) {
	router.push({ name: 'OrdreFiche', params: { id: name } })
}
async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}
</script>

<template>
	<main class="bureau-main">
		<div v-if="error" role="alert" class="card p-3.5 text-tone-red">
			{{ error }}
			<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
		</div>
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Cette recette n'existe pas ou n'existe plus.</div>
		<div v-else-if="!recette" class="card p-8 text-center text-ink-gray-6">Chargement de la recette…</div>

		<template v-else>
			<RecordHeader>
				<template #title>{{ recette.designation }}</template>
				<template #flags><StatusPill :status="recette.actif ? 'Active' : 'Inactive'" :tone="recette.actif ? 'green' : 'gray'" /></template>
				<template #sub>
					<span class="tabular-nums">{{ recette.name }}</span>
					<RouterLink class="ref-link" :to="{ name: 'Article', params: { id: recette.produit } }">{{ recette.produit }}</RouterLink>
					<div><TagEditor doctype="Recette de Conditionnement" :name="recette.name" :modified="recette.modified" :tags="recette.tags" :can-edit="true" @changed="(tags) => (recette!.tags = tags)" /></div>
				</template>
				<template #actions>
					<button v-if="can('nouvel_ordre')" type="button" class="btn-secondary" :disabled="busy" @click="ordering = true">Nouvel ordre</button>
					<button v-if="can('modifier')" type="button" class="btn-primary" :disabled="busy" @click="editing = true">Modifier</button>
					<MoreMenu>
						<button v-if="can('dupliquer')" type="button" class="app-menu-item" role="menuitem" @click="dupliquer">Dupliquer</button>
						<button v-if="can('activer') || can('desactiver')" type="button" class="app-menu-item" role="menuitem" @click="toggleActive">{{ recette.actif ? 'Rendre inactive' : 'Activer' }}</button>
						<div class="app-menu-sep"></div>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Recette de Conditionnement', recette.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="can('supprimer')">
							<div class="app-menu-sep"></div>
							<button type="button" class="app-menu-item text-tone-red" role="menuitem" @click="supprimer">Supprimer la recette</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>
			<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<div class="bureau-detail">
				<div class="bureau-center">
					<section class="card ordre-kpis recette-kpis" aria-label="En bref">
						<div><span>Recette donnée pour</span><strong>{{ formatQty(recette.quantite_base) }}</strong><small>{{ recette.unite }}</small></div>
						<div><span>Rendement visé</span><strong>{{ pct(recette.rendement) }}</strong><small>&nbsp;</small></div>
						<div><span>Rendement réel moyen</span><strong>{{ recette.rendement_moyen === null ? '—' : pct(recette.rendement_moyen) }}</strong><small>{{ recette.ordres_termines ? `sur ${recette.ordres_termines} ordre${recette.ordres_termines > 1 ? 's' : ''} terminé${recette.ordres_termines > 1 ? 's' : ''}` : 'aucun ordre terminé' }}</small></div>
					</section>

					<section class="card ref-card">
						<div class="ref-card-head"><h3>Matières pour {{ formatQty(recette.quantite_base) }} {{ recette.unite }}</h3></div>
						<table class="ref-table">
							<thead><tr><th>Matière</th><th>Type</th><th class="end">Quantité</th><th>Obligatoire</th></tr></thead>
							<tbody>
								<tr v-for="row in recette.ingredients" :key="row.name">
									<td><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: row.article } }">{{ row.designation }}</RouterLink> <span class="text-xs tabular-nums text-ink-gray-6">{{ row.article }}</span></td>
									<td><span class="badge" :class="row.type === 'Fût' ? 'tone-violet' : 'tone-blue'">{{ row.type }}</span></td>
									<td class="end tabular-nums">{{ formatQty(row.quantite) }} <span class="text-xs text-ink-gray-6">{{ row.unite }}</span></td>
									<td>{{ row.obligatoire ? 'oui' : 'non' }}</td>
								</tr>
							</tbody>
						</table>
					</section>

					<section class="card recette-calc">
						<label for="recette-calc" class="font-semibold">Combien faut-il pour</label>
						<input id="recette-calc" v-model="pour" class="field-input w-28 text-right tabular-nums" inputmode="decimal" />
						<span>{{ recette.unite }} ?</span>
						<span class="flex-auto text-ink-gray-8">
							<template v-if="parseQty(pour) > 0">{{ besoins.map((row) => `${formatQty(row.quantite)} ${row.unite ?? ''} ${row.designation}`.replace(/\s+/g, ' ')).join(' · ') }}</template>
							<template v-else>Saisissez une quantité.</template>
						</span>
					</section>

					<section class="card ref-card">
						<div class="ref-card-head">
							<h3>Ordres qui utilisent cette recette</h3>
							<RouterLink v-if="recette.nb_ordres" class="text-sm font-medium text-link" :to="{ name: 'Ordres', query: { vue: 'all' } }">Tout voir ({{ recette.nb_ordres }})</RouterLink>
						</div>
						<p v-if="!recette.ordres.length" class="text-ink-gray-6">Aucun ordre pour l'instant.</p>
						<table v-else class="ref-table">
							<tbody>
								<tr v-for="row in recette.ordres" :key="row.name">
									<td><RouterLink class="ref-link tabular-nums" :to="{ name: 'OrdreFiche', params: { id: row.name } }">{{ row.name }}</RouterLink></td>
									<td><StatusPill :status="row.etape" :tone="ETAPE_TONES[row.state]" /></td>
									<td class="tabular-nums">{{ formatDay(row.date_prevue) }}</td>
									<td class="end tabular-nums">{{ row.qty_reelle === null ? `${formatQty(row.qty_prevue)} prévues` : `${formatQty(row.qty_reelle)} sur ${formatQty(row.qty_prevue)} · ${pct(row.rendement ?? 0)}` }}</td>
								</tr>
							</tbody>
						</table>
					</section>
				</div>

				<aside class="record-activity" aria-label="Commentaires et activité de la recette">
					<ActivityFeed ref="feed" :api="activityApi" :version="recette.modified" :user-name="userName" @changed="refresh()" />
				</aside>
			</div>
		</template>

		<RecetteDialog v-if="editing && recette" :recette="recette" @close="editing = false" @saved="onSaved" />
		<OrdreDialog v-if="ordering && recette" :produit="recette.produit" :recette="recette.name" @close="ordering = false" @created="onOrdre" />
		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
	</main>
</template>
