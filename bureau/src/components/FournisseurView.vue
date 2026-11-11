<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideCalendar from '~icons/lucide/calendar'
import LucideMail from '~icons/lucide/mail'
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
import FournisseurDialog from './FournisseurDialog.vue'
import ContactsCard from './ContactsCard.vue'
import PieceLink from './PieceLink.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import { deleteFournisseur, fournisseurActivity, setFournisseurPiece } from '@/lib/api'
import { formatAmount, type AchatKey, type FournisseurAchat, type FournisseurDetail } from '@/lib/fournisseurs'
import { confirmAction } from '@/lib/confirm'
import { deskUrl, formatDay } from '@/lib/display'
import { useFournisseur } from '@/lib/useFournisseur'

const props = defineProps<{ id: string; tab?: string }>()
const emit = defineEmits<{ tab: [tab: string]; changed: []; deleted: [] }>()

const { fournisseur, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useFournisseur(
	() => props.id,
	() => emit('changed'),
	true,
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => fournisseurActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, fournisseur })

/** Natures d'achat, dans l'ordre du cycle. */
const ACHATS: { key: AchatKey; title: string; piece: string; doctype: string; field: string; empty: string; fiche: string }[] = [
	{ key: 'devis', title: 'Devis fournisseur', piece: 'Devis', doctype: 'Supplier Quotation', field: 'supplier', empty: 'Aucun devis de ce fournisseur.', fiche: 'DevisFournisseurFiche' },
	{ key: 'commandes', title: "Commandes d'achat", piece: 'Commande', doctype: 'Purchase Order', field: 'supplier', empty: 'Aucune commande à ce fournisseur.', fiche: 'CommandeAchatFiche' },
	{ key: 'receptions', title: 'Réceptions', piece: 'Réception', doctype: 'Purchase Receipt', field: 'supplier', empty: 'Aucune réception de ce fournisseur.', fiche: 'ReceptionFiche' },
	{ key: 'factures', title: "Factures d'achat", piece: 'Facture', doctype: 'Purchase Invoice', field: 'supplier', empty: 'Aucune facture de ce fournisseur.', fiche: 'FactureAchatFiche' },
]
const shownAchats = computed(() => ACHATS.filter((group) => fournisseur.value?.achats?.[group.key]))
const achatCount = computed(() => shownAchats.value.reduce((total, group) => total + (fournisseur.value?.achats?.[group.key]?.length ?? 0), 0))

const tabs = computed(() => {
	const current = fournisseur.value
	if (!current) return []
	const list: { key: string; label: string; count?: number }[] = [{ key: 'apercu', label: 'Aperçu' }]
	if (shownAchats.value.length) list.push({ key: 'achats', label: 'Achats', count: achatCount.value })
	if (current.comptabilite) list.push({ key: 'comptabilite', label: 'Comptabilité' })
	list.push({ key: 'infos', label: 'Informations' })
	return list
})
const activeTab = computed(() => (tabs.value.some((tab) => tab.key === props.tab) ? props.tab! : 'apercu'))

interface Achat extends FournisseurAchat {
	piece: string
	doctype: string
	fiche: string
}
function achats(current: FournisseurDetail): Achat[] {
	return ACHATS.flatMap((group) => (current.achats?.[group.key] ?? []).map((row) => ({ ...row, piece: group.piece, doctype: group.doctype, fiche: group.fiche })))
}
const lastAchats = computed(() => (fournisseur.value ? achats(fournisseur.value).sort((a, b) => String(b.date).localeCompare(String(a.date))).slice(0, 5) : []))
const unpaid = computed(() => (fournisseur.value?.achats?.factures ?? []).filter((row) => (row.reste ?? 0) > 0 && row.status !== 'Draft'))
const missingPieces = computed(() => (fournisseur.value?.pieces ?? []).filter((piece) => !piece.fichier).length)
const mainContact = computed(() => fournisseur.value?.contacts[0])

