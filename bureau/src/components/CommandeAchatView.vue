<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideBuilding2 from '~icons/lucide/building-2'
import LucideCalendar from '~icons/lucide/calendar'
import LucideFileText from '~icons/lucide/file-text'
import LucideDownload from '~icons/lucide/download'
import LucidePrinter from '~icons/lucide/printer'
import LucidePackageOpen from '~icons/lucide/package-open'
import LucideUser from '~icons/lucide/user'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FormDialog from '@shared/components/FormDialog.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import VersionsCard from './VersionsCard.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import AchatDialog from './AchatDialog.vue'
import { commandeAchatActivity, commandeAchatPdfUrl, commandeAchatPrintUrl, createCommandeAchatSuivante, deleteCommandeAchat, runCommandeAchatAction, setCommandeAchatStatus } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { STATUS_ACTIONS } from '@/lib/commandes'
import { A_RECEVOIR, formatPercent, type CommandeAchatDetail, type StatusAction } from '@/lib/commandesAchat'
import { dayFromToday } from '@/lib/devis'
import { confirmAction } from '@/lib/confirm'
import { createPieceVersion } from '@/lib/api'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { useCommandeAchat } from '@/lib/useCommandeAchat'

const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: []; deleted: [] }>()

const { commande, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useCommandeAchat(
	() => props.id,
	() => emit('changed'),
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => commandeAchatActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, commande })

