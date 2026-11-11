<script setup lang="ts">
import { computed, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideBuilding2 from '~icons/lucide/building-2'
import LucideCalendar from '~icons/lucide/calendar'
import LucideFileText from '~icons/lucide/file-text'
import LucideHash from '~icons/lucide/hash'
import LucideMapPin from '~icons/lucide/map-pin'
import LucideDownload from '~icons/lucide/download'
import LucidePrinter from '~icons/lucide/printer'
import LucideTruck from '~icons/lucide/truck'
import LucideUser from '~icons/lucide/user'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FormDialog from '@shared/components/FormDialog.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import VenteDialog from './VenteDialog.vue'
import { commandeActivity, commandePdfUrl, commandePrintUrl, createSuivante, deleteCommande, runCommandeAction, setCommandeStatus } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { formatPercent, STATUS_ACTIONS, type CommandeDetail, type StatusAction } from '@/lib/commandes'
import { dayFromToday } from '@/lib/devis'
import { deskUrl, formatDay } from '@/lib/display'
import { useCommande } from '@/lib/useCommande'

const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: []; deleted: [] }>()

const { commande, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useCommande(
	() => props.id,
	() => emit('changed'),
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => commandeActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, commande })

const can = (action: string) => Boolean(commande.value?.actions.includes(action as never))
const late = computed(() => {
	const current = commande.value
	return Boolean(current?.livraison && current.livraison < dayFromToday(0) && ['To Deliver and Bill', 'To Deliver'].includes(current.status))
})
const statusActions = computed(() => STATUS_ACTIONS.filter((item) => can(item.key)))
const submitted = computed(() => commande.value?.docstatus === 1)

async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

const editing = ref(false)
function onSaved(updated: CommandeDetail) {
	commande.value = updated
	notice.value = 'Commande enregistrée.'
	emit('changed')
}

async function valider() {
	const current = commande.value
	if (current && (await perform(() => runCommandeAction(current, 'valider')))) notice.value = 'Commande validée.'
}
async function changeStatus(action: StatusAction) {
	const current = commande.value
	const label = STATUS_ACTIONS.find((item) => item.key === action)
	if (current && (await perform(() => setCommandeStatus(current, action)))) notice.value = label?.done ?? ''
}

// Bon de livraison ou facture : créé en brouillon, à vérifier puis valider sur le Desk (lots, dépôts, échéances).
const created = ref<{ doctype: string; name: string; label: string } | null>(null)
async function createNext(kind: 'livraison' | 'facture') {
	const current = commande.value
	if (!current) return
	let result: { doctype: string; name: string } | null = null
	const done = await perform(async () => {
		const response = await createSuivante(current, kind)
		result = response
		return response.commande
	})
	if (done && result) {
		const { doctype, name } = result
		created.value = { doctype, name, label: kind === 'livraison' ? `Bon de livraison ${name} créé : préparez-le (dépôt, lots) puis validez-le.` : `Facture ${name} créée en brouillon : vérifiez-la puis validez-la.` }
	}
}

