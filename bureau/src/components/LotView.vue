<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideCalendar from '~icons/lucide/calendar'
import LucideCalendarClock from '~icons/lucide/calendar-clock'
import LucideFactory from '~icons/lucide/factory'
import LucideHash from '~icons/lucide/hash'
import LucidePackage from '~icons/lucide/package'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FormDialog from '@shared/components/FormDialog.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import LedgerTable from './LedgerTable.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import { deleteLot, lotActivity, preparerMiseAuRebut, updateLot } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { confirmAction } from '@/lib/confirm'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { etatPeremption } from '@/lib/lots'
import { useLot } from '@/lib/useLot'

const props = defineProps<{ id: string; tab?: string }>()
const emit = defineEmits<{ tab: [tab: string]; changed: []; deleted: [] }>()

const { lot, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useLot(
	() => props.id,
	() => emit('changed'),
	true,
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => lotActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, lot })

const etat = computed(() => (lot.value ? etatPeremption(lot.value) : null))
const tabs = computed(() => {
	const current = lot.value
	if (!current) return []
	const list: { key: string; label: string; count?: number }[] = [{ key: 'stock', label: 'Stock', count: current.depots.length }]
	if (current.mouvements) list.push({ key: 'mouvements', label: 'Mouvements' })
	if (current.tracabilite) list.push({ key: 'tracabilite', label: 'Traçabilité', count: current.tracabilite.length })
	return list
})
const activeTab = computed(() => (tabs.value.some((tab) => tab.key === props.tab) ? props.tab! : 'stock'))

function onTags(tags: string[]) {
	if (lot.value) lot.value.tags = tags
	emit('changed')
}

// Modification : péremption, fabrication, lot du fournisseur, désactivation.
const editing = ref(false)
const form = reactive({ peremption: '', fabrication: '', lot_fournisseur: '', desactive: false })
function openEdit() {
	const current = lot.value
	if (!current) return
	Object.assign(form, { peremption: current.peremption ?? '', fabrication: current.fabrication ?? '', lot_fournisseur: current.lot_fournisseur ?? '', desactive: Boolean(current.desactive) })
	editing.value = true
}
async function save() {
	const current = lot.value
	if (!current) return
	const done = await perform(() => updateLot(current, { peremption: form.peremption, fabrication: form.fabrication, lot_fournisseur: form.lot_fournisseur.trim(), desactive: form.desactive ? 1 : 0 }))
	if (done) {
		editing.value = false
		notice.value = 'Lot enregistré.'
	}
}

