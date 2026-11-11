<script setup lang="ts">
import { computed, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideFolderTree from '~icons/lucide/folder-tree'
import LucidePackage from '~icons/lucide/package'
import LucideTag from '~icons/lucide/tag'
import LucideWallet from '~icons/lucide/wallet'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import DepotDialog from './DepotDialog.vue'
import LedgerTable from './LedgerTable.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import { deleteDepot, depotActivity } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { confirmAction } from '@/lib/confirm'
import type { DepotDetail } from '@/lib/depots'
import { deskUrl } from '@/lib/display'
import { useDepot } from '@/lib/useDepot'

const props = defineProps<{ id: string; tab?: string }>()
const emit = defineEmits<{ tab: [tab: string]; changed: []; deleted: [] }>()

const { depot, error, notFound, actionError, notice, noticeTone, busy, load, refresh } = useDepot(
	() => props.id,
	() => emit('changed'),
	true,
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => depotActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, depot })

const tabs = computed(() => {
	const current = depot.value
	if (!current) return []
	const list: { key: string; label: string; count?: number }[] = []
	if (current.stock) list.push({ key: 'stock', label: 'Stock', count: current.stock.length })
	if (current.mouvements) list.push({ key: 'mouvements', label: 'Mouvements' })
	return list
})
const activeTab = computed(() => (tabs.value.some((tab) => tab.key === props.tab) ? props.tab! : (tabs.value[0]?.key ?? '')))

function onTags(tags: string[]) {
	if (depot.value) depot.value.tags = tags
	emit('changed')
}

const editing = ref(false)
function onSaved(updated: DepotDetail) {
	depot.value = updated
	notice.value = 'Dépôt enregistré.'
	emit('changed')
}

async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

// Suppression : Frappe refuse tant que le dépôt a du stock ou des écritures, et le message le dit.
async function supprimer() {
	const current = depot.value
	if (!current) return
	if (!(await confirmAction({ title: 'Supprimer le dépôt', message: `Le dépôt ${current.name} sera supprimé définitivement. S'il a du stock ou des écritures, la suppression est refusée et rien ne change.`, confirmLabel: 'Supprimer', danger: true }))) return
	busy.value = true
	actionError.value = ''
	try {
		await deleteDepot(current)
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
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Ce dépôt n'existe pas ou n'existe plus.</div>
		<div v-else-if="!depot" class="card p-8 text-center text-ink-gray-6">Chargement du dépôt…</div>

		<template v-else>
			<RecordHeader>
				<template #title>{{ depot.depot }}</template>
				<template #flags><StatusPill v-if="depot.desactive" status="Désactivé" tone="gray" /></template>
				<template #sub>
					<span class="tabular-nums">{{ depot.name }}</span>
					<span v-if="depot.parent">{{ depot.parent }}</span>
					<div v-if="depot.tags?.length || depot.can_edit"><TagEditor doctype="Warehouse" :name="depot.name" :modified="depot.modified" :tags="depot.tags" :can-edit="depot.can_edit" @changed="onTags" /></div>
				</template>
				<template #actions>
					<button v-if="depot.can_edit" type="button" class="btn-primary" :disabled="busy" @click="editing = true">Modifier</button>
					<MoreMenu>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Warehouse', depot.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="depot.can_delete">
							<div class="app-menu-sep"></div>
							<button type="button" class="app-menu-item text-tone-red" role="menuitem" :disabled="busy" @click="supprimer">Supprimer le dépôt</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations du dépôt">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucideFolderTree aria-hidden="true" />Groupe</dt><dd :class="!depot.parent && 'record-fact-none'">{{ depot.parent || 'Aucun' }}</dd></div>
							<div><dt><LucideTag aria-hidden="true" />Type</dt><dd :class="!depot.type && 'record-fact-none'">{{ depot.type || 'Non renseigné' }}</dd></div>
							<div v-if="depot.articles !== null"><dt><LucidePackage aria-hidden="true" />Articles en stock</dt><dd class="tabular-nums">{{ depot.articles }}</dd></div>
							<div v-if="depot.valeur !== null"><dt><LucideWallet aria-hidden="true" />Valeur du stock</dt><dd class="tabular-nums">{{ formatAmount(depot.valeur) }} DA</dd></div>
							<div v-if="depot.compte"><dt>Compte de stock</dt><dd>{{ depot.compte }}</dd></div>
						</dl>
					</div>
				</aside>

				<div class="client-main">
					<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
					<div v-if="tabs.length" class="record-tabs" role="tablist">
						<button v-for="item in tabs" :key="item.key" type="button" class="record-tab" role="tab" :aria-selected="activeTab === item.key" @click="emit('tab', item.key)">
							{{ item.label }}<span v-if="item.count" class="ml-1 tabular-nums text-ink-gray-6">{{ item.count }}</span>
						</button>
					</div>

					<div class="bureau-detail">
						<div class="bureau-center">
							<section v-if="activeTab === 'stock' && depot.stock" class="card ref-card">
								<h3>Stock du dépôt</h3>
								<p v-if="!depot.stock.length" class="text-ink-gray-6">Aucun article dans ce dépôt.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Article</th><th class="end">En stock</th><th class="end">Réservé</th><th class="end">Projeté</th><th class="end">Valeur (DA)</th></tr></thead>
									<tbody>
										<tr v-for="row in depot.stock" :key="row.article">
											<td><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: row.article } }">{{ row.designation }}</RouterLink><span class="ml-1 text-xs tabular-nums text-ink-gray-6">{{ row.article }}</span></td>
											<td class="end tabular-nums" :class="row.quantite < 0 && 'font-semibold text-tone-red'">{{ formatQty(row.quantite) }} <span class="text-xs text-ink-gray-6">{{ row.unite }}</span></td>
											<td class="end tabular-nums" :class="!row.reserve && 'text-ink-gray-6'">{{ formatQty(row.reserve) }}</td>
											<td class="end tabular-nums">{{ formatQty(row.projete) }}</td>
											<td class="end tabular-nums">{{ formatAmount(row.valeur) }}</td>
										</tr>
									</tbody>
								</table></div>
							</section>
							<section v-else-if="activeTab === 'mouvements' && depot.mouvements" class="card ref-card">
								<h3>Derniers mouvements</h3>
								<LedgerTable :rows="depot.mouvements" :show-depot="false" empty="Aucun mouvement dans ce dépôt." />
							</section>
						</div>

						<aside class="record-activity" aria-label="Commentaires et activité du dépôt">
							<ActivityFeed ref="feed" :api="activityApi" :version="depot.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<DepotDialog v-if="editing && depot" :depot="depot" @close="editing = false" @saved="onSaved" />
		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
	</main>
</template>
