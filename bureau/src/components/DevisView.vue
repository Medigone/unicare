<script setup lang="ts">
import { useRouter } from 'vue-router'
import { computed, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideBuilding2 from '~icons/lucide/building-2'
import LucideCalendar from '~icons/lucide/calendar'
import LucideCalendarClock from '~icons/lucide/calendar-clock'
import LucideDownload from '~icons/lucide/download'
import LucidePrinter from '~icons/lucide/printer'
import LucideUser from '~icons/lucide/user'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FormDialog from '@shared/components/FormDialog.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import VersionsCard from './VersionsCard.vue'
import VenteDialog from './VenteDialog.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import { createDevisCommande, deleteDevis, devisActivity, devisPdfUrl, devisPrintUrl, markDevisLost, runDevisAction } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { dayFromToday, type DevisDetail } from '@/lib/devis'
import { confirmAction } from '@/lib/confirm'
import { createPieceVersion } from '@/lib/api'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { useDevis } from '@/lib/useDevis'

const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: []; deleted: [] }>()

const { devis, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useDevis(
	() => props.id,
	() => emit('changed'),
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => devisActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, devis })

const can = (action: string) => Boolean(devis.value?.actions.includes(action as never))
const today = dayFromToday(0)
const expired = computed(() => Boolean(devis.value?.valable && devis.value.valable < today && devis.value.docstatus === 1))

async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

// Modification du brouillon.
const editing = ref(false)
function onSaved(updated: DevisDetail) {
	devis.value = updated
	notice.value = 'Devis enregistré.'
	emit('changed')
}

// Valider : le serveur refuse s'il reste un blocage, la fiche l'affiche déjà.
async function valider() {
	const current = devis.value
	if (!current || !(await confirmAction({ title: 'Valider le devis', message: `Le devis ${current.name} sera validé : il ne pourra plus être modifié.`, confirmLabel: 'Valider le devis' }))) return
	if (current && (await perform(() => runDevisAction(current, 'valider')))) notice.value = 'Devis validé.'
}

// Confirmations : annuler un devis validé, supprimer un brouillon.
const confirming = ref<'annuler' | 'annuler_version' | 'supprimer' | null>(null)
async function confirm() {
	const current = devis.value
	const action = confirming.value
	if (!current || !action) return
	if (action === 'annuler' || action === 'annuler_version') {
		const cancelled = await perform(() => runDevisAction(current, 'annuler'))
		if (cancelled) notice.value = 'Devis annulé.'
		confirming.value = null
		if (cancelled && action === 'annuler_version') await nouvelleVersion(true)
		return
	}
	busy.value = true
	try {
		await deleteDevis(current)
		confirming.value = null
		emit('deleted')
	} catch (e) {
		actionError.value = (e as Error).message
		confirming.value = null
	} finally {
		busy.value = false
	}
}

// Perdu, avec sa raison.
const losing = ref(false)
const lost = ref({ raison: '', precisions: '' })
const lostError = ref('')
async function declareLost() {
	const current = devis.value
	if (!current) return
	if (!lost.value.raison) {
		lostError.value = 'Choisissez une raison.'
		return
	}
	if (await perform(() => markDevisLost(current, lost.value.raison, lost.value.precisions.trim()))) {
		losing.value = false
		notice.value = 'Devis déclaré perdu.'
	}
}

