<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideBuilding2 from '~icons/lucide/building-2'
import LucideCalendar from '~icons/lucide/calendar'
import LucideHash from '~icons/lucide/hash'
import LucidePrinter from '~icons/lucide/printer'
import LucideShoppingCart from '~icons/lucide/shopping-cart'
import LucideUndo2 from '~icons/lucide/undo-2'
import LucideUser from '~icons/lucide/user'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FormDialog from '@shared/components/FormDialog.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import VersionsCard from './VersionsCard.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import { createReceptionSuivante, deleteReception, prepareReception, receptionActivity, receptionPrintUrl, runReceptionAction } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { confirmAction } from '@/lib/confirm'
import { createPieceVersion } from '@/lib/api'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { changedReceptionPrep, fillDepot, receptionPrepLines, type ReceptionLine, type ReceptionPrep } from '@/lib/receptions'
import { useReception } from '@/lib/useReception'

const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: []; deleted: []; open: [name: string] }>()

const { reception: livraison, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useReception(
	() => props.id,
	() => emit('changed'),
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => receptionActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	// Une préparation en cours n'est pas écrasée par un changement venu d'ailleurs : la sauvegarde le signalera.
	if (prepDirty.value) return
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, livraison })

// Les pièces qui ont déjà leur fiche dans le bureau ; les autres s'ouvrent sur le Desk.
const router = useRouter()
const hasFiche = (name: string) => router.hasRoute(name)
const can = (action: string) => Boolean(livraison.value?.actions.includes(action as never))
const preparing = computed(() => can('preparer'))

// Préparation : une copie des lignes, remise à zéro à chaque version reçue du serveur.
const prep = ref<ReceptionPrep[]>([])
const prepInitial = ref<ReceptionPrep[]>([])
const blFournisseur = ref('')
const transport = ref('')
watch(
	() => livraison.value?.modified,
	() => {
		const current = livraison.value
		if (!current) return
		prepInitial.value = receptionPrepLines(current)
		prep.value = receptionPrepLines(current)
		blFournisseur.value = current.bl_fournisseur ?? ''
		transport.value = current.transport ?? ''
	},
	{ immediate: true },
)
const prepChanges = computed(() => changedReceptionPrep(prepInitial.value, prep.value))
const headerChanged = computed(() => blFournisseur.value.trim() !== (livraison.value?.bl_fournisseur ?? '') || transport.value.trim() !== (livraison.value?.transport ?? ''))
const prepDirty = computed(() => prepChanges.value.length > 0 || headerChanged.value)
const missingDepot = computed(() => (livraison.value?.lignes ?? []).some((line, index) => line.stock && !prep.value[index]?.depot))
const defaultDepot = ref('')

function lineOf(entry: ReceptionPrep) {
	return livraison.value?.lignes.find((line) => line.name === entry.name) as ReceptionLine
}
function applyDepot() {
	if (defaultDepot.value) prep.value = fillDepot(prep.value, defaultDepot.value)
}
async function savePrep() {
	const current = livraison.value
	if (!current) return false
	const lignes = prepChanges.value
	if (!lignes.length && !headerChanged.value) return true
	if (lignes.some((line) => line.quantite !== undefined && !Number.isFinite(line.quantite))) {
		actionError.value = 'Une quantité est illisible.'
		return false
	}
	const done = await perform(() => prepareReception(current, lignes, headerChanged.value ? blFournisseur.value.trim() : undefined, headerChanged.value ? transport.value.trim() : undefined))
	if (done) notice.value = 'Préparation enregistrée.'
	return done
}
async function valider() {
	const current = livraison.value
	if (!current) return
	if (!(await confirmAction({ title: current.retour ? 'Valider le retour' : 'Valider la réception', message: current.retour ? `Le retour ${current.name} sera validé : la marchandise sort du stock.` : `La réception ${current.name} sera validée : la marchandise entre en stock et la commande avance.`, confirmLabel: current.retour ? 'Valider le retour' : 'Valider la réception' }))) return
	if (prepDirty.value && !(await savePrep())) return
	const saved = livraison.value
	if (!saved || saved.blocked.length) return
	if (await perform(() => runReceptionAction(saved, 'valider'))) notice.value = saved.retour ? 'Retour validé : le stock est sorti.' : 'Réception validée : le stock est entré.'
}

async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

