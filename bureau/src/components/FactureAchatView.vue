<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideBuilding2 from '~icons/lucide/building-2'
import LucideCalendar from '~icons/lucide/calendar'
import LucideCalendarClock from '~icons/lucide/calendar-clock'
import LucideHash from '~icons/lucide/hash'
import LucidePrinter from '~icons/lucide/printer'
import LucideReceipt from '~icons/lucide/receipt'
import LucideShoppingCart from '~icons/lucide/shopping-cart'
import LucidePackageCheck from '~icons/lucide/package-check'
import LucideUndo2 from '~icons/lucide/undo-2'
import LucideUser from '~icons/lucide/user'
import ActivityFeed from '@shared/components/ActivityFeed.vue'
import FormDialog from '@shared/components/FormDialog.vue'
import MoreMenu from '@shared/components/MoreMenu.vue'
import StatusPill from '@shared/components/StatusPill.vue'
import AppToast from './AppToast.vue'
import RecordHeader from './RecordHeader.vue'
import TagEditor from './TagEditor.vue'
import { createAvoirFournisseur, deleteFactureAchat, factureAchatActivity, factureAchatPrintUrl, getFactureAchatOptions, payerFactureAchat, runFactureAchatAction, updateFactureAchat } from '@/lib/api'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { dayFromToday, parseNumber } from '@/lib/devis'
import { deskUrl, formatDay } from '@/lib/display'
import { factureAchatStatus as factureStatus, factureAchatTone as factureTone, validatePaiementFournisseur as validateEncaissement, type FactureAchatValues, type PaiementFournisseurValues as EncaissementValues } from '@/lib/facturesAchat'
import { useFactureAchat } from '@/lib/useFactureAchat'

const props = defineProps<{ id: string }>()
const emit = defineEmits<{ changed: []; deleted: []; open: [name: string] }>()

const { facture, error, notFound, actionError, notice, noticeTone, busy, load, perform, refresh } = useFactureAchat(
	() => props.id,
	() => emit('changed'),
)
const feed = ref<InstanceType<typeof ActivityFeed> | null>(null)
const activityApi = computed(() => factureAchatActivity(props.id))
const userName = window.user_fullname || window.user || ''
function refreshAll(message = '') {
	if (draftDirty.value) return
	refresh(message)
	feed.value?.refresh()
}
defineExpose({ refresh: refreshAll, facture })

const can = (action: string) => Boolean(facture.value?.actions.includes(action as never))
const today = dayFromToday(0)
const late = computed(() => Boolean(facture.value && facture.value.reste > 0 && facture.value.echeance && facture.value.echeance < today && facture.value.docstatus === 1))
const paidPercent = computed(() => {
	const current = facture.value
	return current && current.total_ttc > 0 ? Math.min(100, Math.round((current.paye / current.total_ttc) * 100)) : 0
})

