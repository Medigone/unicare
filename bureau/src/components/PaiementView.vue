<script setup lang="ts">
import { computed, ref } from 'vue'
import LucideArrowDownLeft from '~icons/lucide/arrow-down-left'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideBuilding2 from '~icons/lucide/building-2'
import LucideCalendar from '~icons/lucide/calendar'
import LucideCreditCard from '~icons/lucide/credit-card'
import LucideDownload from '~icons/lucide/download'
import LucideLandmark from '~icons/lucide/landmark'
import LucidePrinter from '~icons/lucide/printer'
import LucideUser from '~icons/lucide/user'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FormDialog from '@shared/components/FormDialog.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import PaiementAssistant from './PaiementAssistant.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import { deletePaiement, paiementActivity, paiementPdfUrl, paiementPrintUrl, runPaiementAction } from '@/lib/api'
import { formatAmount } from '@/lib/clients'
import { confirmAction } from '@/lib/confirm'
import { deskUrl, formatDay } from '@/lib/display'
import { PAIEMENT_STATUS, type PaiementDetail } from '@/lib/paiements'
import { usePaiement } from '@/lib/usePaiement'

const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: []; deleted: [] }>()

const { paiement, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = usePaiement(
	() => props.id,
	() => emit('changed'),
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => paiementActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, paiement })

const can = (action: string) => Boolean(paiement.value?.actions.includes(action as never))
const receive = computed(() => paiement.value?.sens === 'Receive')
/** La fiche d'une pièce rapprochée : dans le bureau pour les factures client, sur le Desk sinon. */
// Les pièces et les tiers qui ont leur fiche dans le bureau ; les autres s'ouvrent sur le Desk.
const PIECE_FICHES: Record<string, string> = { 'Sales Invoice': 'FactureFiche', 'Purchase Invoice': 'FactureAchatFiche' }
const TIERS_FICHES: Record<string, string> = { Customer: 'Client', Supplier: 'Fournisseur' }
function pieceRoute(doctype: string, name: string) {
	return doctype in PIECE_FICHES ? { name: PIECE_FICHES[doctype], params: { id: name } } : null
}
function tiersRoute(current: PaiementDetail) {
	return current.tiers_type in TIERS_FICHES ? { name: TIERS_FICHES[current.tiers_type], params: { id: current.tiers } } : null
}

const editing = ref(false)
function onSaved(updated: PaiementDetail) {
	paiement.value = updated
	notice.value = 'Paiement enregistré.'
	emit('changed')
}
async function valider() {
	const current = paiement.value
	if (!current || !(await confirmAction({ title: 'Valider le paiement', message: `Le paiement ${current.name} sera validé : l'écriture comptable est passée et les pièces rapprochées sont mises à jour. Il ne se modifie plus ensuite.`, confirmLabel: 'Valider le paiement' }))) return
	if (current && (await perform(() => runPaiementAction(current, 'valider')))) notice.value = 'Paiement validé : les pièces rapprochées sont à jour.'
}
async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

