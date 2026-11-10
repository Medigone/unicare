<script setup lang="ts">
import { computed, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideBarcode from '~icons/lucide/barcode'
import LucideBoxes from '~icons/lucide/boxes'
import LucideCalendar from '~icons/lucide/calendar'
import LucideFolder from '~icons/lucide/folder'
import LucideHourglass from '~icons/lucide/hourglass'
import LucideLayers from '~icons/lucide/layers'
import LucideRuler from '~icons/lucide/ruler'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import ListState from '@shared/components/ListState.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import ArticleDialog from './ArticleDialog.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import { articleActivity } from '@/lib/api'
import { formatQty, type ArticleDetail, type ArticleMouvement, type MouvementKey } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { deskUrl, formatDay } from '@/lib/display'
import { useArticle } from '@/lib/useArticle'

const props = defineProps<{ id: string; tab?: string }>()
const emit = defineEmits<{ tab: [tab: string]; changed: [] }>()

const { article, error, notFound, actionError, notice, noticeTone, busy, load, refresh } = useArticle(
	() => props.id,
	() => emit('changed'),
	true,
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => articleActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, article })

/** Achats et ventes, dans l'ordre du flux. Le tiers est un fournisseur pour les achats, un client pour les ventes. */
const MOUVEMENTS: { key: MouvementKey; title: string; piece: string; doctype: string; tiers: string; empty: string }[] = [
	{ key: 'commandes_achat', title: "Commandes d'achat", piece: 'Commande achat', doctype: 'Purchase Order', tiers: 'Fournisseur', empty: "Aucune commande d'achat." },
	{ key: 'receptions', title: 'Réceptions', piece: 'Réception', doctype: 'Purchase Receipt', tiers: 'Fournisseur', empty: 'Aucune réception.' },
	{ key: 'commandes_vente', title: 'Commandes client', piece: 'Commande client', doctype: 'Sales Order', tiers: 'Client', empty: 'Aucune commande client.' },
	{ key: 'factures', title: 'Factures', piece: 'Facture', doctype: 'Sales Invoice', tiers: 'Client', empty: 'Aucune facture.' },
]
const shownMouvements = computed(() => MOUVEMENTS.filter((group) => article.value?.mouvements?.[group.key]))
const mouvementCount = computed(() => shownMouvements.value.reduce((total, group) => total + (article.value?.mouvements?.[group.key]?.length ?? 0), 0))
const recetteCount = computed(() => (article.value?.recettes ? article.value.recettes.produit.length + article.value.recettes.ingredient.length : 0))
const ordreCount = computed(() => (article.value?.ordres ? article.value.ordres.produit.length + article.value.ordres.matiere.length : 0))

const tabs = computed(() => {
	const current = article.value
	if (!current) return []
	const list: { key: string; label: string; count?: number }[] = [{ key: 'apercu', label: 'Aperçu' }]
	if (current.bins || current.lots) list.push({ key: 'stock', label: 'Stock et lots', count: current.lots?.length })
	if (current.recettes) list.push({ key: 'recettes', label: 'Recettes', count: recetteCount.value })
	if (current.ordres) list.push({ key: 'ordres', label: 'Ordres de conditionnement', count: ordreCount.value })
	if (shownMouvements.value.length) list.push({ key: 'mouvements', label: 'Achats et ventes', count: mouvementCount.value })
	list.push({ key: 'infos', label: 'Informations' })
	return list
})
const activeTab = computed(() => (tabs.value.some((tab) => tab.key === props.tab) ? props.tab! : 'apercu'))

// Lots encore en stock qui périment dans les 90 jours, ou déjà périmés.
const today = new Date().toISOString().slice(0, 10)
const soon = new Date(Date.now() + 90 * 86400000).toISOString().slice(0, 10)
const expiring = computed(() => (article.value?.lots ?? []).filter((lot) => !lot.disabled && lot.batch_qty > 0 && lot.expiry_date && lot.expiry_date <= soon))
const expired = computed(() => expiring.value.filter((lot) => lot.expiry_date! < today))
const activeLots = computed(() => (article.value?.lots ?? []).filter((lot) => !lot.disabled && lot.batch_qty > 0))

interface Mouvement extends ArticleMouvement {
	piece: string
	doctype: string
}
function mouvements(current: ArticleDetail): Mouvement[] {
	return MOUVEMENTS.flatMap((group) => (current.mouvements?.[group.key] ?? []).map((row) => ({ ...row, piece: group.piece, doctype: group.doctype })))
}
const lastMouvements = computed(() => (article.value ? mouvements(article.value).sort((a, b) => String(b.date).localeCompare(String(a.date))).slice(0, 5) : []))

