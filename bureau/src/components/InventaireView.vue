<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideCalendar from '~icons/lucide/calendar'
import LucidePlus from '~icons/lucide/plus'
import LucidePrinter from '~icons/lucide/printer'
import LucideTrash2 from '~icons/lucide/trash-2'
import LucideUser from '~icons/lucide/user'
import LucideWarehouse from '~icons/lucide/warehouse'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FormDialog from '@shared/components/FormDialog.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import ChoicePicker from './ChoicePicker.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import VersionsCard from './VersionsCard.vue'
import { compterInventaire, createPieceVersion, deleteInventaire, inventaireActivity, inventairePrintUrl, runInventaireAction, searchStockArticles } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { confirmAction } from '@/lib/confirm'
import { canCreate } from '@/lib/droits'
import { deskUrl, formatDay } from '@/lib/display'
import { changedCounts, parseCount, resumeSaisie, type InventaireLine } from '@/lib/inventaires'
import type { StockArticleChoice } from '@/lib/mouvements'
import { signedQty } from '@/lib/stock'
import { useInventaire } from '@/lib/useInventaire'

const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: []; deleted: [] }>()

const { inventaire, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useInventaire(
	() => props.id,
	() => emit('changed'),
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => inventaireActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	// Un comptage en cours n'est pas écrasé par un changement venu d'ailleurs : l'enregistrement le signalera.
	if (dirty.value) return
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, inventaire })

const can = (action: string) => Boolean(inventaire.value?.actions.includes(action as never))
const counting = computed(() => can('compter'))

// Feuille de comptage : les quantités saisies, remises à zéro à chaque version reçue du serveur.
const counts = ref<Record<string, string>>({})
const filter = ref<'toutes' | 'ecarts'>('toutes')
watch(
	() => inventaire.value?.modified,
	() => {
		counts.value = Object.fromEntries((inventaire.value?.lignes ?? []).map((line) => [line.name, String(line.compte)]))
	},
	{ immediate: true },
)
const changes = computed(() => changedCounts(inventaire.value?.lignes ?? [], counts.value))
const dirty = computed(() => changes.value.length > 0)
const resume = computed(() => (inventaire.value ? (counting.value ? resumeSaisie(inventaire.value.lignes, counts.value) : inventaire.value.resume) : null))
function ecartOf(line: InventaireLine) {
	const compte = counting.value ? parseCount(counts.value[line.name] ?? '') : line.compte
	return Number.isFinite(compte) ? Math.round((compte - line.theorique) * 1000) / 1000 : 0
}
const shown = computed(() => (inventaire.value?.lignes ?? []).filter((line) => filter.value === 'toutes' || ecartOf(line)))

async function saveCounts() {
	const current = inventaire.value
	if (!current || !changes.value.length) return true
	if (changes.value.some((line) => !(line.quantite >= 0))) {
		actionError.value = 'Une quantité comptée est illisible ou négative.'
		return false
	}
	const done = await perform(() => compterInventaire(current, { lignes: changes.value }))
	if (done) notice.value = 'Comptage enregistré.'
	return done
}
async function removeLine(line: InventaireLine) {
	const current = inventaire.value
	if (!current) return
	if (!(await saveCounts())) return
	const fresh = inventaire.value
	if (fresh) await perform(() => compterInventaire(fresh, { retirer: [line.name] }))
}

// Ajout d'un article (ou d'un lot) trouvé au comptage et absent de la feuille.
const adding = ref(false)
const ajout = ref({ article: '', label: '', avec_lot: false, lot: '', quantite: '' })
const ajoutError = ref('')
const findArticles = async (query: string) => (await searchStockArticles(query, inventaire.value?.depot ?? undefined)).map((item) => ({ ...item, hint: item.avec_lot ? 'suivi par lots' : item.uom }))
function pickArticle(choice: StockArticleChoice) {
	ajout.value = { ...ajout.value, article: choice.name, label: choice.label, avec_lot: Boolean(choice.avec_lot), lot: '' }
}
async function addLine() {
	const current = inventaire.value
	if (!current) return
	const quantite = parseCount(ajout.value.quantite)
	ajoutError.value = !ajout.value.article ? "Choisissez l'article." : ajout.value.avec_lot && !ajout.value.lot.trim() ? 'Saisissez le lot compté.' : !(quantite >= 0) ? 'Saisissez la quantité comptée.' : ''
	if (ajoutError.value) return
	if (!(await saveCounts())) return
	const fresh = inventaire.value
	if (!fresh) return
	const done = await perform(() => compterInventaire(fresh, { ajouts: [{ article: ajout.value.article, lot: ajout.value.lot.trim() || undefined, quantite }] }))
	if (done) {
		adding.value = false
		ajout.value = { article: '', label: '', avec_lot: false, lot: '', quantite: '' }
		notice.value = 'Ligne ajoutée.'
	}
}