// Brouillon : n° et date du fournisseur, échéance, TVA et, pour un avoir, quantités rendues.
const numero = ref('')
const dateFournisseur = ref('')
const echeance = ref('')
const taxes = ref('')
const quantites = ref<Record<string, string>>({})
const taxOptions = ref<{ value: string; label: string }[]>([])
watch(
	() => facture.value?.modified,
	() => {
		const current = facture.value
		if (!current) return
		numero.value = current.numero_fournisseur ?? ''
		dateFournisseur.value = current.date_fournisseur ?? ''
		echeance.value = current.echeance ?? ''
		taxes.value = current.taxes_modele ?? ''
		quantites.value = Object.fromEntries(current.lignes.map((line) => [line.name, String(line.quantite)]))
	},
	{ immediate: true },
)
watch(
	() => can('modifier'),
	async (editable) => {
		if (!editable || taxOptions.value.length) return
		try {
			taxOptions.value = (await getFactureAchatOptions()).taxes
		} catch {
			// Sans la liste, la TVA reste celle de la facture.
		}
	},
	{ immediate: true },
)
const changedLines = computed(() => {
	const current = facture.value
	if (!current?.avoir) return []
	return current.lignes.filter((line) => (quantites.value[line.name] ?? '').trim() !== String(line.quantite)).map((line) => ({ name: line.name, quantite: parseNumber(quantites.value[line.name] ?? '') }))
})
const draftDirty = computed(() => {
	const current = facture.value
	if (!current || !can('modifier')) return false
	return numero.value.trim() !== (current.numero_fournisseur ?? '') || dateFournisseur.value !== (current.date_fournisseur ?? '') || echeance.value !== (current.echeance ?? '') || taxes.value !== (current.taxes_modele ?? '') || changedLines.value.length > 0
})
async function saveDraft() {
	const current = facture.value
	if (!current) return false
	if (changedLines.value.some((line) => !Number.isFinite(line.quantite))) {
		actionError.value = 'Une quantité est illisible.'
		return false
	}
	const values: FactureAchatValues = {}
	if (numero.value.trim() !== (current.numero_fournisseur ?? '')) values.numero_fournisseur = numero.value.trim()
	if (dateFournisseur.value !== (current.date_fournisseur ?? '')) values.date_fournisseur = dateFournisseur.value
	if (echeance.value !== (current.echeance ?? '')) values.echeance = echeance.value
	if (taxes.value !== (current.taxes_modele ?? '')) values.taxes = taxes.value
	if (changedLines.value.length) values.lignes = changedLines.value
	const done = await perform(() => updateFactureAchat(current, values))
	if (done) notice.value = current.avoir ? 'Avoir enregistré.' : 'Facture enregistrée.'
	return done
}
async function valider() {
	if (draftDirty.value && !(await saveDraft())) return
	const current = facture.value
	if (!current || current.blocked.length) return
	if (await perform(() => runFactureAchatAction(current, 'valider'))) notice.value = current.avoir ? 'Avoir validé.' : 'Facture validée.'
}