// Confirmations : annuler une commande validée, supprimer un brouillon.
const confirming = ref<'annuler' | 'supprimer' | null>(null)
async function confirm() {
	const current = commande.value
	const action = confirming.value
	if (!current || !action) return
	if (action === 'annuler') {
		if (await perform(() => runCommandeAction(current, 'annuler'))) notice.value = 'Commande annulée.'
		confirming.value = null
		return
	}
	busy.value = true
	try {
		await deleteCommande(current)
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
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Cette commande n'existe pas ou n'existe plus.</div>
		<div v-else-if="!commande" class="card p-8 text-center text-ink-gray-6">Chargement de la commande…</div>

		<template v-else>
			<RecordHeader>
				<template #title><span class="tabular-nums">{{ commande.name }}</span></template>
				<template #flags><StatusPill :status="commande.status" /></template>
				<template #sub>
					<RouterLink class="ref-link" :to="{ name: 'Client', params: { id: commande.client } }">{{ commande.client_label }}</RouterLink>
					<span class="tabular-nums">{{ formatAmount(commande.total_ttc) }} DA TTC</span>
					<div><TagEditor doctype="Sales Order" :name="commande.name" :modified="commande.modified" :tags="commande.tags" :can-edit="true" @changed="(tags) => (commande!.tags = tags)" /></div>
				</template>
				<template #actions>
					<button v-if="can('valider')" type="button" class="btn-primary" :disabled="busy || commande.blocked.length > 0" :title="commande.blocked.join(' ') || undefined" @click="valider">Valider</button>
					<button v-if="can('livraison')" type="button" class="btn-primary" :disabled="busy" @click="createNext('livraison')">Créer la livraison</button>
					<button v-if="can('facture')" type="button" class="btn-secondary" :disabled="busy" @click="createNext('facture')">Créer la facture</button>
					<button v-if="can('modifier')" type="button" class="btn-secondary" :disabled="busy" @click="editing = true">Modifier</button>
					<MoreMenu>
						<template v-if="statusActions.length">
							<button v-for="item in statusActions" :key="item.key" type="button" class="app-menu-item" role="menuitem" :disabled="busy" @click="changeStatus(item.key)">{{ item.label }}</button>
							<div class="app-menu-sep"></div>
						</template>
						<template v-if="commande.can_print">
							<a class="app-menu-item" role="menuitem" :href="commandePrintUrl(commande.name)" target="_blank" rel="noopener noreferrer"><LucidePrinter class="h-3.5 w-3.5" aria-hidden="true" />Imprimer</a>
							<a class="app-menu-item" role="menuitem" :href="commandePdfUrl(commande.name)"><LucideDownload class="h-3.5 w-3.5" aria-hidden="true" />Télécharger le PDF</a>
							<div class="app-menu-sep"></div>
						</template>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Sales Order', commande.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="can('annuler') || can('supprimer')">
							<div class="app-menu-sep"></div>
							<button v-if="can('annuler')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'annuler'">Annuler la commande</button>
							<button v-if="can('supprimer')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'supprimer'">Supprimer le brouillon</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations de la commande">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucideBuilding2 aria-hidden="true" />Client</dt><dd><RouterLink class="ref-link" :to="{ name: 'Client', params: { id: commande.client } }">{{ commande.client_label }}</RouterLink></dd></div>
							<div v-if="commande.commune || commande.wilaya"><dt><LucideMapPin aria-hidden="true" />Livrée à</dt><dd>{{ [commande.commune, commande.wilaya].filter(Boolean).join(', ') }}</dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Date</dt><dd class="tabular-nums">{{ formatDay(commande.date) || '—' }}</dd></div>
							<div><dt><LucideTruck aria-hidden="true" />Livraison prévue</dt><dd class="tabular-nums" :class="late && 'text-tone-red'">{{ formatDay(commande.livraison) || '—' }}<template v-if="late"> · en retard</template></dd></div>
							<div v-if="commande.reference"><dt><LucideHash aria-hidden="true" />Référence client</dt><dd>{{ commande.reference }}</dd></div>
							<div v-if="commande.devis.length"><dt><LucideFileText aria-hidden="true" />Devis</dt><dd><template v-for="(name, index) in commande.devis" :key="name">{{ index ? ', ' : '' }}<RouterLink class="ref-link tabular-nums" :to="{ name: 'DevisFiche', params: { id: name } }">{{ name }}</RouterLink></template></dd></div>
							<div><dt><LucideUser aria-hidden="true" />Créée par</dt><dd>{{ commande.cree_par }}</dd></div>
						</dl>
					</div>
					<div v-if="submitted" class="side-block">
						<div class="commande-progress"><span>Livré</span><strong class="tabular-nums">{{ formatPercent(commande.livre) }}</strong></div>
						<div class="commande-bar" role="progressbar" :aria-valuenow="commande.livre" aria-valuemin="0" aria-valuemax="100" aria-label="Part livrée"><span :style="{ width: `${Math.min(commande.livre, 100)}%` }"></span></div>
						<div class="commande-progress mt-1"><span>Facturé</span><strong class="tabular-nums">{{ formatPercent(commande.facture) }}</strong></div>
						<div class="commande-bar" role="progressbar" :aria-valuenow="commande.facture" aria-valuemin="0" aria-valuemax="100" aria-label="Part facturée"><span :style="{ width: `${Math.min(commande.facture, 100)}%` }"></span></div>
					</div>
				</aside>

				<div class="client-main">
					<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
					<div class="bureau-detail">
						<div class="bureau-center">
							<div v-if="commande.blocked.length" role="status" class="rounded-control tone-amber px-3.5 py-2.5">
								<strong class="font-semibold">Pas encore validable :</strong> {{ commande.blocked.join(' ') }}
								<button v-if="can('modifier')" type="button" class="font-medium underline" @click="editing = true">Modifier la commande</button>
							</div>
							<div v-if="commande.status === 'On Hold'" role="status" class="rounded-control tone-amber px-3.5 py-2.5">
								<strong class="font-semibold">Commande en attente :</strong> ni livraison ni facture tant qu'elle n'est pas reprise.
								<button v-if="can('reprendre')" type="button" class="font-medium underline" :disabled="busy" @click="changeStatus('reprendre')">Reprendre</button>
							</div>

							<section class="card ref-card">
								<h3>Lignes</h3>
								<p v-if="!commande.lignes.length" class="text-ink-gray-6">Aucune ligne.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Article</th><th class="end">Quantité</th><th v-if="submitted" class="end">Livré</th><th class="end">Prix HT (DA)</th><th class="end">Montant HT (DA)</th></tr></thead>
									<tbody>
										<tr v-for="line in commande.lignes" :key="line.name">
											<td>
												<RouterLink class="ref-link" :to="{ name: 'Article', params: { id: line.article } }">{{ line.designation }}</RouterLink>
												<span class="ml-1 text-xs tabular-nums text-ink-gray-6">{{ line.article }}</span>
												<span v-if="line.description" class="block text-sm text-ink-gray-7">{{ line.description }}</span>
											</td>
											<td class="end tabular-nums">{{ formatQty(line.quantite) }} {{ line.unite }}</td>
											<td v-if="submitted" class="end tabular-nums" :class="line.livre >= line.quantite ? 'text-tone-green' : !line.livre && 'text-ink-gray-6'">{{ formatQty(line.livre) }}</td>
											<td class="end tabular-nums" :class="!line.prix && 'font-semibold text-tone-amber'">{{ line.prix ? formatAmount(line.prix) : 'Sans prix' }}</td>
											<td class="end tabular-nums">{{ formatAmount(line.montant) }}</td>
										</tr>
									</tbody>
								</table></div>
								<dl class="devis-totaux">
									<div><dt>Total HT</dt><dd class="tabular-nums">{{ formatAmount(commande.total) }} DA</dd></div>
									<div v-for="tax in commande.taxes" :key="tax.description"><dt>{{ tax.description }}</dt><dd class="tabular-nums">{{ formatAmount(tax.montant) }} DA</dd></div>
									<div class="devis-total-ttc"><dt>Total TTC</dt><dd class="tabular-nums">{{ formatAmount(commande.arrondi ?? commande.total_ttc) }} DA</dd></div>
								</dl>
								<p v-if="commande.en_lettres" class="text-sm text-ink-gray-6">{{ commande.en_lettres }}</p>
							</section>

							<div v-if="submitted" class="client-cards">
								<section v-for="group in [{ key: 'livraisons', title: 'Livraisons', doctype: 'Delivery Note', rows: commande.livraisons, empty: 'Aucun bon de livraison.' }, { key: 'factures', title: 'Factures', doctype: 'Sales Invoice', rows: commande.factures, empty: 'Aucune facture.' }].filter((item) => item.rows)" :key="group.key" class="card ref-card">
									<h3>{{ group.title }}</h3>
									<p v-if="!group.rows!.length" class="text-ink-gray-6">{{ group.empty }}</p>
									<div v-else class="ref-scroll"><table class="ref-table">
										<thead><tr><th>Numéro</th><th>Date</th><th>Statut</th><th class="end">Total (DA)</th></tr></thead>
										<tbody><tr v-for="row in group.rows!" :key="row.name"><td><RouterLink class="ref-link" :to="{ name: group.doctype === 'Delivery Note' ? 'LivraisonFiche' : 'FactureFiche', params: { id: row.name } }">{{ row.name }}</RouterLink></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td><StatusPill :status="row.status" /></td><td class="end tabular-nums">{{ formatAmount(row.total) }}</td></tr></tbody>
									</table></div>
								</section>
							</div>
						</div>

						<aside class="record-activity" aria-label="Commentaires et activité de la commande">
							<ActivityFeed ref="feed" :api="activityApi" :version="commande.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<VenteDialog v-if="editing && commande" kind="commande" :piece="commande" @close="editing = false" @saved="(piece) => onSaved(piece as CommandeDetail)" />

		<FormDialog v-if="confirming && commande" :title="confirming === 'annuler' ? 'Annuler la commande' : 'Supprimer le brouillon'" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour confirmer" @close="confirming = null" @submit="confirm">
			<p>{{ confirming === 'annuler' ? `La commande ${commande.name} sera annulée et libérera le stock réservé. ERPNext refuse si une livraison ou une facture validée en dépend.` : `Le brouillon ${commande.name} sera supprimé définitivement.` }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="confirm">{{ confirming === 'annuler' ? 'Annuler la commande' : 'Supprimer' }}</button>
			</template>
		</FormDialog>

		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
		<AppToast :message="created?.label ?? ''" :duration="0" @close="created = null">
			<template v-if="created">
				<RouterLink v-if="created.doctype === 'Delivery Note'" class="app-toast-action" :to="{ name: 'LivraisonFiche', params: { id: created.name } }" @click="created = null">Préparer le bon</RouterLink>
				<RouterLink v-else class="app-toast-action" :to="{ name: 'FactureFiche', params: { id: created.name } }" @click="created = null">Ouvrir la facture</RouterLink>
			</template>
		</AppToast>
	</main>
</template>