// Les pièces qui ont déjà leur fiche dans le bureau ; les autres s'ouvrent sur le Desk.
const router = useRouter()
const hasFiche = (name: string) => router.hasRoute(name)
const can = (action: string) => Boolean(commande.value?.actions.includes(action as never))
const late = computed(() => {
	const current = commande.value
	return Boolean(current?.reception && current.reception < dayFromToday(0) && A_RECEVOIR.includes(current.status))
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
function onSaved(updated: CommandeAchatDetail) {
	commande.value = updated
	notice.value = 'Commande enregistrée.'
	emit('changed')
}

async function valider() {
	const current = commande.value
	if (!current || !(await confirmAction({ title: 'Valider la commande', message: `La commande d'achat ${current.name} sera validée : elle ne se modifie plus et attend sa réception.`, confirmLabel: 'Valider la commande' }))) return
	if (current && (await perform(() => runCommandeAchatAction(current, 'valider')))) notice.value = 'Commande validée.'
}
async function changeStatus(action: StatusAction) {
	const current = commande.value
	const label = STATUS_ACTIONS.find((item) => item.key === action)
	if (!current || !label || !(await confirmAction({ title: label.label, message: label.confirm(current.name), confirmLabel: label.label, danger: action === 'cloturer' }))) return
	if (current && (await perform(() => setCommandeAchatStatus(current, action)))) notice.value = label?.done ?? ''
}

// Réception ou facture d'achat : créée en brouillon, à vérifier puis valider (lots, dépôts, n° de facture).
const created = ref<{ doctype: string; name: string; label: string } | null>(null)
async function createNext(kind: 'reception' | 'facture') {
	const current = commande.value
	if (!current) return
	const [title, message] = kind === 'reception' ? ['Créer la réception', `La réception de la commande ${current.name} sera créée en brouillon, avec les quantités restant à recevoir.`] : ['Créer la facture d\'achat', `La facture d'achat de la commande ${current.name} sera créée en brouillon, avec ce qui reste à facturer.`]
	if (!(await confirmAction({ title, message, confirmLabel: title }))) return
	let result: { doctype: string; name: string; note: string | null } | null = null
	const done = await perform(async () => {
		const response = await createCommandeAchatSuivante(current, kind)
		result = response
		return response.commande
	})
	if (done && result) {
		const { doctype, name, note } = result
		created.value = { doctype, name, label: [kind === 'reception' ? `Réception ${name} créée : saisissez les quantités reçues et les lots, puis validez-la.` : `Facture d'achat ${name} créée en brouillon : saisissez le n° du fournisseur puis validez-la.`, note].filter(Boolean).join(' ') }
	}
}

// Confirmations : annuler une commande validée, supprimer un brouillon.
const confirming = ref<'annuler' | 'annuler_version' | 'supprimer' | null>(null)
async function confirm() {
	const current = commande.value
	const action = confirming.value
	if (!current || !action) return
	if (action === 'annuler' || action === 'annuler_version') {
		const cancelled = await perform(() => runCommandeAchatAction(current, 'annuler'))
		if (cancelled) notice.value = 'Commande annulée.'
		confirming.value = null
		if (cancelled && action === 'annuler_version') await nouvelleVersion(true)
		return
	}
	busy.value = true
	try {
		await deleteCommandeAchat(current)
		confirming.value = null
		emit('deleted')
	} catch (e) {
		actionError.value = (e as Error).message
		confirming.value = null
	} finally {
		busy.value = false
	}
}
// Versions : une pièce annulée se refait en nouvelle version (brouillon NOM-1), comme « Modifier » sur le Desk.
const versionRouter = useRouter()
async function nouvelleVersion(confirmed = false) {
	const current = commande.value
	if (!current) return
	if (!confirmed && !(await confirmAction({ title: 'Nouvelle version', message: `Une nouvelle version de ${current.name} sera créée en brouillon, avec le même contenu : vous la corrigerez puis la validerez.`, confirmLabel: 'Créer la nouvelle version' }))) return
	busy.value = true
	actionError.value = ''
	try {
		const result = await createPieceVersion('commandes_achat', current)
		emit('changed')
		await versionRouter.push({ name: 'CommandeAchatFiche', params: { id: result.name } })
		notice.value = result.note || `Nouvelle version ${result.name} créée en brouillon.`
	} catch (e) {
		actionError.value = (e as Error).message
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
					<RouterLink class="ref-link" :to="{ name: 'Fournisseur', params: { id: commande.fournisseur } }">{{ commande.fournisseur_label }}</RouterLink>
					<span class="tabular-nums">{{ formatAmount(commande.total_ttc) }} DA TTC</span>
					<div><TagEditor doctype="Purchase Order" :name="commande.name" :modified="commande.modified" :tags="commande.tags" :can-edit="true" @changed="(tags) => (commande!.tags = tags)" /></div>
				</template>
				<template #actions>
					<button v-if="can('nouvelle_version')" type="button" class="btn-primary" :disabled="busy" @click="nouvelleVersion()">Nouvelle version</button>
					<button v-if="can('valider')" type="button" class="btn-primary" :disabled="busy || commande.blocked.length > 0" :title="commande.blocked.join(' ') || undefined" @click="valider">Valider</button>
					<button v-if="can('reception')" type="button" class="btn-primary" :disabled="busy" @click="createNext('reception')">Créer la réception</button>
					<button v-if="can('facture')" type="button" class="btn-secondary" :disabled="busy" @click="createNext('facture')">Créer la facture</button>
					<button v-if="can('modifier')" type="button" class="btn-secondary" :disabled="busy" @click="editing = true">Modifier</button>
					<MoreMenu>
						<template v-if="statusActions.length">
							<button v-for="item in statusActions" :key="item.key" type="button" class="app-menu-item" role="menuitem" :disabled="busy" @click="changeStatus(item.key)">{{ item.label }}</button>
							<div class="app-menu-sep"></div>
						</template>
						<template v-if="commande.can_print">
							<a class="app-menu-item" role="menuitem" :href="commandeAchatPrintUrl(commande.name)" target="_blank" rel="noopener noreferrer"><LucidePrinter class="h-3.5 w-3.5" aria-hidden="true" />Imprimer</a>
							<a class="app-menu-item" role="menuitem" :href="commandeAchatPdfUrl(commande.name)"><LucideDownload class="h-3.5 w-3.5" aria-hidden="true" />Télécharger le PDF</a>
							<div class="app-menu-sep"></div>
						</template>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Purchase Order', commande.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="can('annuler') || can('supprimer')">
							<div class="app-menu-sep"></div>
							<button v-if="can('annuler')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'annuler'">Annuler la commande</button>
							<button v-if="can('supprimer')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'supprimer'">{{ commande.docstatus === 2 ? 'Supprimer la pièce annulée' : 'Supprimer le brouillon' }}</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations de la commande d'achat">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucideBuilding2 aria-hidden="true" />Fournisseur</dt><dd><RouterLink class="ref-link" :to="{ name: 'Fournisseur', params: { id: commande.fournisseur } }">{{ commande.fournisseur_label }}</RouterLink></dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Date</dt><dd class="tabular-nums">{{ formatDay(commande.date) || '—' }}</dd></div>
							<div><dt><LucidePackageOpen aria-hidden="true" />Réception prévue</dt><dd class="tabular-nums" :class="late && 'text-tone-red'">{{ formatDay(commande.reception) || '—' }}<template v-if="late"> · en retard</template></dd></div>
							<div v-if="commande.depot"><dt><LucidePackageOpen aria-hidden="true" />Dépôt</dt><dd>{{ commande.depot }}</dd></div>
							<div v-if="commande.devis.length"><dt><LucideFileText aria-hidden="true" />Devis fournisseur</dt><dd><template v-for="(name, index) in commande.devis" :key="name">{{ index ? ', ' : '' }}<RouterLink class="ref-link tabular-nums" :to="{ name: 'DevisFournisseurFiche', params: { id: name } }">{{ name }}</RouterLink></template></dd></div>
							<div><dt><LucideUser aria-hidden="true" />Créée par</dt><dd>{{ commande.cree_par }}</dd></div>
						</dl>
					</div>
					<div v-if="submitted" class="side-block">
						<div class="commande-progress"><span>Reçu</span><strong class="tabular-nums">{{ formatPercent(commande.recu) }}</strong></div>
						<div class="commande-bar" role="progressbar" :aria-valuenow="commande.recu" aria-valuemin="0" aria-valuemax="100" aria-label="Part reçue"><span :style="{ width: `${Math.min(commande.recu, 100)}%` }"></span></div>
						<div class="commande-progress mt-1"><span>Facturé</span><strong class="tabular-nums">{{ formatPercent(commande.facture) }}</strong></div>
						<div class="commande-bar" role="progressbar" :aria-valuenow="commande.facture" aria-valuemin="0" aria-valuemax="100" aria-label="Part facturée"><span :style="{ width: `${Math.min(commande.facture, 100)}%` }"></span></div>
					</div>
				</aside>

				<div class="client-main">
					<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
					<div class="bureau-detail">
						<div class="bureau-center">
							<VersionsCard :versions="commande.versions" :docstatus="commande.docstatus" fiche="CommandeAchatFiche" :can-amend="can('nouvelle_version')" :busy="busy" @amend="nouvelleVersion()" />
							<div v-if="commande.blocked.length" role="status" class="rounded-control tone-amber px-3.5 py-2.5">
								<strong class="font-semibold">Pas encore validable :</strong> {{ commande.blocked.join(' ') }}
								<button v-if="can('modifier')" type="button" class="font-medium underline" @click="editing = true">Modifier la commande</button>
							</div>
							<div v-if="commande.status === 'On Hold'" role="status" class="rounded-control tone-amber px-3.5 py-2.5">
								<strong class="font-semibold">Commande en attente :</strong> ni réception ni facture tant qu'elle n'est pas reprise.
								<button v-if="can('reprendre')" type="button" class="font-medium underline" :disabled="busy" @click="changeStatus('reprendre')">Reprendre</button>
							</div>

							<section class="card ref-card">
								<h3>Lignes</h3>
								<p v-if="!commande.lignes.length" class="text-ink-gray-6">Aucune ligne.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Article</th><th class="end">Quantité</th><th v-if="submitted" class="end">Reçu</th><th class="end">Prix HT (DA)</th><th class="end">Montant HT (DA)</th></tr></thead>
									<tbody>
										<tr v-for="line in commande.lignes" :key="line.name">
											<td>
												<RouterLink class="ref-link" :to="{ name: 'Article', params: { id: line.article } }">{{ line.designation }}</RouterLink>
												<span class="ml-1 text-xs tabular-nums text-ink-gray-6">{{ line.article }}</span>
												<span v-if="line.description" class="block text-sm text-ink-gray-7">{{ line.description }}</span>
											</td>
											<td class="end tabular-nums">{{ formatQty(line.quantite) }} {{ line.unite }}</td>
											<td v-if="submitted" class="end tabular-nums" :class="line.recu >= line.quantite ? 'text-tone-green' : !line.recu && 'text-ink-gray-6'">{{ formatQty(line.recu) }}</td>
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
								<section v-for="group in [{ key: 'receptions', title: 'Réceptions', doctype: 'Purchase Receipt', fiche: 'ReceptionFiche', rows: commande.receptions, empty: 'Aucune réception.' }, { key: 'factures', title: 'Factures d\'achat', doctype: 'Purchase Invoice', fiche: 'FactureAchatFiche', rows: commande.factures, empty: 'Aucune facture.' }].filter((item) => item.rows)" :key="group.key" class="card ref-card">
									<h3>{{ group.title }}</h3>
									<p v-if="!group.rows!.length" class="text-ink-gray-6">{{ group.empty }}</p>
									<div v-else class="ref-scroll"><table class="ref-table">
										<thead><tr><th>Numéro</th><th>Date</th><th>Statut</th><th class="end">Total (DA)</th></tr></thead>
										<tbody><tr v-for="row in group.rows!" :key="row.name"><td><RouterLink v-if="hasFiche(group.fiche)" class="ref-link" :to="{ name: group.fiche, params: { id: row.name } }">{{ row.name }}</RouterLink><a v-else class="ref-link" :href="deskUrl(group.doctype, row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td><StatusPill :status="row.status" /></td><td class="end tabular-nums">{{ formatAmount(row.total) }}</td></tr></tbody>
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

		<AchatDialog v-if="editing && commande" kind="commande" :piece="commande" @close="editing = false" @saved="(piece) => onSaved(piece as CommandeAchatDetail)" />

		<FormDialog v-if="confirming && commande" :title="confirming !== 'supprimer' ? 'Annuler la commande' : commande.docstatus === 2 ? 'Supprimer la pièce annulée' : 'Supprimer le brouillon'" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour confirmer" @close="confirming = null" @submit="confirm">
			<p>{{ confirming !== 'supprimer' ? `La commande d'achat ${commande.name} sera annulée. ERPNext refuse si une réception ou une facture validée en dépend.` : commande.docstatus === 2 ? `La pièce annulée ${commande.name} sera supprimée définitivement. Frappe refuse si une pièce non annulée la cite encore, par exemple sa nouvelle version.` : `Le brouillon ${commande.name} sera supprimé définitivement.` }}</p>
			<template #actions>
				<button v-if="confirming === 'annuler' && canCreate('Purchase Order')" type="button" class="btn-secondary" :disabled="busy" @click="(confirming = 'annuler_version'), confirm()">Annuler et créer une nouvelle version</button>
				<button type="button" class="btn-primary" :disabled="busy" @click="confirm">{{ confirming !== 'supprimer' ? 'Annuler la commande' : 'Supprimer' }}</button>
			</template>
		</FormDialog>

		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
		<AppToast :message="created?.label ?? ''" :duration="0" @close="created = null">
			<template v-if="created">
				<RouterLink v-if="hasFiche(created.doctype === 'Purchase Receipt' ? 'ReceptionFiche' : 'FactureAchatFiche')" class="app-toast-action" :to="{ name: created.doctype === 'Purchase Receipt' ? 'ReceptionFiche' : 'FactureAchatFiche', params: { id: created.name } }" @click="created = null">{{ created.doctype === 'Purchase Receipt' ? 'Préparer la réception' : 'Ouvrir la facture' }}</RouterLink>
				<a v-else class="app-toast-action" :href="deskUrl(created.doctype, created.name)" target="_blank" rel="noopener noreferrer" @click="created = null">Ouvrir sur le Desk</a>
			</template>
		</AppToast>
	</main>
</template>