// Paiement au fournisseur : le reste à payer proposé, en espèces par défaut.
const paying = ref(false)
const paiement = ref<EncaissementValues>({ montant: '', mode: '', date: today, reference: '', date_reference: '' })
const paiementErrors = ref<Partial<Record<keyof EncaissementValues, string>>>({})
const modeType = computed(() => facture.value?.modes.find((item) => item.value === paiement.value.mode)?.type)
function openPaiement() {
	const current = facture.value
	if (!current) return
	paiement.value = { montant: String(current.reste), mode: current.modes.find((item) => item.type === 'Cash')?.value ?? '', date: today, reference: '', date_reference: '' }
	paiementErrors.value = {}
	paying.value = true
}
async function encaisser() {
	const current = facture.value
	if (!current) return
	paiementErrors.value = validateEncaissement(paiement.value, current.reste, modeType.value, today)
	if (Object.keys(paiementErrors.value).length) return
	const values = paiement.value
	let name = ''
	const done = await perform(async () => {
		const result = await payerFactureAchat(current, { montant: parseNumber(values.montant), mode: values.mode, date: values.date, reference: values.reference.trim() || undefined, date_reference: values.date_reference || undefined })
		name = result.paiement
		return result.facture
	})
	if (done) {
		paying.value = false
		notice.value = `Paiement ${name} enregistré.`
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

// Avoir fournisseur : un brouillon à toutes les quantités, qu'on réduit avant de le valider.
const createdAvoir = ref<string | null>(null)
async function avoir() {
	const current = facture.value
	if (!current) return
	let name = ''
	const done = await perform(async () => {
		const result = await createAvoirFournisseur(current)
		name = result.name
		if (result.note) notice.value = result.note
		return result.facture
	})
	if (done) createdAvoir.value = name
}

const confirming = ref<'annuler' | 'supprimer' | null>(null)
async function confirm() {
	const current = facture.value
	const action = confirming.value
	if (!current || !action) return
	if (action === 'annuler') {
		if (await perform(() => runFactureAchatAction(current, 'annuler'))) notice.value = current.avoir ? 'Avoir annulé.' : 'Facture annulée.'
		confirming.value = null
		return
	}
	busy.value = true
	try {
		await deleteFactureAchat(current)
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
		<div v-else-if="notFound" class="card p-8 text-center text-ink-gray-6">Cette facture n'existe pas ou n'existe plus.</div>
		<div v-else-if="!facture" class="card p-8 text-center text-ink-gray-6">Chargement de la facture…</div>

		<template v-else>
			<RecordHeader>
				<template #title><span class="tabular-nums">{{ facture.name }}</span></template>
				<template #flags>
					<StatusPill :status="factureStatus(facture.status)" :tone="factureTone(facture.status)" />
					<span v-if="facture.avoir" class="record-flag">Avoir</span>
				</template>
				<template #sub>
					<RouterLink class="ref-link" :to="{ name: 'Fournisseur', params: { id: facture.fournisseur } }">{{ facture.fournisseur_label }}</RouterLink>
					<span v-if="facture.numero_fournisseur" class="tabular-nums">nº {{ facture.numero_fournisseur }}</span>
					<span class="tabular-nums">{{ formatAmount(facture.total_ttc) }} DA TTC</span>
					<div><TagEditor doctype="Purchase Invoice" :name="facture.name" :modified="facture.modified" :tags="facture.tags" :can-edit="true" @changed="(tags) => (facture!.tags = tags)" /></div>
				</template>
				<template #actions>
					<button v-if="draftDirty" type="button" class="btn-secondary" :disabled="busy" @click="saveDraft">Enregistrer</button>
					<button v-if="can('valider')" type="button" class="btn-primary" :disabled="busy || (!draftDirty && facture.blocked.length > 0)" :title="facture.blocked.join(' ') || undefined" @click="valider">{{ facture.avoir ? "Valider l'avoir" : 'Valider la facture' }}</button>
					<button v-if="can('payer')" type="button" class="btn-primary" :disabled="busy" @click="openPaiement">Payer</button>
					<MoreMenu>
						<button v-if="can('avoir')" type="button" class="app-menu-item" role="menuitem" :disabled="busy" @click="avoir"><LucideUndo2 class="h-3.5 w-3.5" aria-hidden="true" />Avoir fournisseur</button>
						<div v-if="can('avoir')" class="app-menu-sep"></div>
						<template v-if="facture.can_print">
							<a class="app-menu-item" role="menuitem" :href="factureAchatPrintUrl(facture.name)" target="_blank" rel="noopener noreferrer"><LucidePrinter class="h-3.5 w-3.5" aria-hidden="true" />Imprimer</a>
							<div class="app-menu-sep"></div>
						</template>
						<button type="button" class="app-menu-item" role="menuitem" @click="copyLink">Copier le lien</button>
						<a class="app-menu-item" role="menuitem" :href="deskUrl('Purchase Invoice', facture.name)" target="_blank" rel="noopener noreferrer"><LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />Ouvrir sur le Desk</a>
						<template v-if="can('annuler') || can('supprimer')">
							<div class="app-menu-sep"></div>
							<button v-if="can('annuler')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'annuler'">{{ facture.avoir ? "Annuler l'avoir" : 'Annuler la facture' }}</button>
							<button v-if="can('supprimer')" type="button" class="app-menu-item text-tone-red" role="menuitem" @click="confirming = 'supprimer'">Supprimer le brouillon</button>
						</template>
					</MoreMenu>
				</template>
			</RecordHeader>

			<div class="client-dossier">
				<aside class="card client-side" aria-label="Informations de la facture d'achat">
					<div class="side-block">
						<dl class="record-facts">
							<div><dt><LucideBuilding2 aria-hidden="true" />Fournisseur</dt><dd><RouterLink class="ref-link" :to="{ name: 'Fournisseur', params: { id: facture.fournisseur } }">{{ facture.fournisseur_label }}</RouterLink></dd></div>
							<div v-if="!can('modifier')"><dt><LucideHash aria-hidden="true" />Facture du fournisseur</dt><dd class="tabular-nums" :class="!facture.numero_fournisseur && 'record-fact-none'">{{ facture.numero_fournisseur || 'Non renseignée' }}<template v-if="facture.date_fournisseur"> du {{ formatDay(facture.date_fournisseur) }}</template></dd></div>
							<div><dt><LucideCalendar aria-hidden="true" />Date</dt><dd class="tabular-nums">{{ formatDay(facture.date) || '—' }}</dd></div>
							<div v-if="!can('modifier')"><dt><LucideCalendarClock aria-hidden="true" />Échéance</dt><dd class="tabular-nums" :class="late && 'text-tone-red'">{{ formatDay(facture.echeance) || '—' }}<template v-if="late"> · en retard</template></dd></div>
							<div v-if="facture.avoir_de"><dt><LucideUndo2 aria-hidden="true" />Avoir sur</dt><dd><button type="button" class="ref-link tabular-nums" @click="emit('open', facture.avoir_de)">{{ facture.avoir_de }}</button></dd></div>
							<div v-if="facture.commandes.length"><dt><LucideShoppingCart aria-hidden="true" />Commande d'achat</dt><dd><template v-for="(name, index) in facture.commandes" :key="name">{{ index ? ', ' : '' }}<RouterLink class="ref-link tabular-nums" :to="{ name: 'CommandeAchatFiche', params: { id: name } }">{{ name }}</RouterLink></template></dd></div>
							<div v-if="facture.receptions.length"><dt><LucidePackageCheck aria-hidden="true" />Réception</dt><dd><template v-for="(name, index) in facture.receptions" :key="name">{{ index ? ', ' : '' }}<RouterLink class="ref-link tabular-nums" :to="{ name: 'ReceptionFiche', params: { id: name } }">{{ name }}</RouterLink></template></dd></div>
							<div><dt><LucideUser aria-hidden="true" />Créée par</dt><dd>{{ facture.cree_par }}</dd></div>
						</dl>
					</div>
					<div v-if="can('modifier')" class="side-block">
						<template v-if="!facture.avoir">
							<label class="field-label" for="facture-numero">Nº de la facture du fournisseur <span class="req">obligatoire</span></label>
							<input id="facture-numero" v-model="numero" class="field-input tabular-nums" placeholder="Tel qu'imprimé sur la facture reçue" autocomplete="off" :aria-invalid="!numero.trim()" />
							<label class="field-label mt-1" for="facture-date-fournisseur">Date de la facture du fournisseur</label>
							<input id="facture-date-fournisseur" v-model="dateFournisseur" class="field-input tabular-nums" type="date" :max="today" />
						</template>
						<label class="field-label mt-1" for="facture-echeance">Échéance</label>
						<input id="facture-echeance" v-model="echeance" class="field-input tabular-nums" type="date" :min="facture.date ?? undefined" />
						<label class="field-label mt-1" for="facture-taxes">TVA déductible</label>
						<select id="facture-taxes" v-model="taxes" class="field-input">
							<option value="">Sans TVA</option>
							<option v-if="taxes && !taxOptions.some((item) => item.value === taxes)" :value="taxes">{{ taxes }}</option>
							<option v-for="item in taxOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
						</select>
					</div>
					<div v-if="facture.docstatus === 1 && !facture.avoir" class="side-block">
						<div class="commande-progress"><span>Payé</span><strong class="tabular-nums">{{ paidPercent }} %</strong></div>
						<div class="commande-bar" role="progressbar" :aria-valuenow="paidPercent" aria-valuemin="0" aria-valuemax="100" aria-label="Part payée"><span :style="{ width: `${paidPercent}%` }"></span></div>
						<dl class="record-facts mt-1">
							<div><dt><LucideReceipt aria-hidden="true" />Reste à payer</dt><dd class="tabular-nums" :class="facture.reste > 0 ? 'text-tone-red' : 'record-fact-none'">{{ formatAmount(facture.reste) }} DA</dd></div>
						</dl>
					</div>
				</aside>

				<div class="client-main">
					<p v-if="actionError" role="alert" class="flex-none rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
					<div class="bureau-detail">
						<div class="bureau-center">
							<div v-if="can('valider') && facture.blocked.length && !draftDirty" role="status" class="rounded-control tone-amber px-3.5 py-2.5"><strong class="font-semibold">Pas encore validable :</strong> {{ facture.blocked.join(' ') }}</div>
							<div v-if="late" role="status" class="rounded-control tone-red px-3.5 py-2.5">
								<strong class="font-semibold">Échéance dépassée</strong> depuis le {{ formatDay(facture.echeance) }} : {{ formatAmount(facture.reste) }} DA restent à payer.
								<button v-if="can('payer')" type="button" class="font-medium underline" @click="openPaiement">Payer</button>
							</div>
							<div v-if="facture.avoir && facture.docstatus === 0" role="status" class="rounded-control tone-blue px-3.5 py-2.5">
								Saisissez en négatif les quantités créditées par le fournisseur (−1 pour une unité) ; 0 retire la ligne. L'avoir réduit le reste à payer de {{ facture.avoir_de }} tant qu'elle n'est pas soldée, sinon le fournisseur nous doit ce montant.
							</div>

							<section class="card ref-card">
								<h3>Lignes</h3>
								<div class="ref-scroll"><table class="ref-table">
									<thead><tr><th>Article</th><th class="end">Quantité</th><th class="end">Prix HT (DA)</th><th class="end">Montant HT (DA)</th></tr></thead>
									<tbody>
										<tr v-for="(line, index) in facture.lignes" :key="line.name">
											<td><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: line.article } }">{{ line.designation }}</RouterLink><span class="ml-1 text-xs tabular-nums text-ink-gray-6">{{ line.article }}</span></td>
											<td class="end tabular-nums">
												<span v-if="facture.avoir && can('modifier')" class="inline-flex items-center gap-1"><input v-model="quantites[line.name]" class="field-input w-20 text-right tabular-nums" inputmode="decimal" :aria-label="`Quantité créditée, ligne ${index + 1}`" /><span class="text-xs text-ink-gray-6">{{ line.unite }}</span></span>
												<template v-else>{{ formatQty(line.quantite) }} {{ line.unite }}</template>
											</td>
											<td class="end tabular-nums">{{ formatAmount(line.prix) }}</td>
											<td class="end tabular-nums">{{ formatAmount(line.montant) }}</td>
										</tr>
									</tbody>
								</table></div>
								<dl class="devis-totaux">
									<div><dt>Total HT</dt><dd class="tabular-nums">{{ formatAmount(facture.total) }} DA</dd></div>
									<div v-for="tax in facture.taxes" :key="tax.description"><dt>{{ tax.description }}</dt><dd class="tabular-nums">{{ formatAmount(tax.montant) }} DA</dd></div>
									<div class="devis-total-ttc"><dt>Total TTC</dt><dd class="tabular-nums">{{ formatAmount(facture.total_ttc) }} DA</dd></div>
								</dl>
								<p v-if="facture.en_lettres" class="text-sm text-ink-gray-6">{{ facture.en_lettres }}</p>
							</section>

							<div v-if="facture.docstatus === 1 && !facture.avoir" class="client-cards">
								<section v-if="facture.paiements" class="card ref-card">
									<div class="ref-card-head"><h3>Paiements</h3><button v-if="can('payer')" type="button" class="ref-link" @click="openPaiement">Payer</button></div>
									<p v-if="!facture.paiements.length" class="text-ink-gray-6">Aucun paiement.</p>
									<div v-else class="ref-scroll"><table class="ref-table">
										<thead><tr><th>Paiement</th><th>Date</th><th>Mode</th><th class="end">Montant (DA)</th></tr></thead>
										<tbody><tr v-for="row in facture.paiements" :key="row.name"><td><RouterLink class="ref-link" :to="{ name: 'PaiementFiche', params: { id: row.name } }">{{ row.name }}</RouterLink><span v-if="row.brouillon" class="ml-1 text-xs text-tone-amber">brouillon</span></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td>{{ row.mode || '—' }}<span v-if="row.reference" class="block text-xs text-ink-gray-6">{{ row.reference }}</span></td><td class="end tabular-nums">{{ formatAmount(row.montant) }}</td></tr></tbody>
									</table></div>
								</section>
								<section class="card ref-card">
									<h3>Avoirs fournisseur</h3>
									<p v-if="!facture.avoirs.length" class="text-ink-gray-6">Aucun avoir.</p>
									<div v-else class="ref-scroll"><table class="ref-table">
										<thead><tr><th>Avoir</th><th>Date</th><th>Statut</th><th class="end">Total (DA)</th></tr></thead>
										<tbody><tr v-for="row in facture.avoirs" :key="row.name"><td><button type="button" class="ref-link tabular-nums" @click="emit('open', row.name)">{{ row.name }}</button></td><td class="tabular-nums">{{ formatDay(row.date) }}</td><td><StatusPill :status="factureStatus(row.status)" :tone="factureTone(row.status)" /></td><td class="end tabular-nums">{{ formatAmount(row.total) }}</td></tr></tbody>
									</table></div>
								</section>
							</div>
						</div>

						<aside class="record-activity" aria-label="Commentaires et activité de la facture d'achat">
							<ActivityFeed ref="feed" :api="activityApi" :version="facture.modified" :user-name="userName" @changed="refresh()" />
						</aside>
					</div>
				</div>
			</div>
		</template>

		<FormDialog v-if="paying && facture" title="Payer la facture" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour payer" @close="paying = false" @submit="encaisser">
			<p class="text-sm">Reste à payer : <strong class="tabular-nums">{{ formatAmount(facture.reste) }} DA</strong>. Un paiement partiel laisse le reste sur la facture.</p>
			<div class="form-grid">
				<div class="form-field">
					<label class="field-label" for="paiement-montant">Montant (DA) <span class="req">obligatoire</span></label>
					<input id="paiement-montant" v-model="paiement.montant" class="field-input text-right tabular-nums" inputmode="decimal" :aria-invalid="Boolean(paiementErrors.montant)" />
					<p v-if="paiementErrors.montant" class="field-error" role="alert">{{ paiementErrors.montant }}</p>
				</div>
				<div class="form-field">
					<label class="field-label" for="paiement-mode">Mode <span class="req">obligatoire</span></label>
					<select id="paiement-mode" v-model="paiement.mode" class="field-input" :aria-invalid="Boolean(paiementErrors.mode)">
						<option value="">Choisir…</option>
						<option v-for="item in facture.modes" :key="item.value" :value="item.value">{{ item.value }}</option>
					</select>
					<p v-if="paiementErrors.mode" class="field-error" role="alert">{{ paiementErrors.mode }}</p>
				</div>
				<div class="form-field">
					<label class="field-label" for="paiement-date">Date du paiement</label>
					<input id="paiement-date" v-model="paiement.date" class="field-input tabular-nums" type="date" :max="today" :aria-invalid="Boolean(paiementErrors.date)" />
					<p v-if="paiementErrors.date" class="field-error" role="alert">{{ paiementErrors.date }}</p>
				</div>
				<template v-if="modeType === 'Bank'">
					<div class="form-field">
						<label class="field-label" for="paiement-reference">Référence <span class="req">obligatoire</span></label>
						<input id="paiement-reference" v-model="paiement.reference" class="field-input" placeholder="Nº de chèque, de virement…" autocomplete="off" :aria-invalid="Boolean(paiementErrors.reference)" />
						<p v-if="paiementErrors.reference" class="field-error" role="alert">{{ paiementErrors.reference }}</p>
					</div>
					<div class="form-field">
						<label class="field-label" for="paiement-date-ref">Date du chèque ou du virement</label>
						<input id="paiement-date-ref" v-model="paiement.date_reference" class="field-input tabular-nums" type="date" />
					</div>
				</template>
			</div>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="encaisser">{{ busy ? 'Paiement…' : 'Payer' }}</button>
			</template>
		</FormDialog>

		<FormDialog v-if="confirming && facture" :title="confirming === 'annuler' ? (facture.avoir ? 'Annuler l\'avoir' : 'Annuler la facture') : 'Supprimer le brouillon'" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour confirmer" @close="confirming = null" @submit="confirm">
			<p>{{ confirming === 'annuler' ? `${facture.name} sera annulée : l'écriture comptable est contrepassée. ERPNext refuse si un paiement ou un avoir validé en dépend.` : `Le brouillon ${facture.name} sera supprimé ; ses quantités redeviennent à facturer.` }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="confirm">{{ confirming === 'annuler' ? 'Annuler' : 'Supprimer' }}</button>
			</template>
		</FormDialog>

		<AppToast :message="notice" :tone="noticeTone" @close="notice = ''" />
		<AppToast :message="createdAvoir ? `Avoir fournisseur ${createdAvoir} créé : ajustez les quantités puis validez-le.` : ''" :duration="0" @close="createdAvoir = null">
			<button v-if="createdAvoir" type="button" class="app-toast-action" @click="(emit('open', createdAvoir), (createdAvoir = null))">Ouvrir l'avoir</button>
		</AppToast>
	</main>
</template>
