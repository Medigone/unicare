<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideBuilding2 from '~icons/lucide/building-2'
import LucideCalendar from '~icons/lucide/calendar'
import LucideDownload from '~icons/lucide/download'
import LucideMapPin from '~icons/lucide/map-pin'
import LucidePrinter from '~icons/lucide/printer'
import LucideShoppingCart from '~icons/lucide/shopping-cart'
import LucideSparkles from '~icons/lucide/sparkles'
import LucideUndo2 from '~icons/lucide/undo-2'
import LucideUser from '~icons/lucide/user'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FormDialog from '@shared/components/FormDialog.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import { createLivraisonSuivante, deleteLivraison, livraisonActivity, livraisonPdfUrl, livraisonPrintUrl, prepareLivraison, runLivraisonAction } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { deskUrl, formatDay } from '@/lib/display'
import { changedPrep, lotsFor, prepLines, suggestLots, type LivraisonLine, type PrepLine } from '@/lib/livraisons'
import { useLivraison } from '@/lib/useLivraison'

const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: []; deleted: []; open: [name: string] }>()

const { livraison, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useLivraison(
	() => props.id,
	() => emit('changed'),
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => livraisonActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	// Une préparation en cours n'est pas écrasée par un changement venu d'ailleurs : la sauvegarde le signalera.
	if (prepDirty.value) return
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, livraison })

const can = (action: string) => Boolean(livraison.value?.actions.includes(action as never))
const preparing = computed(() => can('preparer'))

// Préparation : une copie des lignes, remise à zéro à chaque version reçue du serveur.
const prep = ref<PrepLine[]>([])
const prepInitial = ref<PrepLine[]>([])
const transport = ref('')
const vehicule = ref('')
watch(
	() => livraison.value?.modified,
	() => {
		const current = livraison.value
		if (!current) return
		prepInitial.value = prepLines(current)
		prep.value = prepLines(current)
		transport.value = current.transport ?? ''
		vehicule.value = current.vehicule ?? ''
	},
	{ immediate: true },
)
const prepChanges = computed(() => changedPrep(prepInitial.value, prep.value))
const prepDirty = computed(() => prepChanges.value.length > 0 || transport.value.trim() !== (livraison.value?.transport ?? '') || vehicule.value.trim() !== (livraison.value?.vehicule ?? ''))
const missingLots = computed(() => (livraison.value?.lignes ?? []).some((line, index) => line.stock && ((line.avec_lot && !prep.value[index]?.lot) || !prep.value[index]?.depot)))

function lineOf(entry: PrepLine) {
	return livraison.value?.lignes.find((line) => line.name === entry.name) as LivraisonLine
}
function depotsFor(line: LivraisonLine, current: string) {
	const depots = line.depots ?? []
	return current && !depots.some((item) => item.depot === current) ? [{ depot: current, qty: 0 }, ...depots] : depots
}
function onDepot(entry: PrepLine) {
	// Changer de dépôt : le lot choisi n'y est peut-être plus, on repropose le meilleur.
	const line = lineOf(entry)
	if (line.avec_lot && !lotsFor(line, entry.depot).some((item) => item.lot === entry.lot)) entry.lot = ''
}
function suggest() {
	const current = livraison.value
	if (current) prep.value = suggestLots(current.lignes, prep.value)
}
function lotLabel(lot: { lot: string; qty: number; peremption: string | null }) {
	return `${lot.lot} · ${formatQty(lot.qty)} dispo${lot.peremption ? ` · périme le ${formatDay(lot.peremption)}` : ''}`
}
async function savePrep() {
	const current = livraison.value
	if (!current) return false
	const lignes = prepChanges.value
	const unchangedTransport = transport.value.trim() === (current.transport ?? '') && vehicule.value.trim() === (current.vehicule ?? '')
	if (!lignes.length && unchangedTransport) return true
	if (lignes.some((line) => line.quantite !== undefined && !Number.isFinite(line.quantite))) {
		actionError.value = 'Une quantité est illisible.'
		return false
	}
	const done = await perform(() => prepareLivraison(current, lignes, unchangedTransport ? undefined : transport.value.trim(), unchangedTransport ? undefined : vehicule.value.trim()))
	if (done) notice.value = 'Préparation enregistrée.'
	return done
}
async function valider() {
	if (prepDirty.value && !(await savePrep())) return
	const current = livraison.value
	if (!current || current.blocked.length) return
	if (await perform(() => runLivraisonAction(current, 'valider'))) notice.value = current.retour ? 'Retour validé : le stock est rentré.' : 'Bon validé : le stock est sorti.'
}

