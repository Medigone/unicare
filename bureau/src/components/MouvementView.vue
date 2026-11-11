<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import LucideArrowRight from '~icons/lucide/arrow-right'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideCalendar from '~icons/lucide/calendar'
import LucideFactory from '~icons/lucide/factory'
import LucideMessageSquare from '~icons/lucide/message-square'
import LucidePrinter from '~icons/lucide/printer'
import LucideUser from '~icons/lucide/user'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FormDialog from '@shared/components/FormDialog.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import MouvementDialog from './MouvementDialog.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import VersionsCard from './VersionsCard.vue'
import { createPieceVersion, deleteMouvement, mouvementActivity, mouvementPrintUrl, runMouvementAction } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { confirmAction } from '@/lib/confirm'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { natureLabel, type MouvementDetail } from '@/lib/mouvements'
import { useMouvement } from '@/lib/useMouvement'

const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: []; deleted: [] }>()

const { mouvement, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useMouvement(
	() => props.id,
	() => emit('changed'),
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => mouvementActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, mouvement })

const can = (action: string) => Boolean(mouvement.value?.actions.includes(action as never))
const valeur = computed(() => (mouvement.value ? mouvement.value.valeur_sortie || mouvement.value.valeur_entree : 0))

async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

const editing = ref(false)
function onSaved(updated: MouvementDetail) {
	mouvement.value = updated
	notice.value = 'Mouvement enregistré.'
	emit('changed')
}

const EFFETS: Record<string, string> = {
	transfert: 'la marchandise quitte le dépôt de départ et entre dans le dépôt d\'arrivée.',
	entree: 'la marchandise entre dans le dépôt.',
	sortie: 'la marchandise quitte définitivement le stock.',
}
async function valider() {
	const current = mouvement.value
	if (!current) return
	if (!(await confirmAction({ title: 'Valider le mouvement', message: `Le mouvement ${current.name} sera validé : ${EFFETS[current.nature] ?? 'le stock bouge.'} Il ne se modifie plus ensuite.`, confirmLabel: 'Valider le mouvement' }))) return
	if (await perform(() => runMouvementAction(current, 'valider'))) notice.value = 'Mouvement validé : le stock a bougé.'
}