function ordreStatus(row: { workflow_state: string | null; docstatus: number }) {
	return row.workflow_state || (row.docstatus === 2 ? 'Annulé' : row.docstatus === 1 ? 'Validé' : 'Brouillon')
}
function onTags(tags: string[]) {
	if (article.value) article.value.tags = tags
	emit('changed')
}
function newOnDesk(doctype: string, field: string) {
	return `${deskUrl(doctype, 'new')}?${field}=${encodeURIComponent(props.id)}`
}
async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

const editing = ref(false)
function onSaved(updated: ArticleDetail) {
	article.value = updated
	notice.value = 'Article enregistré.'
	emit('changed')
}
</script>

<template>
	<main class="bureau-main">
		<div v-if="error" role="alert" class="card p-3.5 text-tone-red">
			{{ error }}
			<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
		</div>
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Cet article n'existe pas ou n'existe plus.</div>
		<div v-else-if="!article" class="card p-8 text-center text-ink-gray-6">Chargement de l'article…</div>

		<template v-else>
			<RecordHeader>
				<template #title>{{ article.designation }}</template>
				<template #flags>
					<span v-if="article.type" class="record-flag">{{ article.type }}</span>
					<StatusPill v-if="article.disabled" status="Désactivé" tone="gray" />
				</template>
				<template #sub>
					<span class="tabular-nums">{{ article.name }}</span>
					<span v-if="article.groupe">{{ article.groupe }}</span>
					<div v-if="article.tags?.length || article.can_edit"><TagEditor doctype="Item" :name="article.name" :modified="article.modified" :tags="article.tags" :can-edit="article.can_edit" @changed="onTags" /></div>
				</template>
				<template #actions>
					<button v-if="article.can_edit" type="button" class="btn-primary" :disabled="busy" @click="editing = true">Modifier</button>
					<MoreMenu>
						<a v-if="article.type === 'Produit fini' && article.recettes" class="app-menu-item" role="menuitem" :href="newOnDesk('Recette de Conditionnement', 'produit_fini')" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Nouvelle recette</a>
						<a v-if="article.type === 'Produit fini' && article.ordres" class="app-menu-item" role="menuitem" :href="newOnDesk('Ordre de Conditionnement', 'produit_fini')" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Nouvel ordre de conditionnement</a>
						<div v-if="article.type === 'Produit fini' && (article.recettes || article.ordres)" class="app-menu-sep"></div>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Item', article.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations de l'article">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucideLayers aria-hidden="true" />Type</dt><dd :class="!article.type && 'record-fact-none'">{{ article.type || 'Non renseigné' }}</dd></div>
							<div><dt><LucideFolder aria-hidden="true" />Groupe</dt><dd>{{ article.groupe || '—' }}</dd></div>
							<div><dt><LucideRuler aria-hidden="true" />Unité de stock</dt><dd>{{ article.uom || '—' }}</dd></div>
							<div v-if="article.stock !== null"><dt><LucideBoxes aria-hidden="true" />Stock</dt><dd class="tabular-nums" :class="!article.stock && 'record-fact-none'">{{ formatQty(article.stock) }} {{ article.uom }}</dd></div>
							<div v-else-if="!article.is_stock_item"><dt><LucideBoxes aria-hidden="true" />Stock</dt><dd class="record-fact-none">Article hors stock</dd></div>
							<div><dt><LucideHourglass aria-hidden="true" />Conservation</dt><dd class="tabular-nums" :class="!article.shelf_life_in_days && 'record-fact-none'">{{ article.shelf_life_in_days ? `${article.shelf_life_in_days} jours` : 'Non renseignée' }}</dd></div>
							<div v-if="article.barcodes.length"><dt><LucideBarcode aria-hidden="true" />Code-barres</dt><dd class="tabular-nums">{{ article.barcodes.join(', ') }}</dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Créé le</dt><dd class="tabular-nums">{{ formatDay(article.depuis) || '—' }}</dd></div>
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
						<!-- Aperçu : il résume les autres onglets. -->
						<div v-if="activeTab === 'apercu'" class="bureau-center">
							<div v-if="expiring.length" role="status" class="rounded-control px-3.5 py-2.5" :class="expired.length ? 'tone-red' : 'tone-amber'">
								<strong class="font-semibold">
									<template v-if="expired.length">{{ expired.length > 1 ? `${expired.length} lots périmés` : '1 lot périmé' }} encore en stock</template>
									<template v-else>{{ expiring.length > 1 ? `${expiring.length} lots périment` : '1 lot périme' }} dans les 90 jours</template>
								</strong>.
								<button type="button" class="font-medium underline" @click="emit('tab', 'stock')">Voir les lots</button>
							</div>
							<div class="client-cards">
								<section v-if="article.bins" class="card ref-card">
									<div class="ref-card-head"><h3>Stock</h3><button type="button" class="ref-link" @click="emit('tab', 'stock')">Voir le détail</button></div>
									<div class="amount-row"><span class="amount tabular-nums">{{ formatQty(article.stock) }} {{ article.uom }}</span></div>
									<dl class="kv">
										<div v-for="bin in article.bins.filter((row) => row.actual_qty).slice(0, 3)" :key="bin.warehouse"><dt>{{ bin.warehouse }}</dt><dd class="tabular-nums">{{ formatQty(bin.actual_qty) }}</dd></div>
										<div v-if="article.lots"><dt>Lots en stock</dt><dd class="tabular-nums">{{ activeLots.length }}</dd></div>
									</dl>
								</section>
								<section class="card ref-card">
									<h3>Identité</h3>
									<dl class="kv">
										<div><dt>Désignation</dt><dd>{{ article.designation }}</dd></div>
										<div><dt>Code</dt><dd class="tabular-nums">{{ article.name }}</dd></div>
										<div><dt>Type</dt><dd>{{ article.type || '—' }}</dd></div>
										<div><dt>Groupe</dt><dd>{{ article.groupe || '—' }}</dd></div>
										<div><dt>Unité de stock</dt><dd>{{ article.uom || '—' }}</dd></div>
										<div><dt>Géré par lots</dt><dd>{{ article.has_batch_no ? 'Oui' : 'Non' }}</dd></div>
									</dl>
								</section>
							</div>
							<section v-if="shownMouvements.length" class="card ref-card">
								<div class="ref-card-head"><h3>Derniers achats et ventes</h3><button v-if="mouvementCount > lastMouvements.length" type="button" class="ref-link" @click="emit('tab', 'mouvements')">Tout voir</button></div>
								<p v-if="!lastMouvements.length" class="text-ink-gray-6">Aucun achat ni vente de cet article.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Pièce</th><th>Numéro</th><th>Date</th><th>Tiers</th><th class="end">Quantité</th></tr></thead>
									<tbody><tr v-for="row in lastMouvements" :key="`${row.doctype}-${row.name}`"><td>{{ row.piece }}</td><td><a class="ref-link" :href="deskUrl(row.doctype, row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td>{{ row.tiers || '—' }}</td><td class="end tabular-nums">{{ formatQty(row.qty) }} {{ row.uom }}</td></tr></tbody>
								</table></div>
							</section>
						</div>

						<!-- Stock et lots. -->
						<div v-else-if="activeTab === 'stock'" class="bureau-center">
							<section v-if="article.bins" class="card ref-card">
								<h3>Stock par dépôt</h3>
								<p v-if="!article.bins.length" class="text-ink-gray-6">Aucun mouvement de stock pour cet article.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Dépôt</th><th class="end">En stock</th><th class="end">Réservé</th><th class="end">Commandé</th><th class="end">Prévisionnel</th></tr></thead>
									<tbody><tr v-for="bin in article.bins" :key="bin.warehouse"><td>{{ bin.warehouse }}</td><td class="end tabular-nums" :class="!bin.actual_qty && 'text-ink-gray-6'">{{ formatQty(bin.actual_qty) }}</td><td class="end tabular-nums" :class="!bin.reserved_qty && 'text-ink-gray-6'">{{ formatQty(bin.reserved_qty) }}</td><td class="end tabular-nums" :class="!bin.ordered_qty && 'text-ink-gray-6'">{{ formatQty(bin.ordered_qty) }}</td><td class="end tabular-nums">{{ formatQty(bin.projected_qty) }}</td></tr></tbody>
								</table></div>
							</section>
							<section v-if="article.lots" class="card ref-card">
								<h3>Lots</h3>
								<ListState v-if="!article.lots.length" illustration title="Aucun lot" text="Les lots se créent à la réception des matières ou à la clôture d'un ordre de conditionnement." />
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Lot</th><th>Origine</th><th>Lot fournisseur</th><th>Fabriqué le</th><th>Périme le</th><th class="end">Quantité</th></tr></thead>
									<tbody>
										<tr v-for="lot in article.lots" :key="lot.name" :class="{ 'text-ink-gray-6': lot.disabled }">
											<td><a class="ref-link tabular-nums" :href="deskUrl('Batch', lot.name)" target="_blank" rel="noopener noreferrer">{{ lot.name }}</a></td>
											<td>
												<a v-if="lot.ordre" class="ref-link" :href="deskUrl('Ordre de Conditionnement', lot.ordre)" target="_blank" rel="noopener noreferrer">{{ lot.origine || 'Production' }}</a>
												<template v-else>{{ lot.origine || '—' }}</template>
											</td>
											<td class="tabular-nums">{{ lot.lot_fournisseur || '—' }}</td>
											<td class="tabular-nums">{{ formatDay(lot.manufacturing_date) || '—' }}</td>
											<td class="tabular-nums" :class="lot.expiry_date && lot.batch_qty > 0 && lot.expiry_date <= soon && (lot.expiry_date < today ? 'text-tone-red font-semibold' : 'text-tone-amber font-semibold')">{{ formatDay(lot.expiry_date) || '—' }}</td>
											<td class="end tabular-nums" :class="!lot.batch_qty && 'text-ink-gray-6'">{{ formatQty(lot.batch_qty) }}</td>
										</tr>
									</tbody>
								</table></div>
							</section>
						</div>

						<!-- Recettes. -->
						<div v-else-if="activeTab === 'recettes' && article.recettes" class="bureau-center">
							<section v-if="article.type === 'Produit fini' || article.recettes.produit.length" class="card ref-card">
								<div class="ref-card-head"><h3>Recettes de ce produit</h3><a class="ref-link" :href="newOnDesk('Recette de Conditionnement', 'produit_fini')" target="_blank" rel="noopener noreferrer">Nouvelle recette</a></div>
								<p v-if="!article.recettes.produit.length" class="text-ink-gray-6">Aucune recette ne produit cet article.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Recette</th><th>Statut</th><th class="end">Quantité de base</th><th class="end">Rendement théorique</th></tr></thead>
									<tbody><tr v-for="row in article.recettes.produit" :key="row.name"><td><a class="ref-link" :href="deskUrl('Recette de Conditionnement', row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td><td><StatusPill :status="row.actif ? 'Active' : 'Inactive'" :tone="row.actif ? 'green' : 'gray'" /></td><td class="end tabular-nums">{{ formatQty(row.quantite_base) }} {{ row.uom }}</td><td class="end tabular-nums">{{ row.rendement_theorique ? `${formatQty(row.rendement_theorique)} %` : '—' }}</td></tr></tbody>
								</table></div>
							</section>
							<section v-if="article.type !== 'Produit fini' || article.recettes.ingredient.length" class="card ref-card">
								<h3>Entre dans les recettes</h3>
								<p v-if="!article.recettes.ingredient.length" class="text-ink-gray-6">Cet article n'entre dans aucune recette.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Recette</th><th>Produit fini</th><th>Statut</th><th class="end">Quantité</th></tr></thead>
									<tbody><tr v-for="row in article.recettes.ingredient" :key="row.name"><td><a class="ref-link" :href="deskUrl('Recette de Conditionnement', row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td><td><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: row.produit_fini! } }">{{ row.nom_produit || row.produit_fini }}</RouterLink></td><td><StatusPill :status="row.actif ? 'Active' : 'Inactive'" :tone="row.actif ? 'green' : 'gray'" /></td><td class="end tabular-nums">{{ formatQty(row.qty) }} {{ row.uom }}</td></tr></tbody>
								</table></div>
							</section>
						</div>

						<!-- Ordres de conditionnement. -->
						<div v-else-if="activeTab === 'ordres' && article.ordres" class="bureau-center">
							<section v-for="group in [{ key: 'produit', title: 'Ordres qui produisent cet article', rows: article.ordres.produit, empty: 'Aucun ordre ne produit cet article.', show: article.type === 'Produit fini' || article.ordres.produit.length > 0 }, { key: 'matiere', title: 'Ordres qui consomment cet article', rows: article.ordres.matiere, empty: 'Aucun ordre ne consomme cet article.', show: article.type !== 'Produit fini' || article.ordres.matiere.length > 0 }].filter((item) => item.show)" :key="group.key" class="card ref-card">
								<h3>{{ group.title }}</h3>
								<p v-if="!group.rows.length" class="text-ink-gray-6">{{ group.empty }}</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Ordre</th><th v-if="group.key === 'matiere'">Produit fini</th><th>Date prévue</th><th>Statut</th><th class="end">Prévu</th><th class="end">Réel</th></tr></thead>
									<tbody>
										<tr v-for="row in group.rows" :key="row.name">
											<td><a class="ref-link" :href="deskUrl('Ordre de Conditionnement', row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td>
											<td v-if="group.key === 'matiere'"><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: row.produit_fini } }">{{ row.nom_produit || row.produit_fini }}</RouterLink></td>
											<td class="tabular-nums">{{ formatDay(row.date_prevue) || '—' }}</td>
											<td><StatusPill :status="ordreStatus(row)" /></td>
											<td class="end tabular-nums">{{ row.qty_prevue === null ? '—' : `${formatQty(row.qty_prevue)} ${row.uom ?? ''}` }}</td>
											<td class="end tabular-nums" :class="!row.qty_reelle_pf && 'text-ink-gray-6'">{{ row.qty_reelle_pf ? `${formatQty(row.qty_reelle_pf)} ${row.uom ?? ''}` : '—' }}</td>
										</tr>
									</tbody>
								</table></div>
							</section>
						</div>

						<!-- Achats et ventes. -->
						<div v-else-if="activeTab === 'mouvements'" class="bureau-center">
							<section v-for="group in shownMouvements" :key="group.key" class="card ref-card">
								<h3>{{ group.title }}</h3>
								<p v-if="!article.mouvements?.[group.key]?.length" class="text-ink-gray-6">{{ group.empty }}</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Numéro</th><th>Date</th><th>{{ group.tiers }}</th><th>Statut</th><th class="end">Quantité</th><th class="end">Montant (DA)</th></tr></thead>
									<tbody>
										<tr v-for="(row, index) in article.mouvements?.[group.key] ?? []" :key="`${row.name}-${index}`">
											<td><a class="ref-link" :href="deskUrl(group.doctype, row.name)" target="_blank" rel="noopener noreferrer">{{ row.name }}</a></td>
											<td class="tabular-nums">{{ formatDay(row.date) }}</td>
											<td>{{ row.tiers || '—' }}</td>
											<td><StatusPill :status="row.status" /></td>
											<td class="end tabular-nums">{{ formatQty(row.qty) }} {{ row.uom }}</td>
											<td class="end tabular-nums">{{ formatAmount(row.montant) }}</td>
										</tr>
									</tbody>
								</table></div>
							</section>
						</div>

						<!-- Informations. -->
						<div v-else-if="activeTab === 'infos'" class="info-grid">
							<section class="card ref-card">
								<h3>Gestion</h3>
								<dl class="kv">
									<div><dt>Article de stock</dt><dd>{{ article.is_stock_item ? 'Oui' : 'Non' }}</dd></div>
									<div><dt>Géré par lots</dt><dd>{{ article.has_batch_no ? 'Oui' : 'Non' }}</dd></div>
									<div><dt>Conservation</dt><dd class="tabular-nums">{{ article.shelf_life_in_days ? `${article.shelf_life_in_days} jours` : '—' }}</dd></div>
									<div><dt>Acheté</dt><dd>{{ article.is_purchase_item ? 'Oui' : 'Non' }}</dd></div>
									<div><dt>Vendu</dt><dd>{{ article.is_sales_item ? 'Oui' : 'Non' }}</dd></div>
									<div><dt>État</dt><dd>{{ article.disabled ? 'Désactivé' : 'Actif' }}</dd></div>
								</dl>
							</section>
							<section class="card ref-card">
								<h3>Description</h3>
								<p v-if="article.description" class="whitespace-pre-line">{{ article.description }}</p>
								<p v-else class="text-ink-gray-6">Aucune description.</p>
							</section>
							<section class="card ref-card">
								<div class="ref-card-head"><h3>Codes-barres</h3><a class="ref-link" :href="deskUrl('Item', article.name)" target="_blank" rel="noopener noreferrer">Gérer sur le Desk</a></div>
								<p v-if="!article.barcodes.length" class="text-ink-gray-6">Aucun code-barres.</p>
								<p v-for="code in article.barcodes" :key="code" class="tabular-nums">{{ code }}</p>
							</section>
						</div>

						<!-- Le fil vient après le contenu, quel que soit l'onglet. -->
						<aside class="record-activity" aria-label="Commentaires et activité de l'article">
							<ActivityFeed ref="feed" :api="activityApi" :version="article.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<ArticleDialog v-if="editing && article" :article="article" @close="editing = false" @saved="onSaved" />
		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
	</main>
</template>