const confirming = ref<'annuler' | 'supprimer' | null>(null)
async function confirm() {
	const current = paiement.value
	const action = confirming.value
	if (!current || !action) return
	if (action === 'annuler') {
		if (await perform(() => runPaiementAction(current, 'annuler'))) notice.value = 'Paiement annulé : les pièces retrouvent leur reste dû.'
		confirming.value = null
		return
	}
	busy.value = true
	try {
		await deletePaiement(current)
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
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Ce paiement n'existe pas ou n'existe plus.</div>
		<div v-else-if="!paiement" class="card p-8 text-center text-ink-gray-6">Chargement du paiement…</div>

		<template v-else>
			<RecordHeader>
				<template #title><span class="tabular-nums">{{ paiement.name }}</span></template>
				<template #flags>
					<StatusPill :status="PAIEMENT_STATUS[paiement.status]" :tone="paiement.status === 'Submitted' ? 'green' : paiement.status === 'Draft' ? 'amber' : 'gray'" />
					<span class="record-flag">{{ paiement.type_label }}</span>
				</template>
				<template #sub>
					<span>{{ paiement.tiers_label }}</span>
					<span class="tabular-nums">{{ receive ? '' : '−' }}{{ formatAmount(paiement.montant) }} DA</span>
					<div><TagEditor doctype="Payment Entry" :name="paiement.name" :modified="paiement.modified" :tags="paiement.tags" :can-edit="true" @changed="(tags) => (paiement!.tags = tags)" /></div>
				</template>
				<template #actions>
					<button v-if="can('modifier')" type="button" class="btn-secondary" :disabled="busy" @click="editing = true">Modifier</button>
					<button v-if="can('valider')" type="button" class="btn-primary" :disabled="busy" @click="valider">Valider le paiement</button>
					<MoreMenu>
						<template v-if="paiement.can_print">
							<a class="app-menu-item" role="menuitem" :href="paiementPrintUrl(paiement.name)" target="_blank" rel="noopener noreferrer"><LucidePrinter class="h-3.5 w-3.5" aria-hidden="true" />Imprimer le reçu</a>
							<a class="app-menu-item" role="menuitem" :href="paiementPdfUrl(paiement.name)"><LucideDownload class="h-3.5 w-3.5" aria-hidden="true" />Télécharger le PDF</a>
							<div class="app-menu-sep"></div>
						</template>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Payment Entry', paiement.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="can('annuler') || can('supprimer')">
							<div class="app-menu-sep"></div>
							<button v-if="can('annuler')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'annuler'">Annuler le paiement</button>
							<button v-if="can('supprimer')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'supprimer'">Supprimer le brouillon</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations du paiement">
					<div class="side-block">
						<dl class="record-facts">
							<div>
								<dt><component :is="receive ? LucideArrowDownLeft : LucideArrowUpRight" aria-hidden="true" />Sens</dt>
								<dd :class="receive ? 'text-tone-green' : 'text-tone-amber'">{{ receive ? "Entrée d'argent" : "Sortie d'argent" }}</dd>
							</div>
							<div>
								<dt><LucideBuilding2 aria-hidden="true" />{{ paiement.tiers_type === 'Customer' ? 'Client' : 'Fournisseur' }}</dt>
								<dd><RouterLink v-if="tiersRoute(paiement)" class="ref-link" :to="tiersRoute(paiement)!">{{ paiement.tiers_label }}</RouterLink><a v-else class="ref-link" :href="deskUrl(paiement.tiers_type, paiement.tiers)" target="_blank" rel="noopener noreferrer">{{ paiement.tiers_label }}</a></dd>
							</div>
							<div><dt><LucideCalendar aria-hidden="true" />Date</dt><dd class="tabular-nums">{{ formatDay(paiement.date) || '—' }}</dd></div>
							<div><dt><LucideCreditCard aria-hidden="true" />Mode</dt><dd>{{ paiement.mode || '—' }}<span v-if="paiement.reference" class="block font-normal text-ink-gray-7">{{ paiement.reference }}<template v-if="paiement.date_reference"> du {{ formatDay(paiement.date_reference) }}</template></span></dd></div>
							<div><dt><LucideLandmark aria-hidden="true" />Comptes</dt><dd class="font-normal">{{ paiement.compte_depart }} → {{ paiement.compte_arrivee }}</dd></div>
							<div><dt><LucideUser aria-hidden="true" />Créé par</dt><dd>{{ paiement.cree_par }}</dd></div>
						</dl>
					</div>
				</aside>

				<div class="client-main">
					<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
					<div class="bureau-detail">
						<div class="bureau-center">
							<div v-if="paiement.status === 'Draft'" role="status" class="rounded-control tone-amber px-3.5 py-2.5">
								<strong class="font-semibold">Brouillon :</strong> relisez le montant et le rapprochement, puis validez pour passer l'écriture.
							</div>

							<section class="card ref-card">
								<div class="ref-card-head"><h3>Rapprochement</h3><button v-if="can('modifier')" type="button" class="ref-link" @click="editing = true">Modifier</button></div>
								<p v-if="!paiement.affectations.length" class="text-ink-gray-6">Aucune pièce rapprochée : tout le montant est une avance.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Pièce</th><th>Échéance</th><th class="end">Total (DA)</th><th class="end">Reste dû (DA)</th><th class="end">Affecté (DA)</th></tr></thead>
									<tbody>
										<tr v-for="row in paiement.affectations" :key="row.name">
											<td><RouterLink v-if="pieceRoute(row.doctype, row.name)" class="ref-link tabular-nums" :to="pieceRoute(row.doctype, row.name)!">{{ row.name }}</RouterLink><a v-else class="ref-link tabular-nums" :href="deskUrl(row.doctype, row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td>
											<td class="tabular-nums">{{ formatDay(row.echeance) || '—' }}</td>
											<td class="end tabular-nums">{{ formatAmount(row.total) }}</td>
											<td class="end tabular-nums">{{ formatAmount(row.reste) }}</td>
											<td class="end tabular-nums font-semibold">{{ formatAmount(row.montant) }}</td>
										</tr>
									</tbody>
								</table></div>
								<dl class="devis-totaux">
									<div><dt>Montant du paiement</dt><dd class="tabular-nums">{{ formatAmount(paiement.montant) }} DA</dd></div>
									<div><dt>Affecté aux pièces</dt><dd class="tabular-nums">{{ formatAmount(paiement.affecte) }} DA</dd></div>
									<div class="devis-total-ttc"><dt>Avance (non affecté)</dt><dd class="tabular-nums">{{ formatAmount(paiement.non_affecte) }} DA</dd></div>
								</dl>
								<p v-if="paiement.en_lettres" class="text-sm text-ink-gray-6">{{ paiement.en_lettres }}</p>
							</section>

							<section v-if="paiement.remarque" class="card ref-card">
								<h3>Remarque</h3>
								<p class="whitespace-pre-line">{{ paiement.remarque }}</p>
							</section>
						</div>

						<aside class="record-activity" aria-label="Commentaires et activité du paiement">
							<ActivityFeed ref="feed" :api="activityApi" :version="paiement.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<PaiementAssistant v-if="editing && paiement" :paiement="paiement" @close="editing = false" @saved="onSaved" />

		<FormDialog v-if="confirming && paiement" :title="confirming === 'annuler' ? 'Annuler le paiement' : 'Supprimer le brouillon'" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour confirmer" @close="confirming = null" @submit="confirm">
			<p>{{ confirming === 'annuler' ? `Le paiement ${paiement.name} sera annulé : l'écriture est contrepassée et les pièces rapprochées retrouvent leur reste dû.` : `Le brouillon ${paiement.name} sera supprimé.` }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="confirm">{{ confirming === 'annuler' ? 'Annuler le paiement' : 'Supprimer' }}</button>
			</template>
		</FormDialog>

		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
	</main>
</template>