function onTags(tags: string[]) {
	if (fournisseur.value) fournisseur.value.tags = tags
	emit('changed')
}
// Les pièces qui ont déjà leur fiche dans le bureau ; les autres s'ouvrent sur le Desk.
const router = useRouter()
const hasFiche = (fiche: string) => router.hasRoute(fiche)

async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

const editing = ref(false)
function onSaved(updated: FournisseurDetail) {
	fournisseur.value = updated
	notice.value = 'Fournisseur enregistré.'
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
	const current = fournisseur.value
	if (current && pendingPiece) perform(() => setFournisseurPiece(current, pendingPiece, file.file_url))
}
// Suppression de la fiche : Frappe refuse tant qu'une pièce ou un autre document y est lié, et le message le dit.
async function supprimer() {
	const current = fournisseur.value
	if (!current) return
	if (!(await confirmAction({ title: 'Supprimer le fournisseur', message: `${current.name} sera supprimé définitivement. Si une pièce ou un autre document y est lié, la suppression est refusée et rien ne change.`, confirmLabel: 'Supprimer', danger: true }))) return
	busy.value = true
	actionError.value = ''
	try {
		await deleteFournisseur(current)
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
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Ce fournisseur n'existe pas ou n'existe plus.</div>
		<div v-else-if="!fournisseur" class="card p-8 text-center text-ink-gray-6">Chargement du fournisseur…</div>

		<template v-else>
			<RecordHeader>
				<template #title>{{ fournisseur.fournisseur }}</template>
				<template #flags><StatusPill :status="fournisseur.status" /></template>
				<template #sub>
					<span class="tabular-nums">{{ fournisseur.name }}</span>
					<span v-if="fournisseur.commune_label || fournisseur.wilaya">{{ [fournisseur.commune_label, fournisseur.wilaya].filter(Boolean).join(', ') }}</span>
					<div v-if="fournisseur.tags?.length || fournisseur.can_edit"><TagEditor doctype="Supplier" :name="fournisseur.name" :modified="fournisseur.modified" :tags="fournisseur.tags" :can-edit="fournisseur.can_edit" @changed="onTags" /></div>
				</template>
				<template #actions>
					<button v-if="fournisseur.can_edit" type="button" class="btn-primary" :disabled="busy" @click="editing = true">Modifier</button>
					<MoreMenu>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Supplier', fournisseur.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="fournisseur.can_delete">
							<div class="app-menu-sep"></div>
							<button type="button" class="app-menu-item text-tone-red" role="menuitem" :disabled="busy" @click="supprimer">Supprimer le fournisseur</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations du fournisseur">
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
							<div><dt><LucideTag aria-hidden="true" />Catégorie</dt><dd :class="!fournisseur.categorie && 'record-fact-none'">{{ fournisseur.categorie || 'Non renseignée' }}</dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Fournisseur depuis</dt><dd class="tabular-nums">{{ formatDay(fournisseur.depuis) || '—' }}</dd></div>
							<div v-if="fournisseur.solde !== null"><dt><LucideWallet aria-hidden="true" />À payer</dt><dd class="tabular-nums" :class="!fournisseur.solde && 'record-fact-none'">{{ fournisseur.solde ? `${formatAmount(fournisseur.solde)} DA` : 'Rien' }}</dd></div>
							<div>
								<dt><LucideMapPin aria-hidden="true" />Adresse</dt>
								<dd class="min-w-0 whitespace-pre-line">{{ fournisseur.adresse || [fournisseur.commune_label, fournisseur.wilaya].filter(Boolean).join(', ') || 'Non renseignée' }}</dd>
							</div>
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
						<FileUploader ref="pieceUploader" class="w-full" doctype="Supplier" :docname="fournisseur.name" :zone="false" :multiple="false" @uploaded="onPieceUploaded" />

						<!-- Aperçu : il résume les autres onglets. -->
						<div v-if="activeTab === 'apercu'" class="bureau-center">
							<div v-if="unpaid.length" role="status" class="rounded-control tone-amber px-3.5 py-2.5">
								<strong class="font-semibold">{{ unpaid.length > 1 ? `${unpaid.length} factures à payer` : '1 facture à payer' }}</strong>
								pour {{ formatAmount(unpaid.reduce((total, row) => total + (row.reste ?? 0), 0)) }} DA.
								<button type="button" class="font-medium underline" @click="emit('tab', 'achats')">Voir les factures</button>
							</div>
							<div class="client-cards">
								<section v-if="fournisseur.comptabilite" class="card ref-card">
									<div class="ref-card-head"><h3>À payer</h3><button type="button" class="ref-link" @click="emit('tab', 'comptabilite')">Voir les écritures</button></div>
									<div class="amount-row"><span class="amount tabular-nums">{{ formatAmount(fournisseur.comptabilite.solde) }} DA</span></div>
									<dl class="kv">
										<div><dt>Total débit</dt><dd class="tabular-nums">{{ formatAmount(fournisseur.comptabilite.debit) }} DA</dd></div>
										<div><dt>Total crédit</dt><dd class="tabular-nums">{{ formatAmount(fournisseur.comptabilite.credit) }} DA</dd></div>
									</dl>
								</section>
								<section class="card ref-card">
									<h3>Identité</h3>
									<dl class="kv">
										<div><dt>Raison sociale</dt><dd>{{ fournisseur.fournisseur }}</dd></div>
										<div><dt>Catégorie</dt><dd>{{ fournisseur.categorie || '—' }}</dd></div>
										<div><dt>Statut</dt><dd>{{ fournisseur.status || '—' }}</dd></div>
										<div><dt>Pays</dt><dd>{{ fournisseur.pays || '—' }}</dd></div>
										<div><dt>Téléphone</dt><dd class="tabular-nums">{{ fournisseur.telephone || '—' }}</dd></div>
										<div><dt>Email</dt><dd>{{ fournisseur.email || '—' }}</dd></div>
										<div><dt>Code</dt><dd class="tabular-nums">{{ fournisseur.name }}</dd></div>
									</dl>
								</section>
							</div>
							<section v-if="shownAchats.length" class="card ref-card">
								<div class="ref-card-head"><h3>Derniers achats</h3><button v-if="achatCount > lastAchats.length" type="button" class="ref-link" @click="emit('tab', 'achats')">Tout voir</button></div>
								<p v-if="!lastAchats.length" class="text-ink-gray-6">Aucun devis, commande, réception ni facture.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Pièce</th><th>Numéro</th><th>Date</th><th>Statut</th><th class="end">Montant (DA)</th></tr></thead>
									<tbody><tr v-for="row in lastAchats" :key="`${row.doctype}-${row.name}`"><td>{{ row.piece }}</td><td><RouterLink v-if="hasFiche(row.fiche)" class="ref-link" :to="{ name: row.fiche, params: { id: row.name } }">{{ row.name }}</RouterLink><a v-else class="ref-link" :href="deskUrl(row.doctype, row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td><StatusPill :status="row.status" /></td><td class="end tabular-nums">{{ formatAmount(row.total) }}</td></tr></tbody>
								</table></div>
							</section>
						</div>

						<!-- Achats. -->
						<div v-else-if="activeTab === 'achats'" class="bureau-center">
							<section v-for="group in shownAchats" :key="group.key" class="card ref-card">
								<div class="ref-card-head"><h3>{{ group.title }}</h3></div>
								<p v-if="!fournisseur.achats?.[group.key]?.length" class="text-ink-gray-6">{{ group.empty }}</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Numéro</th><th>Date</th><th>Statut</th><th class="end">Montant (DA)</th><th v-if="group.key === 'factures'" class="end">Reste à payer (DA)</th></tr></thead>
									<tbody>
										<tr v-for="row in fournisseur.achats?.[group.key] ?? []" :key="row.name">
											<td><RouterLink v-if="hasFiche(group.fiche)" class="ref-link" :to="{ name: group.fiche, params: { id: row.name } }">{{ row.name }}</RouterLink><a v-else class="ref-link" :href="deskUrl(group.doctype, row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td>
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
						<div v-else-if="activeTab === 'comptabilite' && fournisseur.comptabilite" class="bureau-center">
							<section class="card ref-card">
								<h3>Ce que la société doit au fournisseur</h3>
								<div class="amount-row"><span class="amount tabular-nums">{{ formatAmount(fournisseur.comptabilite.solde) }} DA</span></div>
								<dl class="kv">
									<div><dt>Total débit</dt><dd class="tabular-nums">{{ formatAmount(fournisseur.comptabilite.debit) }} DA</dd></div>
									<div><dt>Total crédit</dt><dd class="tabular-nums">{{ formatAmount(fournisseur.comptabilite.credit) }} DA</dd></div>
								</dl>
							</section>
							<section class="card ref-card">
								<h3>Dernières écritures</h3>
								<ListState v-if="!fournisseur.comptabilite.ecritures.length" illustration title="Aucune écriture" text="Les factures d'achat et paiements validés du fournisseur apparaissent ici." />
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Date</th><th>Pièce</th><th>Numéro</th><th class="end">Débit (DA)</th><th class="end">Crédit (DA)</th></tr></thead>
									<tbody>
										<tr v-for="row in fournisseur.comptabilite.ecritures" :key="`${row.voucher_type}-${row.voucher_no}`">
											<td class="tabular-nums">{{ formatDay(row.date) }}</td>
											<td>{{ row.voucher_type }}</td>
											<td><PieceLink :doctype="row.voucher_type" :name="row.voucher_no" /></td>
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
									<tbody><tr v-for="piece in fournisseur.pieces" :key="piece.key">
										<td>{{ piece.label }}</td>
										<td class="tabular-nums" :class="!piece.numero && 'text-ink-gray-6'">{{ piece.numero || 'Non renseigné' }}</td>
										<td>
											<span class="inline-flex gap-2">
												<a v-if="piece.fichier" class="ref-link" :href="piece.fichier" target="_blank" rel="noopener noreferrer">Ouvrir</a>
												<button v-if="fournisseur.can_edit" type="button" class="ref-link" :disabled="busy" :aria-label="`${piece.fichier ? 'Remplacer' : 'Joindre'} le fichier ${piece.label}`" @click="joinPiece(piece.key)">{{ piece.fichier ? 'Remplacer' : 'Joindre' }}</button>
												<span v-else-if="!piece.fichier" class="text-ink-gray-6">Aucun</span>
											</span>
										</td>
									</tr></tbody>
								</table></div>
							</section>
							<ContactsCard :contacts="fournisseur.contacts" link-doctype="Supplier" :link-name="fournisseur.name" :can-edit="fournisseur.can_edit" @changed="(message) => refreshAll(message)" />
							<section class="card ref-card">
								<h3>Adresse</h3>
								<dl class="kv">
									<div><dt>Adresse</dt><dd class="whitespace-pre-line">{{ fournisseur.adresse || '—' }}</dd></div>
									<div><dt>Commune</dt><dd>{{ fournisseur.commune_label || '—' }}</dd></div>
									<div><dt>Wilaya</dt><dd>{{ fournisseur.wilaya || '—' }}</dd></div>
									<div><dt>Pays</dt><dd>{{ fournisseur.pays || '—' }}</dd></div>
								</dl>
							</section>
						</div>

						<!-- Le fil vient après le contenu, quel que soit l'onglet. -->
						<aside class="record-activity" aria-label="Commentaires et activité du fournisseur">
							<ActivityFeed ref="feed" :api="activityApi" :version="fournisseur.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<FournisseurDialog v-if="editing && fournisseur" :fournisseur="fournisseur" @close="editing = false" @saved="onSaved" />
		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
	</main>
</template>