// Facture d'achat ou retour fournisseur (une réception à quantités négatives, préparée ici).
const created = ref<{ doctype: string; name: string; label: string } | null>(null)
async function createNext(kind: 'facture' | 'retour') {
	const current = livraison.value
	if (!current) return
	const [title, message] = kind === 'facture' ? ['Créer la facture d\'achat', `La facture d'achat de la réception ${current.name} sera créée en brouillon.`] : ['Créer le retour fournisseur', `Un retour fournisseur sera créé en brouillon sur ${current.name} : vous y saisirez les quantités rendues.`]
	if (!(await confirmAction({ title, message, confirmLabel: title }))) return
	let result: { doctype: string; name: string; note: string | null } | null = null
	const done = await perform(async () => {
		const response = await createReceptionSuivante(current, kind)
		result = response
		return response.reception
	})
	if (done && result) {
		const { doctype, name, note } = result
		created.value = { doctype, name, label: [kind === 'facture' ? `Facture d'achat ${name} créée en brouillon : saisissez le n° du fournisseur puis validez-la.` : `Retour fournisseur ${name} créé : saisissez les quantités rendues.`, note].filter(Boolean).join(' ') }
	}
}

const confirming = ref<'annuler' | 'annuler_version' | 'supprimer' | null>(null)
async function confirm() {
	const current = livraison.value
	const action = confirming.value
	if (!current || !action) return
	if (action === 'annuler' || action === 'annuler_version') {
		const cancelled = await perform(() => runReceptionAction(current, 'annuler'))
		if (cancelled) notice.value = 'Réception annulée : le stock est ressorti.'
		confirming.value = null
		if (cancelled && action === 'annuler_version') await nouvelleVersion(true)
		return
	}
	busy.value = true
	try {
		await deleteReception(current)
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
	const current = livraison.value
	if (!current) return
	if (!confirmed && !(await confirmAction({ title: 'Nouvelle version', message: `Une nouvelle version de ${current.name} sera créée en brouillon, avec le même contenu : vous la corrigerez puis la validerez.`, confirmLabel: 'Créer la nouvelle version' }))) return
	busy.value = true
	actionError.value = ''
	try {
		const result = await createPieceVersion('receptions', current)
		emit('changed')
		await versionRouter.push({ name: 'ReceptionFiche', params: { id: result.name } })
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
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Cette réception n'existe pas ou n'existe plus.</div>
		<div v-else-if="!livraison" class="card p-8 text-center text-ink-gray-6">Chargement de la réception…</div>

		<template v-else>
			<RecordHeader>
				<template #title><span class="tabular-nums">{{ livraison.name }}</span></template>
				<template #flags>
					<StatusPill :status="livraison.status" />
					<span v-if="livraison.retour" class="record-flag">Retour</span>
				</template>
				<template #sub>
					<RouterLink class="ref-link" :to="{ name: 'Fournisseur', params: { id: livraison.fournisseur } }">{{ livraison.fournisseur_label }}</RouterLink>
					<span class="tabular-nums">{{ formatAmount(livraison.total_ttc) }} DA TTC</span>
					<div><TagEditor doctype="Purchase Receipt" :name="livraison.name" :modified="livraison.modified" :tags="livraison.tags" :can-edit="true" @changed="(tags) => (livraison!.tags = tags)" /></div>
				</template>
				<template #actions>
					<button v-if="can('nouvelle_version')" type="button" class="btn-primary" :disabled="busy" @click="nouvelleVersion()">Nouvelle version</button>
					<button v-if="preparing && prepDirty" type="button" class="btn-secondary" :disabled="busy" @click="savePrep">Enregistrer</button>
					<button v-if="can('valider')" type="button" class="btn-primary" :disabled="busy || (!prepDirty && livraison.blocked.length > 0)" :title="livraison.blocked.join(' ') || undefined" @click="valider">{{ livraison.retour ? 'Valider le retour' : 'Valider la réception' }}</button>
					<button v-if="can('facture')" type="button" class="btn-primary" :disabled="busy" @click="createNext('facture')">Créer la facture</button>
					<MoreMenu>
						<button v-if="can('retour')" type="button" class="app-menu-item" role="menuitem" :disabled="busy" @click="createNext('retour')"><LucideUndo2 class="h-3.5 w-3.5" aria-hidden="true" />Retour fournisseur</button>
						<div v-if="can('retour')" class="app-menu-sep"></div>
						<template v-if="livraison.can_print">
							<a class="app-menu-item" role="menuitem" :href="receptionPrintUrl(livraison.name)" target="_blank" rel="noopener noreferrer"><LucidePrinter class="h-3.5 w-3.5" aria-hidden="true" />Imprimer</a>
							<div class="app-menu-sep"></div>
						</template>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Purchase Receipt', livraison.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="can('annuler') || can('supprimer')">
							<div class="app-menu-sep"></div>
							<button v-if="can('annuler')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'annuler'">Annuler la réception</button>
							<button v-if="can('supprimer')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'supprimer'">{{ livraison.docstatus === 2 ? 'Supprimer la pièce annulée' : 'Supprimer le brouillon' }}</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations de la réception">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucideBuilding2 aria-hidden="true" />Fournisseur</dt><dd><RouterLink class="ref-link" :to="{ name: 'Fournisseur', params: { id: livraison.fournisseur } }">{{ livraison.fournisseur_label }}</RouterLink></dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Date</dt><dd class="tabular-nums">{{ formatDay(livraison.date) || '—' }}</dd></div>
							<div v-if="livraison.retour_de"><dt><LucideUndo2 aria-hidden="true" />Retour de</dt><dd><button type="button" class="ref-link tabular-nums" @click="emit('open', livraison.retour_de)">{{ livraison.retour_de }}</button></dd></div>
							<div v-if="livraison.commandes.length"><dt><LucideShoppingCart aria-hidden="true" />Commande d'achat</dt><dd><template v-for="(name, index) in livraison.commandes" :key="name">{{ index ? ', ' : '' }}<RouterLink class="ref-link tabular-nums" :to="{ name: 'CommandeAchatFiche', params: { id: name } }">{{ name }}</RouterLink></template></dd></div>
							<div><dt><LucideUser aria-hidden="true" />Créée par</dt><dd>{{ livraison.cree_par }}</dd></div>
						</dl>
					</div>
					<div class="side-block">
						<template v-if="preparing">
							<label class="field-label" for="reception-bl">BL du fournisseur</label>
							<input id="reception-bl" v-model="blFournisseur" class="field-input" placeholder="Nº du bon de livraison reçu" autocomplete="off" />
							<label class="field-label mt-1" for="reception-transport">Nº de transport</label>
							<input id="reception-transport" v-model="transport" class="field-input" placeholder="Lettre de voiture" autocomplete="off" />
						</template>
						<dl v-else class="record-facts">
							<div><dt><LucideHash aria-hidden="true" />BL du fournisseur</dt><dd :class="!livraison.bl_fournisseur && 'record-fact-none'">{{ livraison.bl_fournisseur || 'Non renseigné' }}</dd></div>
							<div><dt>Nº de transport</dt><dd :class="!livraison.transport && 'record-fact-none'">{{ livraison.transport || 'Non renseigné' }}</dd></div>
						</dl>
					</div>
				</aside>

				<div class="client-main">
					<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
					<div class="bureau-detail">
						<div class="bureau-center">
							<VersionsCard :versions="livraison.versions" :docstatus="livraison.docstatus" fiche="ReceptionFiche" :can-amend="can('nouvelle_version')" />
							<div v-if="preparing && livraison.blocked.length && !prepDirty" role="status" class="rounded-control tone-amber px-3.5 py-2.5">
								<strong class="font-semibold">À préparer :</strong> {{ livraison.blocked.join(' ') }}
							</div>
							<div v-if="preparing && prepDirty" role="status" class="rounded-control tone-blue px-3.5 py-2.5">Préparation modifiée : enregistrez-la, ou validez directement (elle sera enregistrée d'abord).</div>

							<!-- Brouillon : chaque ligne se prépare (quantité reçue, dépôt, lot du fournisseur). -->
							<section v-if="preparing" class="card ref-card">
								<div class="ref-card-head">
									<h3>{{ livraison.retour ? 'Quantités rendues' : 'Ce qui est arrivé' }}</h3>
									<span v-if="missingDepot && livraison.depots.length" class="inline-flex items-center gap-1.5">
										<select v-search v-model="defaultDepot" class="field-input" aria-label="Dépôt pour toutes les lignes">
											<option value="">Dépôt pour toutes les lignes…</option>
											<option v-for="depot in livraison.depots" :key="depot" :value="depot">{{ depot }}</option>
										</select>
										<button type="button" class="btn-secondary" :disabled="!defaultDepot" @click="applyDepot">Appliquer</button>
									</span>
								</div>
								<p class="text-sm text-ink-gray-6">{{ livraison.retour ? 'Saisissez en négatif ce qui repart chez le fournisseur (−2 pour deux unités).' : 'Pour chaque ligne, la quantité reçue, le dépôt où elle entre et, pour un article suivi par lots, le n° de lot du fournisseur et sa péremption. Une quantité à 0 retire la ligne : elle reste à recevoir sur la commande.' }}</p>
								<div class="ref-scroll"><table class="ref-table livraison-prep">
									<thead><tr><th>Article</th><th class="end">Quantité</th><th>Dépôt</th><th>Lot fournisseur</th><th>Péremption</th></tr></thead>
									<tbody>
										<tr v-for="(entry, index) in prep" :key="entry.name">
											<td>
												<RouterLink class="ref-link" :to="{ name: 'Article', params: { id: lineOf(entry).article } }">{{ lineOf(entry).designation }}</RouterLink>
												<span class="block text-xs tabular-nums text-ink-gray-6">{{ lineOf(entry).article }}<template v-if="lineOf(entry).commande"> · {{ lineOf(entry).commande }}</template></span>
											</td>
											<td class="end">
												<span class="inline-flex items-center gap-1">
													<input v-model="entry.quantite" class="field-input w-20 text-right tabular-nums" inputmode="decimal" :aria-label="`Quantité, ligne ${index + 1}`" />
													<span class="text-xs text-ink-gray-6">{{ lineOf(entry).unite }}</span>
												</span>
											</td>
											<td>
												<select v-search v-if="lineOf(entry).stock" v-model="entry.depot" class="field-input" :aria-label="`Dépôt, ligne ${index + 1}`" :aria-invalid="!entry.depot">
													<option value="">Choisir…</option>
													<option v-if="entry.depot && !livraison.depots.includes(entry.depot)" :value="entry.depot">{{ entry.depot }}</option>
													<option v-for="depot in livraison.depots" :key="depot" :value="depot">{{ depot }}</option>
												</select>
												<span v-else class="text-ink-gray-6">Hors stock</span>
											</td>
											<td>
												<input v-if="lineOf(entry).avec_lot && !livraison.retour" v-model="entry.lot" class="field-input tabular-nums" :placeholder="lineOf(entry).lot_obligatoire ? 'Obligatoire' : 'Nº de lot'" autocomplete="off" :aria-label="`Lot du fournisseur, ligne ${index + 1}`" :aria-invalid="!entry.lot.trim()" />
												<span v-else-if="lineOf(entry).avec_lot" class="tabular-nums text-ink-gray-6">{{ entry.lot || 'Repris de la réception' }}</span>
												<span v-else class="text-ink-gray-6">—</span>
											</td>
											<td>
												<input v-if="lineOf(entry).avec_lot && !livraison.retour" v-model="entry.peremption" class="field-input tabular-nums" type="date" :aria-label="`Péremption, ligne ${index + 1}`" />
												<span v-else class="text-ink-gray-6">—</span>
											</td>
										</tr>
									</tbody>
								</table></div>
							</section>

							<!-- Réception validée ou annulée : les lignes telles qu'entrées en stock. -->
							<section v-else class="card ref-card">
								<h3>Lignes</h3>
								<div class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Article</th><th class="end">Quantité</th><th>Dépôt</th><th>Lot</th><th class="end">Montant HT (DA)</th></tr></thead>
									<tbody>
										<tr v-for="line in livraison.lignes" :key="line.name">
											<td><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: line.article } }">{{ line.designation }}</RouterLink><span class="ml-1 text-xs tabular-nums text-ink-gray-6">{{ line.article }}</span></td>
											<td class="end tabular-nums">{{ formatQty(line.quantite) }} {{ line.unite }}</td>
											<td>{{ line.depot || livraison.depot || '—' }}</td>
											<td class="tabular-nums">{{ line.lot || '—' }}<span v-if="line.peremption" class="block text-xs text-ink-gray-6">périme le {{ formatDay(line.peremption) }}</span></td>
											<td class="end tabular-nums">{{ formatAmount(line.montant) }}</td>
										</tr>
									</tbody>
								</table></div>
								<dl class="devis-totaux">
									<div><dt>Total HT</dt><dd class="tabular-nums">{{ formatAmount(livraison.total) }} DA</dd></div>
									<div v-if="livraison.total_taxes"><dt>TVA</dt><dd class="tabular-nums">{{ formatAmount(livraison.total_taxes) }} DA</dd></div>
									<div class="devis-total-ttc"><dt>Total TTC</dt><dd class="tabular-nums">{{ formatAmount(livraison.total_ttc) }} DA</dd></div>
								</dl>
							</section>

							<div v-if="livraison.docstatus === 1 && !livraison.retour" class="client-cards">
								<section v-if="livraison.factures" class="card ref-card">
									<h3>Factures d'achat</h3>
									<p v-if="!livraison.factures.length" class="text-ink-gray-6">Aucune facture.</p>
									<div v-else class="ref-scroll"><table class="ref-table">
										<thead><tr><th>Facture</th><th>Date</th><th>Statut</th><th class="end">Total (DA)</th></tr></thead>
										<tbody><tr v-for="row in livraison.factures" :key="row.name"><td><RouterLink v-if="hasFiche('FactureAchatFiche')" class="ref-link" :to="{ name: 'FactureAchatFiche', params: { id: row.name } }">{{ row.name }}</RouterLink><a v-else class="ref-link" :href="deskUrl('Purchase Invoice', row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td><StatusPill :status="row.status" /></td><td class="end tabular-nums">{{ formatAmount(row.total) }}</td></tr></tbody>
									</table></div>
								</section>
								<section class="card ref-card">
									<h3>Retours fournisseur</h3>
									<p v-if="!livraison.retours.length" class="text-ink-gray-6">Aucun retour.</p>
									<div v-else class="ref-scroll"><table class="ref-table">
										<thead><tr><th>Retour</th><th>Date</th><th>Statut</th><th class="end">Total (DA)</th></tr></thead>
										<tbody><tr v-for="row in livraison.retours" :key="row.name"><td><button type="button" class="ref-link tabular-nums" @click="emit('open', row.name)">{{ row.name }}</button></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td><StatusPill :status="row.status" /></td><td class="end tabular-nums">{{ formatAmount(row.total) }}</td></tr></tbody>
									</table></div>
								</section>
							</div>
						</div>

						<aside class="record-activity" aria-label="Commentaires et activité de la réception">
							<ActivityFeed ref="feed" :api="activityApi" :version="livraison.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<FormDialog v-if="confirming && livraison" :title="confirming !== 'supprimer' ? 'Annuler la réception' : livraison.docstatus === 2 ? 'Supprimer la pièce annulée' : 'Supprimer le brouillon'" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour confirmer" @close="confirming = null" @submit="confirm">
			<p>{{ confirming !== 'supprimer' ? `La réception ${livraison.name} sera annulée : le stock ressort et la commande redevient à recevoir. ERPNext refuse si une facture ou un retour validé en dépend, ou si le stock a déjà été consommé.` : livraison.docstatus === 2 ? `La pièce annulée ${livraison.name} sera supprimée définitivement. Frappe refuse si une pièce non annulée la cite encore, par exemple sa nouvelle version.` : `Le brouillon ${livraison.name} sera supprimé ; ses quantités redeviennent à recevoir sur la commande.` }}</p>
			<template #actions>
				<button v-if="confirming === 'annuler' && canCreate('Purchase Receipt')" type="button" class="btn-secondary" :disabled="busy" @click="(confirming = 'annuler_version'), confirm()">Annuler et créer une nouvelle version</button>
				<button type="button" class="btn-primary" :disabled="busy" @click="confirm">{{ confirming !== 'supprimer' ? 'Annuler la réception' : 'Supprimer' }}</button>
			</template>
		</FormDialog>

		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
		<AppToast :message="created?.label ?? ''" :duration="0" @close="created = null">
			<template v-if="created">
				<button v-if="created.doctype === 'Purchase Receipt'" type="button" class="app-toast-action" @click="(emit('open', created.name), (created = null))">Ouvrir le retour</button>
				<RouterLink v-else-if="hasFiche('FactureAchatFiche')" class="app-toast-action" :to="{ name: 'FactureAchatFiche', params: { id: created.name } }" @click="created = null">Ouvrir la facture</RouterLink>
				<a v-else class="app-toast-action" :href="deskUrl('Purchase Invoice', created.name)" target="_blank" rel="noopener noreferrer" @click="created = null">Ouvrir sur le Desk</a>
			</template>
		</AppToast>
	</main>
</template>