async function valider() {
	const current = inventaire.value
	const summary = resume.value
	if (!current || !summary) return
	if (!(await confirmAction({
		title: "Valider l'inventaire",
		message: `${summary.ecarts} ligne${summary.ecarts > 1 ? 's' : ''} avec écart sur ${summary.lignes} : ${signedQty(summary.plus)} en surplus, ${signedQty(summary.moins)} manquant, pour ${formatAmount(summary.valeur)} DA.\nLe stock de ${current.depot ?? 'ce dépôt'} sera ajusté au comptage, à la date et l'heure de maintenant. Les lignes sans écart ne sont pas gardées.`,
		confirmLabel: "Valider l'inventaire",
	}))) return
	if (!(await saveCounts())) return
	const saved = inventaire.value
	if (!saved || saved.blocked.length) return
	if (await perform(() => runInventaireAction(saved, 'valider'))) notice.value = 'Inventaire validé : le stock est ajusté.'
}

async function copyLink() {
	try {
		await navigator.clipboard.writeText(window.location.href)
		notice.value = 'Lien de la fiche copié.'
	} catch {
		actionError.value = "Le navigateur a refusé la copie : copiez l'adresse de la page."
	}
}

// Versions : un inventaire annulé se refait en nouvelle version, avec sa feuille de comptage.
const router = useRouter()
async function nouvelleVersion(confirmed = false) {
	const current = inventaire.value
	if (!current) return
	if (!confirmed && !(await confirmAction({ title: 'Nouvelle version', message: `Une nouvelle version de ${current.name} sera créée en brouillon, avec les mêmes quantités comptées : vous la corrigerez puis la validerez.`, confirmLabel: 'Créer la nouvelle version' }))) return
	busy.value = true
	actionError.value = ''
	try {
		const result = await createPieceVersion('inventaires', current)
		emit('changed')
		await router.push({ name: 'InventaireFiche', params: { id: result.name } })
		notice.value = result.note || `Nouvelle version ${result.name} créée en brouillon.`
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}

const confirming = ref<'annuler' | 'annuler_version' | 'supprimer' | null>(null)
async function confirm() {
	const current = inventaire.value
	const action = confirming.value
	if (!current || !action) return
	if (action !== 'supprimer') {
		const cancelled = await perform(() => runInventaireAction(current, 'annuler'))
		if (cancelled) notice.value = 'Inventaire annulé : le stock revient comme avant.'
		confirming.value = null
		if (cancelled && action === 'annuler_version') await nouvelleVersion(true)
		return
	}
	busy.value = true
	try {
		await deleteInventaire(current)
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
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Cet inventaire n'existe pas ou n'existe plus.</div>
		<div v-else-if="!inventaire" class="card p-8 text-center text-ink-gray-6">Chargement de l'inventaire…</div>

		<template v-else>
			<RecordHeader>
				<template #title><span class="tabular-nums">{{ inventaire.name }}</span></template>
				<template #flags><StatusPill :status="inventaire.status" /></template>
				<template #sub>
					<span>{{ inventaire.depot || '—' }}</span>
					<span class="tabular-nums">{{ formatDay(inventaire.date) }}</span>
					<div><TagEditor doctype="Stock Reconciliation" :name="inventaire.name" :modified="inventaire.modified" :tags="inventaire.tags" :can-edit="true" @changed="(tags) => (inventaire!.tags = tags)" /></div>
				</template>
				<template #actions>
					<button v-if="can('nouvelle_version')" type="button" class="btn-primary" :disabled="busy" @click="nouvelleVersion()">Nouvelle version</button>
					<button v-if="counting && dirty" type="button" class="btn-secondary" :disabled="busy" @click="saveCounts">Enregistrer le comptage</button>
					<button v-if="can('valider')" type="button" class="btn-primary" :disabled="busy || !resume?.ecarts" :title="resume?.ecarts ? undefined : 'Aucun écart : il n\'y a rien à ajuster.'" @click="valider">Valider l'inventaire</button>
					<MoreMenu>
						<template v-if="inventaire.can_print">
							<a class="app-menu-item" role="menuitem" :href="inventairePrintUrl(inventaire.name)" target="_blank" rel="noopener noreferrer"><LucidePrinter class="h-3.5 w-3.5" aria-hidden="true" />Imprimer la feuille</a>
							<div class="app-menu-sep"></div>
						</template>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Stock Reconciliation', inventaire.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="can('annuler') || can('supprimer')">
							<div class="app-menu-sep"></div>
							<button v-if="can('annuler')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'annuler'">Annuler l'inventaire</button>
							<button v-if="can('supprimer')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'supprimer'">{{ inventaire.docstatus === 2 ? 'Supprimer la pièce annulée' : 'Supprimer le brouillon' }}</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations de l'inventaire">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucideWarehouse aria-hidden="true" />Dépôt</dt><dd><RouterLink v-if="inventaire.depot" class="ref-link" :to="{ name: 'Depot', params: { id: inventaire.depot } }">{{ inventaire.depot }}</RouterLink><template v-else>—</template></dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Date</dt><dd class="tabular-nums">{{ formatDay(inventaire.date) || '—' }}</dd></div>
							<div><dt><LucideUser aria-hidden="true" />Créé par</dt><dd>{{ inventaire.cree_par }}</dd></div>
						</dl>
					</div>
					<div v-if="resume" class="side-block">
						<dl class="record-facts">
							<div><dt>Lignes</dt><dd class="tabular-nums">{{ resume.lignes }}</dd></div>
							<div><dt>Lignes avec écart</dt><dd class="tabular-nums">{{ resume.ecarts }}</dd></div>
							<div><dt>Surplus</dt><dd class="tabular-nums" :class="resume.plus ? 'text-tone-green' : 'record-fact-none'">{{ signedQty(resume.plus) }}</dd></div>
							<div><dt>Manquants</dt><dd class="tabular-nums" :class="resume.moins ? 'text-tone-red' : 'record-fact-none'">{{ signedQty(resume.moins) }}</dd></div>
							<div><dt>Écart de valeur</dt><dd class="tabular-nums" :class="resume.valeur < 0 ? 'text-tone-red' : resume.valeur > 0 && 'text-tone-green'">{{ formatAmount(resume.valeur) }} DA</dd></div>
						</dl>
					</div>
				</aside>

				<div class="client-main">
					<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
					<div class="bureau-detail">
						<div class="bureau-center">
							<VersionsCard :versions="inventaire.versions" :docstatus="inventaire.docstatus" fiche="InventaireFiche" :can-amend="can('nouvelle_version')" />
							<div v-if="counting" role="status" class="rounded-control tone-blue px-3.5 py-2.5">
								Saisissez ce que vous comptez. Le théorique est le stock d'aujourd'hui ; rien ne bouge avant la validation, qui ajuste le stock et ne garde que les lignes avec écart.
							</div>

							<section class="card ref-card">
								<div class="ref-card-head">
									<h3>{{ counting ? 'Feuille de comptage' : 'Lignes ajustées' }}</h3>
									<span class="inline-flex items-center gap-2">
										<select v-search v-model="filter" class="field-input" aria-label="Lignes affichées">
											<option value="toutes">Toutes les lignes</option>
											<option value="ecarts">Seulement les écarts</option>
										</select>
										<button v-if="counting" type="button" class="btn-secondary" :disabled="busy" @click="adding = true"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Ajouter une ligne</button>
									</span>
								</div>
								<p v-if="!shown.length" class="text-ink-gray-6">{{ filter === 'ecarts' ? 'Aucun écart.' : 'Aucune ligne.' }}</p>
								<div v-else class="ref-scroll"><table class="ref-table livraison-prep">
									<thead><tr><th>Article</th><th>Lot</th><th class="end">Théorique</th><th class="end">Compté</th><th class="end">Écart</th><th class="end">Écart (DA)</th><th v-if="counting"></th></tr></thead>
									<tbody>
										<tr v-for="line in shown" :key="line.name">
											<td><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: line.article } }">{{ line.designation }}</RouterLink><span class="block text-xs tabular-nums text-ink-gray-6">{{ line.article }}</span></td>
											<td class="tabular-nums"><RouterLink v-if="line.lot" class="ref-link" :to="{ name: 'Lot', params: { id: line.lot } }">{{ line.lot }}</RouterLink><span v-else class="text-ink-gray-6">—</span></td>
											<td class="end tabular-nums">{{ formatQty(line.theorique) }} <span class="text-xs text-ink-gray-6">{{ line.unite }}</span></td>
											<td class="end">
												<input v-if="counting" v-model="counts[line.name]" class="field-input w-24 text-right tabular-nums" inputmode="decimal" :aria-label="`Quantité comptée, ${line.designation}${line.lot ? `, lot ${line.lot}` : ''}`" />
												<span v-else class="tabular-nums">{{ formatQty(line.compte) }}</span>
											</td>
											<td class="end tabular-nums font-semibold" :class="ecartOf(line) < 0 ? 'text-tone-red' : ecartOf(line) > 0 ? 'text-tone-green' : 'font-normal text-ink-gray-6'">{{ signedQty(ecartOf(line)) }}</td>
											<td class="end tabular-nums" :class="!ecartOf(line) && 'text-ink-gray-6'">{{ formatAmount(ecartOf(line) * line.taux) }}</td>
											<td v-if="counting"><button type="button" class="icon-btn" :disabled="busy" :aria-label="`Retirer ${line.designation} de la feuille`" @click="removeLine(line)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button></td>
										</tr>
									</tbody>
								</table></div>
							</section>
						</div>

						<aside class="record-activity" aria-label="Commentaires et activité de l'inventaire">
							<ActivityFeed ref="feed" :api="activityApi" :version="inventaire.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<FormDialog v-if="adding && inventaire" title="Ajouter une ligne au comptage" :dirty="Boolean(ajout.article)" :busy="busy" hint="Ctrl + Entrée pour ajouter" @close="adding = false" @submit="addLine">
			<div class="form-field">
				<label class="field-label" for="inventaire-article">Article <span class="req">obligatoire</span></label>
				<ChoicePicker :search="findArticles" :picked="ajout.label" input-id="inventaire-article" placeholder="Article ou code" @pick="pickArticle" @clear="ajout = { article: '', label: '', avec_lot: false, lot: '', quantite: ajout.quantite }" />
			</div>
			<div class="form-grid">
				<div v-if="ajout.avec_lot" class="form-field">
					<label class="field-label" for="inventaire-lot">Lot compté <span class="req">obligatoire</span></label>
					<input id="inventaire-lot" v-model="ajout.lot" class="field-input tabular-nums" placeholder="Nº de lot" autocomplete="off" />
				</div>
				<div class="form-field">
					<label class="field-label" for="inventaire-quantite">Quantité comptée <span class="req">obligatoire</span></label>
					<input id="inventaire-quantite" v-model="ajout.quantite" class="field-input text-right tabular-nums" inputmode="decimal" />
				</div>
			</div>
			<p v-if="ajoutError" class="field-error" role="alert">{{ ajoutError }}</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ actionError }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="addLine">Ajouter</button>
			</template>
		</FormDialog>

		<FormDialog v-if="confirming && inventaire" :title="confirming !== 'supprimer' ? 'Annuler l\'inventaire' : 'Supprimer le brouillon'" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour confirmer" @close="confirming = null" @submit="confirm">
			<p>{{ confirming !== 'supprimer' ? `L'inventaire ${inventaire.name} sera annulé : le stock revient comme avant l'ajustement.` : `La feuille de comptage ${inventaire.name} sera supprimée définitivement.` }}</p>
			<template #actions>
				<button v-if="confirming === 'annuler' && canCreate('Stock Reconciliation')" type="button" class="btn-secondary" :disabled="busy" @click="(confirming = 'annuler_version'), confirm()">Annuler et créer une nouvelle version</button>
				<button type="button" class="btn-primary" :disabled="busy" @click="confirm">{{ confirming !== 'supprimer' ? "Annuler l'inventaire" : 'Supprimer' }}</button>
			</template>
		</FormDialog>

		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
	</main>
</template>