// Commande : une date de livraison, puis la commande en brouillon s'ouvre sur le Desk.
const ordering = ref(false)
const livraison = ref(dayFromToday(7))
const createdCommande = ref<string | null>(null)
async function createCommande() {
	const current = devis.value
	if (!current || !livraison.value) return
	let name = ''
	const done = await perform(async () => {
		const result = await createDevisCommande(current, livraison.value)
		name = result.commande
		return result.devis
	})
	if (done) {
		ordering.value = false
		createdCommande.value = name
	}
}
// Versions : une pièce annulée se refait en nouvelle version (brouillon NOM-1), comme « Modifier » sur le Desk.
const versionRouter = useRouter()
async function nouvelleVersion(confirmed = false) {
	const current = devis.value
	if (!current) return
	if (!confirmed && !(await confirmAction({ title: 'Nouvelle version', message: `Une nouvelle version de ${current.name} sera créée en brouillon, avec le même contenu : vous la corrigerez puis la validerez.`, confirmLabel: 'Créer la nouvelle version' }))) return
	busy.value = true
	actionError.value = ''
	try {
		const result = await createPieceVersion('devis', current)
		emit('changed')
		await versionRouter.push({ name: 'DevisFiche', params: { id: result.name } })
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
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Ce devis n'existe pas ou n'existe plus.</div>
		<div v-else-if="!devis" class="card p-8 text-center text-ink-gray-6">Chargement du devis…</div>

		<template v-else>
			<RecordHeader>
				<template #title><span class="tabular-nums">{{ devis.name }}</span></template>
				<template #flags><StatusPill :status="devis.status" /></template>
				<template #sub>
					<RouterLink class="ref-link" :to="{ name: 'Client', params: { id: devis.client } }">{{ devis.client_label }}</RouterLink>
					<span class="tabular-nums">{{ formatAmount(devis.total_ttc) }} DA TTC</span>
					<div><TagEditor doctype="Quotation" :name="devis.name" :modified="devis.modified" :tags="devis.tags" :can-edit="true" @changed="(tags) => (devis!.tags = tags)" /></div>
				</template>
				<template #actions>
					<button v-if="can('nouvelle_version')" type="button" class="btn-primary" :disabled="busy" @click="nouvelleVersion()">Nouvelle version</button>
					<button v-if="can('valider')" type="button" class="btn-primary" :disabled="busy || devis.blocked.length > 0" :title="devis.blocked.join(' ') || undefined" @click="valider">Valider</button>
					<button v-if="can('commande')" type="button" class="btn-primary" :disabled="busy" @click="ordering = true">Créer la commande</button>
					<button v-if="can('modifier')" type="button" class="btn-secondary" :disabled="busy" @click="editing = true">Modifier</button>
					<button v-if="can('perdu')" type="button" class="btn-secondary" :disabled="busy" @click="(losing = true), (lostError = '')">Perdu</button>
					<MoreMenu>
						<template v-if="devis.can_print">
							<a class="app-menu-item" role="menuitem" :href="devisPrintUrl(devis.name)" target="_blank" rel="noopener noreferrer"><LucidePrinter class="h-3.5 w-3.5" aria-hidden="true" />Imprimer</a>
							<a class="app-menu-item" role="menuitem" :href="devisPdfUrl(devis.name)"><LucideDownload class="h-3.5 w-3.5" aria-hidden="true" />Télécharger le PDF</a>
							<div class="app-menu-sep"></div>
						</template>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Quotation', devis.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="can('annuler') || can('supprimer')">
							<div class="app-menu-sep"></div>
							<button v-if="can('annuler')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'annuler'">Annuler le devis</button>
							<button v-if="can('supprimer')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'supprimer'">{{ devis.docstatus === 2 ? 'Supprimer la pièce annulée' : 'Supprimer le brouillon' }}</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations du devis">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucideBuilding2 aria-hidden="true" />Client</dt><dd><RouterLink class="ref-link" :to="{ name: 'Client', params: { id: devis.client } }">{{ devis.client_label }}</RouterLink></dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Date</dt><dd class="tabular-nums">{{ formatDay(devis.date) || '—' }}</dd></div>
							<div><dt><LucideCalendarClock aria-hidden="true" />Valable jusqu'au</dt><dd class="tabular-nums" :class="expired && 'text-tone-red'">{{ formatDay(devis.valable) || '—' }}</dd></div>
							<div><dt><LucideUser aria-hidden="true" />Créé par</dt><dd>{{ devis.cree_par }}</dd></div>
						</dl>
					</div>
				</aside>

				<div class="client-main">
					<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
					<div class="bureau-detail">
						<div class="bureau-center">
							<VersionsCard :versions="devis.versions" :docstatus="devis.docstatus" fiche="DevisFiche" :can-amend="can('nouvelle_version')" />
							<div v-if="devis.blocked.length" role="status" class="rounded-control tone-amber px-3.5 py-2.5">
								<strong class="font-semibold">Pas encore validable :</strong> {{ devis.blocked.join(' ') }}
								<button v-if="can('modifier')" type="button" class="font-medium underline" @click="editing = true">Modifier le devis</button>
							</div>
							<div v-if="devis.perte" role="status" class="rounded-control tone-red px-3.5 py-2.5">
								<strong class="font-semibold">Perdu :</strong> {{ devis.perte.raisons.join(', ') || 'raison non précisée' }}<template v-if="devis.perte.precisions"> · {{ devis.perte.precisions }}</template>
							</div>

							<section class="card ref-card">
								<h3>Lignes</h3>
								<p v-if="!devis.lignes.length" class="text-ink-gray-6">Aucune ligne.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Article</th><th class="end">Quantité</th><th class="end">Prix HT (DA)</th><th class="end">Montant HT (DA)</th></tr></thead>
									<tbody>
										<tr v-for="line in devis.lignes" :key="line.name">
											<td>
												<RouterLink class="ref-link" :to="{ name: 'Article', params: { id: line.article } }">{{ line.designation }}</RouterLink>
												<span class="ml-1 text-xs tabular-nums text-ink-gray-6">{{ line.article }}</span>
												<span v-if="line.description" class="block text-sm text-ink-gray-7">{{ line.description }}</span>
											</td>
											<td class="end tabular-nums">{{ formatQty(line.quantite) }} {{ line.unite }}</td>
											<td class="end tabular-nums" :class="!line.prix && 'font-semibold text-tone-amber'">
												{{ line.prix ? formatAmount(line.prix) : 'Sans prix' }}
												<span v-if="line.prix && line.prix_tarif && line.prix !== line.prix_tarif" class="block text-xs text-ink-gray-6" :title="'Prix du tarif'">tarif {{ formatAmount(line.prix_tarif) }}</span>
											</td>
											<td class="end tabular-nums">{{ formatAmount(line.montant) }}</td>
										</tr>
									</tbody>
								</table></div>
								<dl class="devis-totaux">
									<div><dt>Total HT</dt><dd class="tabular-nums">{{ formatAmount(devis.total) }} DA</dd></div>
									<div v-for="tax in devis.taxes" :key="tax.description"><dt>{{ tax.description }}</dt><dd class="tabular-nums">{{ formatAmount(tax.montant) }} DA</dd></div>
									<div class="devis-total-ttc"><dt>Total TTC</dt><dd class="tabular-nums">{{ formatAmount(devis.arrondi ?? devis.total_ttc) }} DA</dd></div>
								</dl>
								<p v-if="devis.en_lettres" class="text-sm text-ink-gray-6">{{ devis.en_lettres }}</p>
							</section>

							<section v-if="devis.commandes" class="card ref-card">
								<h3>Commandes</h3>
								<p v-if="!devis.commandes.length" class="text-ink-gray-6">{{ can('commande') ? 'Aucune commande : « Créer la commande » la prépare en brouillon.' : 'Aucune commande depuis ce devis.' }}</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Commande</th><th>Date</th><th>Livraison</th><th>Statut</th><th class="end">Total TTC (DA)</th></tr></thead>
									<tbody><tr v-for="row in devis.commandes" :key="row.name"><td><RouterLink class="ref-link" :to="{ name: 'CommandeFiche', params: { id: row.name } }">{{ row.name }}</RouterLink></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td class="tabular-nums">{{ formatDay(row.livraison) || '—' }}</td><td><StatusPill :status="row.status" /></td><td class="end tabular-nums">{{ formatAmount(row.total) }}</td></tr></tbody>
								</table></div>
							</section>
						</div>

						<aside class="record-activity" aria-label="Commentaires et activité du devis">
							<ActivityFeed ref="feed" :api="activityApi" :version="devis.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<VenteDialog v-if="editing && devis" kind="devis" :piece="devis" @close="editing = false" @saved="(piece) => onSaved(piece as DevisDetail)" />

		<FormDialog v-if="losing && devis" title="Déclarer le devis perdu" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour confirmer" @close="losing = false" @submit="declareLost">
			<div class="form-field">
				<label class="field-label" for="devis-raison">Raison <span class="req">obligatoire</span></label>
				<select v-search id="devis-raison" v-model="lost.raison" class="field-input" :aria-invalid="Boolean(lostError)" @change="lostError = ''">
					<option value="">Choisir…</option>
					<option v-for="item in devis.raisons_perte" :key="item" :value="item">{{ item }}</option>
				</select>
				<p v-if="lostError" class="field-error" role="alert">{{ lostError }}</p>
				<p v-else-if="!devis.raisons_perte.length" class="field-note"><span>Aucune raison n'est définie : ajoutez-en sur le Desk (Quotation Lost Reason).</span></p>
			</div>
			<div class="form-field">
				<label class="field-label" for="devis-precisions">Précisions</label>
				<textarea id="devis-precisions" v-model="lost.precisions" class="field-input" rows="3" placeholder="Concurrent retenu, prix proposé…"></textarea>
			</div>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="declareLost">Déclarer perdu</button>
			</template>
		</FormDialog>

		<FormDialog v-if="ordering && devis" title="Créer la commande client" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour créer" @close="ordering = false" @submit="createCommande">
			<p class="text-sm">La commande reprend les lignes restant à commander, en brouillon : elle se vérifie et se valide ensuite depuis sa fiche.</p>
			<div class="form-field">
				<label class="field-label" for="devis-livraison">Date de livraison <span class="req">obligatoire</span></label>
				<input id="devis-livraison" v-model="livraison" class="field-input tabular-nums" type="date" :min="today" />
			</div>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy || !livraison" @click="createCommande">{{ busy ? 'Création…' : 'Créer la commande' }}</button>
			</template>
		</FormDialog>

		<FormDialog v-if="confirming && devis" :title="confirming !== 'supprimer' ? 'Annuler le devis' : devis.docstatus === 2 ? 'Supprimer la pièce annulée' : 'Supprimer le brouillon'" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour confirmer" @close="confirming = null" @submit="confirm">
			<p>{{ confirming !== 'supprimer' ? `Le devis ${devis.name} sera annulé : il reste lisible mais ne peut plus être commandé.` : devis.docstatus === 2 ? `La pièce annulée ${devis.name} sera supprimée définitivement. Frappe refuse si une pièce non annulée la cite encore, par exemple sa nouvelle version.` : `Le brouillon ${devis.name} sera supprimé définitivement.` }}</p>
			<template #actions>
				<button v-if="confirming === 'annuler' && canCreate('Quotation')" type="button" class="btn-secondary" :disabled="busy" @click="(confirming = 'annuler_version'), confirm()">Annuler et créer une nouvelle version</button>
				<button type="button" class="btn-primary" :disabled="busy" @click="confirm">{{ confirming !== 'supprimer' ? 'Annuler le devis' : 'Supprimer' }}</button>
			</template>
		</FormDialog>

		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
		<AppToast :message="createdCommande ? `Commande ${createdCommande} créée en brouillon.` : ''" :duration="0" @close="createdCommande = null">
			<RouterLink class="app-toast-action" :to="{ name: 'CommandeFiche', params: { id: createdCommande ?? '' } }" @click="createdCommande = null">Ouvrir la commande</RouterLink>
		</AppToast>
	</main>
</template>