// Lot périmé : le transfert vers le rebut se prépare en brouillon, puis s'ouvre pour vérification.
const router = useRouter()
async function mettreAuRebut() {
	const current = lot.value
	if (!current) return
	if (!(await confirmAction({ title: 'Mettre le lot au rebut', message: `Un transfert de ${current.name} vers ${current.depot_rebuts ?? 'le dépôt des rebuts'} sera préparé en brouillon, pour tout son stock hors atelier. Rien ne bouge avant que vous le validiez.`, confirmLabel: 'Préparer le transfert' }))) return
	busy.value = true
	try {
		const { name } = await preparerMiseAuRebut(current.name)
		await router.push({ name: 'MouvementFiche', params: { id: name } })
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}

async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

async function supprimer() {
	const current = lot.value
	if (!current) return
	if (!(await confirmAction({ title: 'Supprimer le lot', message: `Le lot ${current.name} sera supprimé définitivement. S'il a déjà bougé (une pièce le cite), la suppression est refusée et rien ne change.`, confirmLabel: 'Supprimer', danger: true }))) return
	busy.value = true
	actionError.value = ''
	try {
		await deleteLot(current)
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
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Ce lot n'existe pas ou n'existe plus.</div>
		<div v-else-if="!lot" class="card p-8 text-center text-ink-gray-6">Chargement du lot…</div>

		<template v-else>
			<RecordHeader>
				<template #title><span class="tabular-nums">{{ lot.name }}</span></template>
				<template #flags>
					<StatusPill v-if="etat === 'perime'" status="Périmé" tone="red" />
					<StatusPill v-else-if="etat === 'proche'" status="Périme bientôt" tone="amber" />
					<StatusPill v-if="lot.desactive" status="Désactivé" tone="gray" />
				</template>
				<template #sub>
					<RouterLink class="ref-link" :to="{ name: 'Article', params: { id: lot.article } }">{{ lot.designation }}</RouterLink>
					<span class="tabular-nums">{{ formatQty(lot.quantite) }} {{ lot.unite }} en stock</span>
					<div v-if="lot.tags?.length || lot.can_edit"><TagEditor doctype="Batch" :name="lot.name" :modified="lot.modified" :tags="lot.tags" :can-edit="lot.can_edit" @changed="onTags" /></div>
				</template>
				<template #actions>
					<button v-if="lot.can_edit" type="button" class="btn-primary" :disabled="busy" @click="openEdit">Modifier</button>
					<MoreMenu>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Batch', lot.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="lot.can_delete">
							<div class="app-menu-sep"></div>
							<button type="button" class="app-menu-item text-tone-red" role="menuitem" :disabled="busy" @click="supprimer">Supprimer le lot</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations du lot">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucidePackage aria-hidden="true" />Article</dt><dd><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: lot.article } }">{{ lot.designation }}</RouterLink></dd></div>
							<div><dt><LucideCalendarClock aria-hidden="true" />Péremption</dt><dd class="tabular-nums" :class="etat === 'perime' ? 'text-tone-red' : etat === 'proche' ? 'text-tone-amber' : !lot.peremption && 'record-fact-none'">{{ formatDay(lot.peremption) || 'Non renseignée' }}</dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Fabrication</dt><dd class="tabular-nums" :class="!lot.fabrication && 'record-fact-none'">{{ formatDay(lot.fabrication) || 'Non renseignée' }}</dd></div>
							<div><dt><LucideFactory aria-hidden="true" />Origine</dt><dd :class="!lot.origine && 'record-fact-none'">{{ lot.origine || 'Non renseignée' }}<template v-if="lot.ordre"> · <RouterLink class="ref-link" :to="{ name: 'OrdreFiche', params: { id: lot.ordre } }">{{ lot.ordre }}</RouterLink></template></dd></div>
							<div><dt><LucideHash aria-hidden="true" />Lot fournisseur</dt><dd class="tabular-nums" :class="!lot.lot_fournisseur && 'record-fact-none'">{{ lot.lot_fournisseur || 'Non renseigné' }}</dd></div>
							<div v-if="lot.fournisseur"><dt>Fournisseur</dt><dd><RouterLink class="ref-link" :to="{ name: 'Fournisseur', params: { id: lot.fournisseur } }">{{ lot.fournisseur }}</RouterLink></dd></div>
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
						<div class="bureau-center">
							<div v-if="etat === 'perime'" role="status" class="flex flex-wrap items-center gap-2.5 rounded-control tone-red px-3.5 py-2.5">
								<span class="flex-auto">
									<strong class="font-semibold">Lot périmé</strong> depuis le {{ formatDay(lot.peremption) }} : il n'est plus proposé à la vente ni à la production.
									<template v-if="lot.mise_au_rebut"> Un transfert vers {{ lot.depot_rebuts ?? 'le rebut' }} est prêt en brouillon : vérifiez-le, puis validez-le.</template>
									<template v-else-if="lot.a_mettre_au_rebut"> Préparez son transfert vers {{ lot.depot_rebuts }}, ou corrigez sa péremption.</template>
									<template v-else> Corrigez sa péremption s'il est encore bon.</template>
								</span>
								<RouterLink v-if="lot.mise_au_rebut" class="btn-secondary" :to="{ name: 'MouvementFiche', params: { id: lot.mise_au_rebut } }">Ouvrir {{ lot.mise_au_rebut }}</RouterLink>
								<button v-else-if="lot.a_mettre_au_rebut && canCreate('Stock Entry')" type="button" class="btn-secondary" :disabled="busy" @click="mettreAuRebut">Préparer le transfert au rebut</button>
							</div>
							<section v-if="activeTab === 'stock'" class="card ref-card">
								<h3>Stock par dépôt</h3>
								<p v-if="!lot.depots.length" class="text-ink-gray-6">Plus rien en stock.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Dépôt</th><th class="end">Quantité</th></tr></thead>
									<tbody><tr v-for="row in lot.depots" :key="row.depot"><td><RouterLink class="ref-link" :to="{ name: 'Depot', params: { id: row.depot } }">{{ row.depot }}</RouterLink></td><td class="end tabular-nums">{{ formatQty(row.qty) }} {{ lot.unite }}</td></tr></tbody>
								</table></div>
							</section>
							<section v-else-if="activeTab === 'mouvements' && lot.mouvements" class="card ref-card">
								<h3>Mouvements du lot</h3>
								<LedgerTable :rows="lot.mouvements" :show-article="false" :show-lots="false" empty="Ce lot n'a pas encore bougé." />
							</section>
							<section v-else-if="activeTab === 'tracabilite' && lot.tracabilite" class="card ref-card">
								<h3>Ordres de production</h3>
								<p v-if="!lot.tracabilite.length" class="text-ink-gray-6">Ce lot n'apparaît dans aucun ordre de production.</p>
								<div v-else class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Sens</th><th>Ordre</th><th>Date</th><th>Produit</th><th>Lot matière</th><th>Lot produit</th><th class="end">Quantité</th></tr></thead>
									<tbody>
										<tr v-for="(row, index) in lot.tracabilite" :key="`${row.ordre}-${index}`">
											<td>{{ row.sens }}</td>
											<td><RouterLink class="ref-link tabular-nums" :to="{ name: 'OrdreFiche', params: { id: row.ordre } }">{{ row.ordre }}</RouterLink><span v-if="row.statut" class="block text-xs text-ink-gray-6">{{ row.statut }}</span></td>
											<td class="tabular-nums">{{ formatDay(row.date) }}</td>
											<td>{{ row.produit || '—' }}</td>
											<td class="tabular-nums"><RouterLink v-if="row.lot_mp && row.lot_mp !== lot.name" class="ref-link" :to="{ name: 'Lot', params: { id: row.lot_mp } }">{{ row.lot_mp }}</RouterLink><template v-else>{{ row.lot_mp || '—' }}</template></td>
											<td class="tabular-nums"><RouterLink v-if="row.lot_pf && row.lot_pf !== lot.name" class="ref-link" :to="{ name: 'Lot', params: { id: row.lot_pf } }">{{ row.lot_pf }}</RouterLink><template v-else>{{ row.lot_pf || '—' }}</template></td>
											<td class="end tabular-nums">{{ formatQty(row.quantite) }}<span v-if="row.quantite_pf" class="block text-xs text-ink-gray-6">{{ formatQty(row.quantite_pf) }} produits</span></td>
										</tr>
									</tbody>
								</table></div>
							</section>
						</div>

						<aside class="record-activity" aria-label="Commentaires et activité du lot">
							<ActivityFeed ref="feed" :api="activityApi" :version="lot.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<FormDialog v-if="editing && lot" :title="`Modifier le lot ${lot.name}`" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour enregistrer" @close="editing = false" @submit="save">
			<div class="form-grid">
				<div class="form-field">
					<label class="field-label" for="lot-peremption">Péremption</label>
					<input id="lot-peremption" v-model="form.peremption" class="field-input tabular-nums" type="date" />
				</div>
				<div class="form-field">
					<label class="field-label" for="lot-fabrication">Fabrication</label>
					<input id="lot-fabrication" v-model="form.fabrication" class="field-input tabular-nums" type="date" />
				</div>
				<div class="form-field">
					<label class="field-label" for="lot-fournisseur">Lot du fournisseur</label>
					<input id="lot-fournisseur" v-model="form.lot_fournisseur" class="field-input tabular-nums" autocomplete="off" />
				</div>
			</div>
			<label class="flex items-center gap-2 text-sm"><input v-model="form.desactive" type="checkbox" />Lot désactivé (il n'est plus proposé dans les pièces)</label>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ actionError }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="save">{{ busy ? 'Enregistrement…' : 'Enregistrer' }}</button>
			</template>
		</FormDialog>
		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
	</main>
</template>