async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

// Facture (sur le Desk) ou retour (un bon de livraison, préparé ici).
const created = ref<{ doctype: string; name: string; label: string } | null>(null)
async function createNext(kind: 'facture' | 'retour') {
	const current = livraison.value
	if (!current) return
	let result: { doctype: string; name: string } | null = null
	const done = await perform(async () => {
		const response = await createLivraisonSuivante(current, kind)
		result = response
		return response.livraison
	})
	if (done && result) {
		const { doctype, name } = result
		created.value = { doctype, name, label: kind === 'facture' ? `Facture ${name} créée en brouillon : vérifiez-la puis validez-la.` : `Bon de retour ${name} créé : saisissez les quantités rendues.` }
	}
}

const confirming = ref<'annuler' | 'supprimer' | null>(null)
async function confirm() {
	const current = livraison.value
	const action = confirming.value
	if (!current || !action) return
	if (action === 'annuler') {
		if (await perform(() => runLivraisonAction(current, 'annuler'))) notice.value = 'Bon annulé : le stock est revenu.'
		confirming.value = null
		return
	}
	busy.value = true
	try {
		await deleteLivraison(current)
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
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Ce bon n'existe pas ou n'existe plus.</div>
		<div v-else-if="!livraison" class="card p-8 text-center text-ink-gray-6">Chargement du bon…</div>

		<template v-else>
			<RecordHeader>
				<template #title><span class="tabular-nums">{{ livraison.name }}</span></template>
				<template #flags>
					<StatusPill :status="livraison.status" />
					<span v-if="livraison.retour" class="record-flag">Retour</span>
				</template>
				<template #sub>
					<RouterLink class="ref-link" :to="{ name: 'Client', params: { id: livraison.client } }">{{ livraison.client_label }}</RouterLink>
					<span class="tabular-nums">{{ formatAmount(livraison.total_ttc) }} DA TTC</span>
					<div><TagEditor doctype="Delivery Note" :name="livraison.name" :modified="livraison.modified" :tags="livraison.tags" :can-edit="true" @changed="(tags) => (livraison!.tags = tags)" /></div>
				</template>
				<template #actions>
					<button v-if="preparing && prepDirty" type="button" class="btn-secondary" :disabled="busy" @click="savePrep">Enregistrer</button>
					<button v-if="can('valider')" type="button" class="btn-primary" :disabled="busy || (!prepDirty && livraison.blocked.length > 0)" :title="livraison.blocked.join(' ') || undefined" @click="valider">{{ livraison.retour ? 'Valider le retour' : 'Valider la livraison' }}</button>
					<button v-if="can('facture')" type="button" class="btn-primary" :disabled="busy" @click="createNext('facture')">Créer la facture</button>
					<MoreMenu>
						<button v-if="can('retour')" type="button" class="app-menu-item" role="menuitem" :disabled="busy" @click="createNext('retour')"><LucideUndo2 class="h-3.5 w-3.5" aria-hidden="true" />Retour client</button>
						<div v-if="can('retour')" class="app-menu-sep"></div>
						<template v-if="livraison.can_print">
							<a class="app-menu-item" role="menuitem" :href="livraisonPrintUrl(livraison.name)" target="_blank" rel="noopener noreferrer"><LucidePrinter class="h-3.5 w-3.5" aria-hidden="true" />Imprimer</a>
							<a class="app-menu-item" role="menuitem" :href="livraisonPdfUrl(livraison.name)"><LucideDownload class="h-3.5 w-3.5" aria-hidden="true" />Télécharger le PDF</a>
							<div class="app-menu-sep"></div>
						</template>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Delivery Note', livraison.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="can('annuler') || can('supprimer')">
							<div class="app-menu-sep"></div>
							<button v-if="can('annuler')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'annuler'">Annuler le bon</button>
							<button v-if="can('supprimer')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'supprimer'">Supprimer le brouillon</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations du bon">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucideBuilding2 aria-hidden="true" />Client</dt><dd><RouterLink class="ref-link" :to="{ name: 'Client', params: { id: livraison.client } }">{{ livraison.client_label }}</RouterLink></dd></div>
							<div v-if="livraison.adresse"><dt><LucideMapPin aria-hidden="true" />Adresse</dt><dd class="whitespace-pre-line font-normal">{{ livraison.adresse }}</dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Date</dt><dd class="tabular-nums">{{ formatDay(livraison.date) || '—' }}</dd></div>
							<div v-if="livraison.retour_de"><dt><LucideUndo2 aria-hidden="true" />Retour du bon</dt><dd><button type="button" class="ref-link tabular-nums" @click="emit('open', livraison.retour_de)">{{ livraison.retour_de }}</button></dd></div>
							<div v-if="livraison.commandes.length"><dt><LucideShoppingCart aria-hidden="true" />Commande</dt><dd><template v-for="(name, index) in livraison.commandes" :key="name">{{ index ? ', ' : '' }}<RouterLink class="ref-link tabular-nums" :to="{ name: 'CommandeFiche', params: { id: name } }">{{ name }}</RouterLink></template></dd></div>
							<div><dt><LucideUser aria-hidden="true" />Créé par</dt><dd>{{ livraison.cree_par }}</dd></div>
						</dl>
					</div>
					<div class="side-block">
						<template v-if="preparing">
							<label class="field-label" for="livraison-transport">Nº de transport</label>
							<input id="livraison-transport" v-model="transport" class="field-input" placeholder="Lettre de voiture" autocomplete="off" />
							<label class="field-label mt-1" for="livraison-vehicule">Véhicule</label>
							<input id="livraison-vehicule" v-model="vehicule" class="field-input" placeholder="Immatriculation" autocomplete="off" />
						</template>
						<dl v-else class="record-facts">
							<div><dt>Nº de transport</dt><dd :class="!livraison.transport && 'record-fact-none'">{{ livraison.transport || 'Non renseigné' }}</dd></div>
							<div><dt>Véhicule</dt><dd :class="!livraison.vehicule && 'record-fact-none'">{{ livraison.vehicule || 'Non renseigné' }}</dd></div>
						</dl>
					</div>
				</aside>

				<div class="client-main">
					<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
					<div class="bureau-detail">
						<div class="bureau-center">
							<div v-if="preparing && livraison.blocked.length && !prepDirty" role="status" class="rounded-control tone-amber px-3.5 py-2.5">
								<strong class="font-semibold">À préparer :</strong> {{ livraison.blocked.join(' ') }}
							</div>
							<div v-if="preparing && prepDirty" role="status" class="rounded-control tone-blue px-3.5 py-2.5">Préparation modifiée : enregistrez-la, ou validez directement (elle sera enregistrée d'abord).</div>

							<!-- Brouillon : chaque ligne se prépare (dépôt, lot, quantité). -->
							<section v-if="preparing" class="card ref-card">
								<div class="ref-card-head">
									<h3>{{ livraison.retour ? 'Quantités rendues' : 'Préparation' }}</h3>
									<button v-if="!livraison.retour && missingLots" type="button" class="btn-secondary" @click="suggest"><LucideSparkles class="h-3.5 w-3.5" aria-hidden="true" />Proposer les lots</button>
								</div>
								<p class="text-sm text-ink-gray-6">{{ livraison.retour ? 'Saisissez en négatif ce que le client rend (−2 pour deux unités), et le dépôt où la marchandise rentre.' : 'Pour chaque ligne, le dépôt d\'où part la marchandise et le lot. Les lots les plus proches de leur péremption sont proposés en premier ; une quantité à 0 retire la ligne du bon.' }}</p>
								<div class="ref-scroll"><table class="ref-table livraison-prep">
									<thead><tr><th>Article</th><th class="end">Quantité</th><th>Dépôt</th><th>Lot</th></tr></thead>
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
												<select v-if="lineOf(entry).stock" v-model="entry.depot" class="field-input" :aria-label="`Dépôt, ligne ${index + 1}`" :aria-invalid="!entry.depot" @change="onDepot(entry)">
													<option value="">Choisir…</option>
													<option v-for="item in depotsFor(lineOf(entry), entry.depot)" :key="item.depot" :value="item.depot">{{ item.depot }} · {{ formatQty(item.qty) }} en stock</option>
												</select>
												<span v-else class="text-ink-gray-6">Hors stock</span>
											</td>
											<td>
												<select v-if="lineOf(entry).avec_lot" v-model="entry.lot" class="field-input" :aria-label="`Lot, ligne ${index + 1}`" :aria-invalid="!entry.lot && !livraison.retour" :disabled="!entry.depot">
													<option value="">{{ entry.depot ? (lotsFor(lineOf(entry), entry.depot).length ? 'Choisir…' : 'Aucun lot dans ce dépôt') : 'Choisir le dépôt d\'abord' }}</option>
													<option v-for="lot in lotsFor(lineOf(entry), entry.depot, entry.lot)" :key="lot.lot" :value="lot.lot">{{ lotLabel(lot) }}</option>
												</select>
												<span v-else class="text-ink-gray-6">—</span>
											</td>
										</tr>
									</tbody>
								</table></div>
							</section>

							<!-- Bon validé ou annulé : les lignes telles que sorties du stock. -->
							<section v-else class="card ref-card">
								<h3>Lignes</h3>
								<div class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Article</th><th class="end">Quantité</th><th>Dépôt</th><th>Lot</th><th class="end">Montant HT (DA)</th></tr></thead>
									<tbody>
										<tr v-for="line in livraison.lignes" :key="line.name">
											<td><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: line.article } }">{{ line.designation }}</RouterLink><span class="ml-1 text-xs tabular-nums text-ink-gray-6">{{ line.article }}</span></td>
											<td class="end tabular-nums">{{ formatQty(line.quantite) }} {{ line.unite }}</td>
											<td>{{ line.depot || '—' }}</td>
											<td class="tabular-nums">{{ line.lot ? line.lot : line.avec_lot ? 'Choisi par ERPNext' : '—' }}</td>
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
									<h3>Factures</h3>
									<p v-if="!livraison.factures.length" class="text-ink-gray-6">Aucune facture.</p>
									<div v-else class="ref-scroll"><table class="ref-table">
										<thead><tr><th>Facture</th><th>Date</th><th>Statut</th><th class="end">Total (DA)</th></tr></thead>
										<tbody><tr v-for="row in livraison.factures" :key="row.name"><td><RouterLink class="ref-link" :to="{ name: 'FactureFiche', params: { id: row.name } }">{{ row.name }}</RouterLink></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td><StatusPill :status="row.status" /></td><td class="end tabular-nums">{{ formatAmount(row.total) }}</td></tr></tbody>
									</table></div>
								</section>
								<section class="card ref-card">
									<h3>Retours</h3>
									<p v-if="!livraison.retours.length" class="text-ink-gray-6">Aucun retour.</p>
									<div v-else class="ref-scroll"><table class="ref-table">
										<thead><tr><th>Bon de retour</th><th>Date</th><th>Statut</th><th class="end">Total (DA)</th></tr></thead>
										<tbody><tr v-for="row in livraison.retours" :key="row.name"><td><button type="button" class="ref-link tabular-nums" @click="emit('open', row.name)">{{ row.name }}</button></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td><StatusPill :status="row.status" /></td><td class="end tabular-nums">{{ formatAmount(row.total) }}</td></tr></tbody>
									</table></div>
								</section>
							</div>
						</div>

						<aside class="record-activity" aria-label="Commentaires et activité du bon">
							<ActivityFeed ref="feed" :api="activityApi" :version="livraison.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<FormDialog v-if="confirming && livraison" :title="confirming === 'annuler' ? 'Annuler le bon de livraison' : 'Supprimer le brouillon'" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour confirmer" @close="confirming = null" @submit="confirm">
			<p>{{ confirming === 'annuler' ? `Le bon ${livraison.name} sera annulé : le stock revient et la commande redevient à livrer. ERPNext refuse si une facture ou un retour validé en dépend.` : `Le brouillon ${livraison.name} sera supprimé ; ses quantités redeviennent à livrer sur la commande.` }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="confirm">{{ confirming === 'annuler' ? 'Annuler le bon' : 'Supprimer' }}</button>
			</template>
		</FormDialog>

		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
		<AppToast :message="created?.label ?? ''" :duration="0" @close="created = null">
			<template v-if="created">
				<button v-if="created.doctype === 'Delivery Note'" type="button" class="app-toast-action" @click="(emit('open', created.name), (created = null))">Ouvrir le retour</button>
				<RouterLink v-else class="app-toast-action" :to="{ name: 'FactureFiche', params: { id: created.name } }" @click="created = null">Ouvrir la facture</RouterLink>
			</template>
		</AppToast>
	</main>
</template>