// Versions : un mouvement annulé se refait en nouvelle version (brouillon NOM-1), comme « Modifier » sur le Desk.
const router = useRouter()
async function nouvelleVersion(confirmed = false) {
	const current = mouvement.value
	if (!current) return
	if (!confirmed && !(await confirmAction({ title: 'Nouvelle version', message: `Une nouvelle version de ${current.name} sera créée en brouillon, avec les mêmes lignes : vous la corrigerez puis la validerez.`, confirmLabel: 'Créer la nouvelle version' }))) return
	busy.value = true
	actionError.value = ''
	try {
		const result = await createPieceVersion('mouvements', current)
		emit('changed')
		await router.push({ name: 'MouvementFiche', params: { id: result.name } })
		notice.value = result.note || `Nouvelle version ${result.name} créée en brouillon.`
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}

// Confirmations : annuler un mouvement validé (et, au choix, le refaire), supprimer un brouillon.
const confirming = ref<'annuler' | 'annuler_version' | 'supprimer' | null>(null)
async function confirm() {
	const current = mouvement.value
	const action = confirming.value
	if (!current || !action) return
	if (action !== 'supprimer') {
		const cancelled = await perform(() => runMouvementAction(current, 'annuler'))
		if (cancelled) notice.value = 'Mouvement annulé : le stock est revenu.'
		confirming.value = null
		if (cancelled && action === 'annuler_version') await nouvelleVersion(true)
		return
	}
	busy.value = true
	try {
		await deleteMouvement(current)
		confirming.value = null
		emit('deleted')
	} catch (e) {
		actionError.value = (e as Error).message
		confirming.value = null
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<main class="bureau-main">
		<div v-if="error" role="alert" class="card p-3.5 text-tone-red">
			{{ error }}
			<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
		</div>
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Ce mouvement n'existe pas ou n'existe plus.</div>
		<div v-else-if="!mouvement" class="card p-8 text-center text-ink-gray-6">Chargement du mouvement…</div>

		<template v-else>
			<RecordHeader>
				<template #title><span class="tabular-nums">{{ mouvement.name }}</span></template>
				<template #flags>
					<StatusPill :status="mouvement.status" />
					<span class="record-flag">{{ natureLabel(mouvement.nature) }}</span>
				</template>
				<template #sub>
					<span class="tabular-nums">{{ formatDay(mouvement.date) }}</span>
					<span class="tabular-nums">{{ formatAmount(valeur) }} DA</span>
					<div><TagEditor doctype="Stock Entry" :name="mouvement.name" :modified="mouvement.modified" :tags="mouvement.tags" :can-edit="true" @changed="(tags) => (mouvement!.tags = tags)" /></div>
				</template>
				<template #actions>
					<button v-if="can('nouvelle_version')" type="button" class="btn-primary" :disabled="busy" @click="nouvelleVersion()">Nouvelle version</button>
					<button v-if="can('valider')" type="button" class="btn-primary" :disabled="busy || mouvement.blocked.length > 0" :title="mouvement.blocked.join(' ') || undefined" @click="valider">Valider</button>
					<button v-if="can('modifier')" type="button" class="btn-secondary" :disabled="busy" @click="editing = true">Modifier</button>
					<MoreMenu>
						<template v-if="mouvement.can_print">
							<a class="app-menu-item" role="menuitem" :href="mouvementPrintUrl(mouvement.name)" target="_blank" rel="noopener noreferrer"><LucidePrinter class="h-3.5 w-3.5" aria-hidden="true" />Imprimer</a>
							<div class="app-menu-sep"></div>
						</template>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Stock Entry', mouvement.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="can('annuler') || can('supprimer')">
							<div class="app-menu-sep"></div>
							<button v-if="can('annuler')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'annuler'">Annuler le mouvement</button>
							<button v-if="can('supprimer')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'supprimer'">{{ mouvement.docstatus === 2 ? 'Supprimer la pièce annulée' : 'Supprimer le brouillon' }}</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations du mouvement">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucideArrowRight aria-hidden="true" />Trajet</dt><dd>{{ mouvement.lignes[0]?.source || 'Entrée' }} → {{ mouvement.lignes[0]?.cible || 'Sortie du stock' }}</dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Date</dt><dd class="tabular-nums">{{ formatDay(mouvement.date) || '—' }}</dd></div>
							<div v-if="mouvement.remarque"><dt><LucideMessageSquare aria-hidden="true" />Remarque</dt><dd class="font-normal">{{ mouvement.remarque }}</dd></div>
							<div v-if="mouvement.ordre"><dt><LucideFactory aria-hidden="true" />Ordre de conditionnement</dt><dd><RouterLink class="ref-link" :to="{ name: 'OrdreFiche', params: { id: mouvement.ordre } }">{{ mouvement.ordre }}</RouterLink></dd></div>
							<div><dt><LucideUser aria-hidden="true" />Créé par</dt><dd>{{ mouvement.cree_par }}</dd></div>
						</dl>
					</div>
				</aside>

				<div class="client-main">
					<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
					<div class="bureau-detail">
						<div class="bureau-center">
							<VersionsCard :versions="mouvement.versions" :docstatus="mouvement.docstatus" fiche="MouvementFiche" :can-amend="can('nouvelle_version')" />
							<div v-if="mouvement.depuis_ordre" role="status" class="rounded-control tone-blue px-3.5 py-2.5">
								<strong class="font-semibold">Mouvement piloté par {{ mouvement.ordre ? `l'ordre ${mouvement.ordre}` : 'la production' }}</strong> : il se consulte ici, mais c'est l'ordre de conditionnement qui le crée et l'annule.
							</div>
							<div v-if="mouvement.blocked.length" role="status" class="rounded-control tone-amber px-3.5 py-2.5">
								<strong class="font-semibold">Pas encore validable :</strong> {{ mouvement.blocked.join(' ') }}
								<button v-if="can('modifier')" type="button" class="font-medium underline" @click="editing = true">Modifier le mouvement</button>
							</div>

							<section class="card ref-card">
								<h3>Lignes</h3>
								<div class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Article</th><th class="end">Quantité</th><th>Départ</th><th>Arrivée</th><th>Lot</th><th class="end">Valeur (DA)</th></tr></thead>
									<tbody>
										<tr v-for="row in mouvement.lignes" :key="row.name">
											<td><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: row.article } }">{{ row.designation }}</RouterLink><span class="ml-1 text-xs tabular-nums text-ink-gray-6">{{ row.article }}</span></td>
											<td class="end tabular-nums">{{ formatQty(row.quantite) }} {{ row.unite }}</td>
											<td>{{ row.source || '—' }}</td>
											<td>{{ row.cible || '—' }}</td>
											<td class="tabular-nums">
												<template v-if="row.lots.length"><template v-for="(lot, index) in row.lots" :key="lot">{{ index ? ', ' : '' }}<RouterLink class="ref-link" :to="{ name: 'Lot', params: { id: lot } }">{{ lot }}</RouterLink></template></template>
												<span v-else :class="row.avec_lot && mouvement.docstatus === 0 ? 'font-semibold text-tone-amber' : 'text-ink-gray-6'">{{ row.avec_lot && mouvement.docstatus === 0 ? 'À choisir' : '—' }}</span>
											</td>
											<td class="end tabular-nums">{{ formatAmount(row.valeur) }}</td>
										</tr>
									</tbody>
								</table></div>
							</section>
						</div>

						<aside class="record-activity" aria-label="Commentaires et activité du mouvement">
							<ActivityFeed ref="feed" :api="activityApi" :version="mouvement.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<MouvementDialog v-if="editing && mouvement" :mouvement="mouvement" @close="editing = false" @saved="onSaved" />

		<FormDialog v-if="confirming && mouvement" :title="confirming !== 'supprimer' ? 'Annuler le mouvement' : mouvement.docstatus === 2 ? 'Supprimer la pièce annulée' : 'Supprimer le brouillon'" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour confirmer" @close="confirming = null" @submit="confirm">
			<p>{{ confirming !== 'supprimer' ? `Le mouvement ${mouvement.name} sera annulé : le stock revient comme avant. ERPNext refuse si ce stock a déjà été consommé ou déplacé depuis.` : `Le brouillon ${mouvement.name} sera supprimé définitivement.` }}</p>
			<template #actions>
				<button v-if="confirming === 'annuler' && canCreate('Stock Entry')" type="button" class="btn-secondary" :disabled="busy" @click="(confirming = 'annuler_version'), confirm()">Annuler et créer une nouvelle version</button>
				<button type="button" class="btn-primary" :disabled="busy" @click="confirm">{{ confirming !== 'supprimer' ? 'Annuler le mouvement' : 'Supprimer' }}</button>
			</template>
		</FormDialog>

		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
	</main>
</template>
