<script setup lang="ts">
import { computed, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideCalendar from '~icons/lucide/calendar'
import LucideMail from '~icons/lucide/mail'
import LucideMap from '~icons/lucide/map'
import LucideMapPin from '~icons/lucide/map-pin'
import LucidePhone from '~icons/lucide/phone'
import LucideTag from '~icons/lucide/tag'
import LucideWallet from '~icons/lucide/wallet'
import type { UploadedFile } from '@shared/api'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FileUploader from '@shared/components/FileUploader.vue'
import ListState from '@shared/components/ListState.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import ClientDialog from './ClientDialog.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import { clientActivity, deleteClient, setClientPiece } from '@/lib/api'
import { formatAmount, type ClientDetail, type ClientVente, type VenteKey } from '@/lib/clients'
import { confirmAction } from '@/lib/confirm'
import { deskUrl, formatDay } from '@/lib/display'
import { useClient } from '@/lib/useClient'

const props = defineProps<{ id: string; tab?: string }>()
const emit = defineEmits<{ tab: [tab: string]; changed: []; deleted: [] }>()

const { client, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useClient(
	() => props.id,
	() => emit('changed'),
	true,
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => clientActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, client })

/** Natures de vente, dans l'ordre du cycle. Le Desk crée la pièce avec le client déjà choisi. */
const VENTES: { key: VenteKey; title: string; piece: string; doctype: string; field: string; empty: string }[] = [
	{ key: 'devis', title: 'Devis', piece: 'Devis', doctype: 'Quotation', field: 'party_name', empty: 'Aucun devis pour ce client.' },
	{ key: 'commandes', title: 'Commandes', piece: 'Commande', doctype: 'Sales Order', field: 'customer', empty: 'Aucune commande pour ce client.' },
	{ key: 'livraisons', title: 'Livraisons', piece: 'Livraison', doctype: 'Delivery Note', field: 'customer', empty: 'Aucune livraison pour ce client.' },
	{ key: 'factures', title: 'Factures', piece: 'Facture', doctype: 'Sales Invoice', field: 'customer', empty: 'Aucune facture pour ce client.' },
]
const shownVentes = computed(() => VENTES.filter((group) => client.value?.ventes?.[group.key]))
const venteCount = computed(() => shownVentes.value.reduce((total, group) => total + (client.value?.ventes?.[group.key]?.length ?? 0), 0))

const tabs = computed(() => {
	const current = client.value
	if (!current) return []
	const list: { key: string; label: string; count?: number }[] = [{ key: 'apercu', label: 'Aperçu' }]
	if (shownVentes.value.length) list.push({ key: 'ventes', label: 'Ventes', count: venteCount.value })
	if (current.comptabilite) list.push({ key: 'comptabilite', label: 'Comptabilité' })
	list.push({ key: 'infos', label: 'Informations' })
	return list
})
const activeTab = computed(() => (tabs.value.some((tab) => tab.key === props.tab) ? props.tab! : 'apercu'))

interface Vente extends ClientVente {
	piece: string
	doctype: string
}
function ventes(current: ClientDetail): Vente[] {
	return VENTES.flatMap((group) => (current.ventes?.[group.key] ?? []).map((row) => ({ ...row, piece: group.piece, doctype: group.doctype })))
}
const lastVentes = computed(() => (client.value ? ventes(client.value).sort((a, b) => String(b.date).localeCompare(String(a.date))).slice(0, 5) : []))
const unpaid = computed(() => (client.value?.ventes?.factures ?? []).filter((row) => (row.reste ?? 0) > 0 && row.status !== 'Draft'))
const missingPieces = computed(() => (client.value?.pieces ?? []).filter((piece) => !piece.fichier).length)
const mainContact = computed(() => client.value?.contacts[0])

function onTags(tags: string[]) {
	if (client.value) client.value.tags = tags
	emit('changed')
}
function newOnDesk(doctype: string, field: string) {
	return `${deskUrl(doctype, 'new')}?${field}=${encodeURIComponent(props.id)}`
}
// Les pièces qui ont leur fiche dans le bureau ; les autres s'ouvrent sur le Desk.
const FICHES: Record<string, string> = { Quotation: 'DevisFiche', 'Sales Order': 'CommandeFiche', 'Delivery Note': 'LivraisonFiche', 'Sales Invoice': 'FactureFiche' }
const DESK_NEW = VENTES.filter((group) => group.key === 'devis' || group.key === 'commandes')

async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

const editing = ref(false)
function onSaved(updated: ClientDetail) {
	client.value = updated
	notice.value = 'Client enregistré.'
	emit('changed')
}

// La pièce choisie : le fichier part avec son avancement, puis se range dans son champ.
const pieceUploader = ref<InstanceType<typeof FileUploader> | null>(null)
let pendingPiece = ''
function joinPiece(piece: string) {
	pendingPiece = piece
	pieceUploader.value?.pick()
}
function onPieceUploaded(file: UploadedFile) {
	const current = client.value
	if (current && pendingPiece) perform(() => setClientPiece(current, pendingPiece, file.file_url))
}
// Suppression de la fiche : Frappe refuse tant qu'une pièce ou un autre document y est lié, et le message le dit.
async function supprimer() {
	const current = client.value
	if (!current) return
	if (!(await confirmAction({ title: 'Supprimer le client', message: `${current.name} sera supprimé définitivement. Si une pièce ou un autre document y est lié, la suppression est refusée et rien ne change.`, confirmLabel: 'Supprimer', danger: true }))) return
	busy.value = true
	actionError.value = ''
	try {
		await deleteClient(current)
		emit('deleted')
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
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Ce client n'existe pas ou n'existe plus.</div>
		<div v-else-if="!client" class="card p-8 text-center text-ink-gray-6">Chargement du client…</div>

		<template v-else>
			<RecordHeader>
				<template #title>{{ client.client }}</template>
				<template #flags><StatusPill :status="client.status" /></template>
				<template #sub>
					<span v-if="client.forme_juridique">{{ client.forme_juridique }}</span>
					<span class="tabular-nums">{{ client.name }}</span>
					<span v-if="client.commune_label || client.wilaya">{{ [client.commune_label, client.wilaya].filter(Boolean).join(', ') }}</span>
					<div v-if="client.tags?.length || client.can_edit"><TagEditor doctype="Customer" :name="client.name" :modified="client.modified" :tags="client.tags" :can-edit="client.can_edit" @changed="onTags" /></div>
				</template>
				<template #actions>
					<button v-if="client.can_edit" type="button" class="btn-primary" :disabled="busy" @click="editing = true">Modifier</button>
					<MoreMenu>
						<a v-for="group in DESK_NEW.filter((item) => client?.ventes?.[item.key])" :key="group.key" class="app-menu-item" role="menuitem" :href="newOnDesk(group.doctype, group.field)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />{{ group.key === 'devis' ? 'Nouveau devis' : 'Nouvelle commande' }}</a>
						<div v-if="DESK_NEW.some((item) => client?.ventes?.[item.key])" class="app-menu-sep"></div>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Customer', client.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="client.can_delete">
							<div class="app-menu-sep"></div>
							<button type="button" class="app-menu-item text-tone-red" role="menuitem" :disabled="busy" @click="supprimer">Supprimer le client</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations du client">
					<div class="side-block">
						<dl class="record-facts">
							<div>
								<dt><LucidePhone aria-hidden="true" />Contact principal</dt>
								<dd v-if="mainContact">
									{{ mainContact.nom || 'Sans nom' }}<span v-if="mainContact.fonction" class="font-normal text-ink-gray-6"> · {{ mainContact.fonction }}</span>
									<span class="contact-links font-normal">
										<a v-if="mainContact.telephone" class="ref-link tabular-nums" :href="`tel:${mainContact.telephone}`">{{ mainContact.telephone }}</a>
										<a v-if="mainContact.email" class="ref-link" :href="`mailto:${mainContact.email}`"><LucideMail class="h-3.5 w-3.5" aria-hidden="true" />{{ mainContact.email }}</a>
									</span>
								</dd>
								<dd v-else class="record-fact-none">Aucun contact enregistré.</dd>
							</div>
							<div><dt><LucideTag aria-hidden="true" />Catégorie</dt><dd :class="!client.categorie && 'record-fact-none'">{{ client.categorie || 'Non renseignée' }}</dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Client depuis</dt><dd class="tabular-nums">{{ formatDay(client.depuis) || '—' }}</dd></div>
							<div v-if="client.solde !== null"><dt><LucideWallet aria-hidden="true" />Solde</dt><dd class="tabular-nums" :class="!client.solde && 'record-fact-none'">{{ client.solde ? `${formatAmount(client.solde)} DA` : 'Aucun' }}</dd></div>
							<div>
								<dt><LucideMapPin aria-hidden="true" />Adresse</dt>
								<dd class="flex items-center justify-between gap-2">
									<span class="min-w-0 whitespace-pre-line">{{ client.adresse || [client.commune_label, client.wilaya].filter(Boolean).join(', ') || 'Non renseignée' }}</span>
									<a v-if="client.map_url" class="icon-btn" :href="client.map_url" target="_blank" rel="noopener noreferrer" aria-label="Voir sur la carte" title="Voir sur la carte"><LucideMap class="h-4 w-4" aria-hidden="true" /></a>
								</dd>
							</div>
							<div v-if="client.region"><dt><LucideMapPin aria-hidden="true" />Région</dt><dd>{{ client.region }}</dd></div>
						</dl>
					</div>
				</aside>

				<div class="client-main">
					<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

					<div class="record-tabs" role="tablist">
						<button v-for="item in tabs" :key="item.key" type="button" class="record-tab" role="tab" :aria-selected="activeTab === item.key" @click="emit('tab', item.key)">
							{{ item.label }}<span v-if="item.count" class="ml-1 tabular-nums text-ink-gray-6">{{ item.count }}</span>
						</button>
					</div>

					<div class="bureau-detail">
						<FileUploader ref="pieceUploader" class="w-full" doctype="Customer" :docname="client.name" :zone="false" :multiple="false" @uploaded="onPieceUploaded" />

						<!-- Aperçu : il résume les autres onglets. -->
						<div v-if="activeTab === 'apercu'" class="bureau-center">
							<div v-if="unpaid.length" role="status" class="rounded-control tone-amber px-3.5 py-2.5">
								<strong class="font-semibold">{{ unpaid.length > 1 ? `${unpaid.length} factures non soldées` : '1 facture non soldée' }}</strong>
								pour {{ formatAmount(unpaid.reduce((total, row) => total + (row.reste ?? 0), 0)) }} DA.
								<button type="button" class="font-medium underline" @click="emit('tab', 'ventes')">Voir les factures</button>
							</div>
							<div class="client-cards">
								<section v-if="client.comptabilite" class="card ref-card">
									<div class="ref-card-head"><h3>Solde</h3><button type="button" class="ref-link" @click="emit('tab', 'comptabilite')">Voir les écritures</button></div>
									<div class="amount-row"><span class="amount tabular-nums">{{ formatAmount(client.comptabilite.solde) }} DA</span></div>
									<dl class="kv">
										<div><dt>Total débit</dt><dd class="tabular-nums">{{ formatAmount(client.comptabilite.debit) }} DA</dd></div>
										<div><dt>Total crédit</dt><dd class="tabular-nums">{{ formatAmount(client.comptabilite.credit) }} DA</dd></div>
									</dl>
								</section>
								<section class="card ref-card">
									<h3>Identité</h3>
									<dl class="kv">
										<div><dt>Raison sociale</dt><dd>{{ client.client }}</dd></div>
										<div><dt>Forme juridique</dt><dd>{{ client.forme_juridique || '—' }}</dd></div>
										<div><dt>Catégorie</dt><dd>{{ client.categorie || '—' }}</dd></div>
										<div><dt>Statut</dt><dd>{{ client.status || '—' }}</dd></div>
										<div><dt>Téléphone principal</dt><dd class="tabular-nums">{{ client.telephone || '—' }}</dd></div>
										<div><dt>Email principal</dt><dd>{{ client.email || '—' }}</dd></div>
										<div><dt>Code</dt><dd class="tabular-nums">{{ client.name }}</dd></div>
									</dl>
								</section>
							</div>
							<section v-if="shownVentes.length" class="card ref-card">
								<div class="ref-card-head"><h3>Dernières ventes</h3><button v-if="venteCount > lastVentes.length" type="button" class="ref-link" @click="emit('tab', 'ventes')">Tout voir</button></div>
								<p v-if="!lastVentes.length" class="text-ink-gray-6">Aucun devis, commande, livraison ni facture.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Pièce</th><th>Numéro</th><th>Date</th><th>Statut</th><th class="end">Montant (DA)</th></tr></thead>
									<tbody><tr v-for="row in lastVentes" :key="`${row.doctype}-${row.name}`"><td>{{ row.piece }}</td><td><RouterLink v-if="row.doctype in FICHES" class="ref-link" :to="{ name: FICHES[row.doctype], params: { id: row.name } }">{{ row.name }}</RouterLink><a v-else class="ref-link" :href="deskUrl(row.doctype, row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td><StatusPill :status="row.status" /></td><td class="end tabular-nums">{{ formatAmount(row.total) }}</td></tr></tbody>
								</table></div>
							</section>
						</div>

						<!-- Ventes. -->
						<div v-else-if="activeTab === 'ventes'" class="bureau-center">
							<section v-for="group in shownVentes" :key="group.key" class="card ref-card">
								<div class="ref-card-head">
									<h3>{{ group.title }}</h3>
									<a v-if="group.key === 'devis' || group.key === 'commandes'" class="ref-link" :href="newOnDesk(group.doctype, group.field)" target="_blank" rel="noopener noreferrer">{{ group.key === 'devis' ? 'Nouveau devis' : 'Nouvelle commande' }}</a>
								</div>
								<p v-if="!client.ventes?.[group.key]?.length" class="text-ink-gray-6">{{ group.empty }}</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Numéro</th><th>Date</th><th>Statut</th><th class="end">Montant (DA)</th><th v-if="group.key === 'factures'" class="end">Reste dû (DA)</th></tr></thead>
									<tbody>
										<tr v-for="row in client.ventes?.[group.key] ?? []" :key="row.name">
											<td><RouterLink v-if="group.doctype in FICHES" class="ref-link" :to="{ name: FICHES[group.doctype], params: { id: row.name } }">{{ row.name }}</RouterLink><a v-else class="ref-link" :href="deskUrl(group.doctype, row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td>
											<td class="tabular-nums">{{ formatDay(row.date) }}</td>
											<td><StatusPill :status="row.status" /></td>
											<td class="end tabular-nums">{{ formatAmount(row.total) }}</td>
											<td v-if="group.key === 'factures'" class="end tabular-nums" :class="!row.reste && 'text-ink-gray-6'">{{ formatAmount(row.reste) }}</td>
										</tr>
									</tbody>
								</table></div>
							</section>
						</div>

						<!-- Comptabilité. -->
						<div v-else-if="activeTab === 'comptabilite' && client.comptabilite" class="bureau-center">
							<section class="card ref-card">
								<h3>Solde du client</h3>
								<div class="amount-row"><span class="amount tabular-nums">{{ formatAmount(client.comptabilite.solde) }} DA</span></div>
								<dl class="kv">
									<div><dt>Total débit</dt><dd class="tabular-nums">{{ formatAmount(client.comptabilite.debit) }} DA</dd></div>
									<div><dt>Total crédit</dt><dd class="tabular-nums">{{ formatAmount(client.comptabilite.credit) }} DA</dd></div>
								</dl>
							</section>
							<section class="card ref-card">
								<h3>Dernières écritures</h3>
								<ListState v-if="!client.comptabilite.ecritures.length" illustration title="Aucune écriture" text="Les factures et paiements validés du client apparaissent ici." />
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Date</th><th>Pièce</th><th>Numéro</th><th class="end">Débit (DA)</th><th class="end">Crédit (DA)</th></tr></thead>
									<tbody>
										<tr v-for="row in client.comptabilite.ecritures" :key="`${row.voucher_type}-${row.voucher_no}`">
											<td class="tabular-nums">{{ formatDay(row.date) }}</td>
											<td>{{ row.voucher_type }}</td>
											<td><a class="ref-link" :href="deskUrl(row.voucher_type, row.voucher_no)" target="_blank" rel="noopener noreferrer">{{ row.voucher_no }}</a></td>
											<td class="end tabular-nums" :class="!row.debit && 'text-ink-gray-6'">{{ formatAmount(row.debit) }}</td>
											<td class="end tabular-nums" :class="!row.credit && 'text-ink-gray-6'">{{ formatAmount(row.credit) }}</td>
										</tr>
									</tbody>
								</table></div>
							</section>
						</div>

						<!-- Informations. -->
						<div v-else-if="activeTab === 'infos'" class="info-grid">
							<section class="card ref-card">
								<div class="ref-card-head"><h3>Pièces administratives</h3><StatusPill :status="missingPieces ? `${missingPieces} manquante${missingPieces > 1 ? 's' : ''}` : 'Complet'" :tone="missingPieces ? 'amber' : 'green'" /></div>
								<div class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Pièce</th><th>Numéro</th><th>Fichier</th></tr></thead>
									<tbody><tr v-for="piece in client.pieces" :key="piece.key">
										<td>{{ piece.label }}</td>
										<td class="tabular-nums" :class="!piece.numero && 'text-ink-gray-6'">{{ piece.numero || 'Non renseigné' }}</td>
										<td>
											<span class="inline-flex gap-2">
												<a v-if="piece.fichier" class="ref-link" :href="piece.fichier" target="_blank" rel="noopener noreferrer">Ouvrir</a>
												<button v-if="client.can_edit" type="button" class="ref-link" :disabled="busy" :aria-label="`${piece.fichier ? 'Remplacer' : 'Joindre'} le fichier ${piece.label}`" @click="joinPiece(piece.key)">{{ piece.fichier ? 'Remplacer' : 'Joindre' }}</button>
												<span v-else-if="!piece.fichier" class="text-ink-gray-6">Aucun</span>
											</span>
										</td>
									</tr></tbody>
								</table></div>
							</section>
							<section class="card ref-card">
								<div class="ref-card-head"><h3>Contacts</h3><a class="ref-link" :href="deskUrl('Customer', client.name)" target="_blank" rel="noopener noreferrer">Gérer sur le Desk</a></div>
								<p v-if="!client.contacts.length" class="text-ink-gray-6">Aucun contact enregistré.</p>
								<div v-for="(contact, index) in client.contacts" :key="index" class="contact">
									<p><span class="font-semibold text-ink-gray-9">{{ contact.nom || 'Sans nom' }}</span><span v-if="contact.principal" class="text-sm text-ink-gray-6"> Principal</span></p>
									<p v-if="contact.fonction" class="text-sm text-ink-gray-6">{{ contact.fonction }}</p>
									<p class="contact-links">
										<a v-if="contact.telephone" class="ref-link tabular-nums" :href="`tel:${contact.telephone}`"><LucidePhone class="h-3.5 w-3.5" aria-hidden="true" />{{ contact.telephone }}</a>
										<a v-if="contact.email" class="ref-link" :href="`mailto:${contact.email}`"><LucideMail class="h-3.5 w-3.5" aria-hidden="true" />{{ contact.email }}</a>
									</p>
								</div>
							</section>
							<section class="card ref-card">
								<h3>Adresse</h3>
								<dl class="kv">
									<div><dt>Adresse</dt><dd class="whitespace-pre-line">{{ client.adresse || '—' }}</dd></div>
									<div><dt>Commune</dt><dd>{{ client.commune_label || '—' }}</dd></div>
									<div><dt>Wilaya</dt><dd>{{ client.wilaya || '—' }}</dd></div>
									<div><dt>Région</dt><dd>{{ client.region || '—' }}</dd></div>
									<div><dt>GPS</dt><dd class="tabular-nums"><a v-if="client.map_url" class="ref-link" :href="client.map_url" target="_blank" rel="noopener noreferrer">{{ client.gps }}</a><template v-else>{{ client.gps || '—' }}</template></dd></div>
								</dl>
							</section>
						</div>

						<!-- Le fil vient après le contenu, quel que soit l'onglet. -->
						<aside class="record-activity" aria-label="Commentaires et activité du client">
							<ActivityFeed ref="feed" :api="activityApi" :version="client.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<ClientDialog v-if="editing && client" :client="client" @close="editing = false" @saved="onSaved" />
		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
	</main>
</template>
