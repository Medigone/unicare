<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import LucideCircleAlert from '~icons/lucide/circle-alert'
import LucideCircleCheck from '~icons/lucide/circle-check'
import LucidePlus from '~icons/lucide/plus'
import LucideTriangleAlert from '~icons/lucide/triangle-alert'
import FormDialog from '@shared/components/FormDialog.vue'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import { createExercice, createTva, getCompta, saveComptes, saveMode, setTva } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'
import { ETAT_LABELS, formatDate, formatTaux, libelleCompte, MODE_TYPES, TVA_SENS, type ModePaiement, type ModeType, type ReglagesCompta, type TauxTva, type TvaSens } from '@/lib/compta'

/**
 * Réglages › Comptabilité et trésorerie : un bilan de la configuration en tête, puis les comptes par défaut de la
 * société, les taux de TVA, les modes de paiement, les exercices et le droit de timbre. Chaque partie est modifiable
 * selon les droits ERPNext du rôle ; sinon elle s'affiche en lecture seule.
 */
const compta = ref<ReglagesCompta | null>(null)
const error = ref('')
const actionError = ref('')
const notice = ref('')
const busy = ref(false)

async function load() {
	try {
		apply(await getCompta())
		error.value = ''
	} catch (e) {
		if (!compta.value) error.value = (e as Error).message
	}
}

// Comptes par défaut : copie de travail, enregistrée d'un bloc.
const comptes = ref<Record<string, string>>({})
const comptesBase = ref('{}')
const comptesDirty = computed(() => JSON.stringify(comptes.value) !== comptesBase.value)

function apply(fresh: ReglagesCompta) {
	compta.value = fresh
	if (!comptesDirty.value) {
		comptes.value = Object.fromEntries(fresh.comptes.groupes.flatMap((groupe) => groupe.champs.map((champ) => [champ.field, champ.valeur ?? ''])))
		comptesBase.value = JSON.stringify(comptes.value)
	}
}

async function run(action: () => Promise<ReglagesCompta>, message: string, after?: () => void) {
	if (busy.value) return false
	busy.value = true
	actionError.value = ''
	try {
		const fresh = await action()
		after?.()
		apply(fresh)
		notice.value = message
		return true
	} catch (e) {
		actionError.value = (e as Error).message
		await load()
		return false
	} finally {
		busy.value = false
	}
}

const aRegler = computed(() => compta.value?.bilan.filter((point) => point.etat !== 'ok').length ?? 0)

async function enregistrerComptes() {
	const modified = compta.value?.societe.modified ?? ''
	await run(() => saveComptes(modified, comptes.value), 'Comptes par défaut enregistrés.', () => (comptesBase.value = JSON.stringify(comptes.value)))
}

// TVA.
async function actionTva(sens: TvaSens, taux: TauxTva, action: 'defaut' | 'activer' | 'desactiver') {
	const messages = { defaut: `${taux.titre} est maintenant le taux par défaut.`, activer: `${taux.titre} est de nouveau proposé.`, desactiver: `${taux.titre} n'est plus proposé.` }
	await run(() => setTva(sens, taux, action), messages[action])
}
const nouveauTaux = ref<{ sens: TvaSens; taux: string } | null>(null)
async function creerTaux() {
	const form = nouveauTaux.value
	if (!form) return
	if (!form.taux.trim()) {
		actionError.value = 'Indiquez le taux.'
		return
	}
	if (await run(() => createTva(form.sens, form.taux), 'Taux créé.')) nouveauTaux.value = null
}

// Modes de paiement : chaque changement est enregistré tout de suite.
async function changerMode(mode: ModePaiement, changes: Partial<{ type: ModeType; compte: string; actif: boolean }>) {
	const values = { type: mode.type, compte: mode.compte ?? '', actif: mode.actif, ...changes }
	await run(() => saveMode(mode, values), `Mode « ${mode.name} » enregistré.`)
}
const nouveauMode = ref<{ nom: string; type: ModeType; compte: string } | null>(null)
async function creerMode() {
	const form = nouveauMode.value
	if (!form) return
	if (!form.nom.trim()) {
		actionError.value = 'Donnez un nom au mode de paiement.'
		return
	}
	if (await run(() => saveMode(null, { ...form, actif: true }), 'Mode de paiement créé.')) nouveauMode.value = null
}

// Exercices.
async function creerExercice() {
	const suivant = compta.value?.exercice_suivant
	if (!suivant) return
	const ok = await confirmAction({
		title: `Créer l'exercice ${suivant.name}`,
		message: `Du ${formatDate(suivant.debut)} au ${formatDate(suivant.fin)}. Les pièces datées de cette période pourront être validées.`,
		confirmLabel: 'Créer',
	})
	if (ok) await run(createExercice, `Exercice ${suivant.name} créé.`)
}

function tranche(index: number) {
	const tranches = compta.value?.timbre.tranches ?? []
	const haut = tranches[index]?.jusqu_a
	const bas = index ? tranches[index - 1]?.jusqu_a : null
	const da = (n: number) => `${n.toLocaleString('fr-FR')} DA`
	if (haut === null || haut === undefined) return bas ? `Au-delà de ${da(bas)}` : 'Tout montant'
	return bas ? `De ${da(bas)} à ${da(haut)}` : `Jusqu'à ${da(haut)}`
}

function allerA(ancre: string) {
	const section = document.getElementById(ancre)
	section?.scrollIntoView({ behavior: 'smooth', block: 'start' })
	section?.querySelector<HTMLElement>('select, input, button')?.focus({ preventScroll: true })
}

onMounted(load)
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Réglages' }, { label: 'Comptabilité et trésorerie' }]" active="compta">
		<div class="bureau-work tdb">
			<div>
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Comptabilité et trésorerie</h1>
				<p class="text-sm text-ink-gray-6">Réglages de la société {{ compta?.societe.name }}. Chaque partie est modifiable selon les droits de votre rôle.</p>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!compta" class="card p-4 text-ink-gray-6">Chargement des réglages…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<template v-if="compta">
				<section class="card reglages-card" aria-labelledby="t-bilan">
					<div>
						<h2 id="t-bilan" class="text-base font-semibold">Bilan de la configuration</h2>
						<p class="text-sm text-ink-gray-6">{{ aRegler ? `${aRegler} point${aRegler > 1 ? 's' : ''} à regarder.` : 'Tout est en place.' }}</p>
					</div>
					<ul class="compta-bilan">
						<li v-for="point in compta.bilan" :key="point.code" :class="`compta-bilan-${point.etat}`">
							<LucideCircleCheck v-if="point.etat === 'ok'" class="compta-bilan-icon" aria-hidden="true" />
							<LucideTriangleAlert v-else-if="point.etat === 'attention'" class="compta-bilan-icon" aria-hidden="true" />
							<LucideCircleAlert v-else class="compta-bilan-icon" aria-hidden="true" />
							<div class="min-w-0 flex-auto">
								<p class="font-semibold">{{ point.label }} <span class="sr-only">: {{ ETAT_LABELS[point.etat] }}</span></p>
								<p class="text-sm text-ink-gray-7">{{ point.detail }}</p>
							</div>
							<template v-if="point.etat !== 'ok'">
								<RouterLink v-if="point.ancre === 'tarifs'" :to="{ name: 'Tarifs' }" class="btn-ghost shrink-0">Régler</RouterLink>
								<button v-else type="button" class="btn-ghost shrink-0" @click="allerA(point.ancre)">Régler</button>
							</template>
						</li>
					</ul>
				</section>

				<div class="reglages-grid">
					<section id="comptes" class="card reglages-card compta-large" aria-labelledby="t-comptes">
						<div>
							<h2 id="t-comptes" class="text-base font-semibold">Comptes par défaut</h2>
							<p class="text-sm text-ink-gray-6">Les comptes que les pièces reprennent quand l'article, le client ou le fournisseur n'en précise pas.</p>
						</div>
						<div v-for="groupe in compta.comptes.groupes" :key="groupe.titre">
							<h3 class="compta-groupe">{{ groupe.titre }}</h3>
							<div class="form-grid">
								<div v-for="champ in groupe.champs" :key="champ.field" class="form-field">
									<label class="field-label" :for="`compte-${champ.field}`">{{ champ.label }} <span v-if="champ.requis" class="req">obligatoire</span></label>
									<select v-search :id="`compte-${champ.field}`" v-model="comptes[champ.field]" class="field-input" :disabled="!compta.droits.comptes">
										<option v-if="!champ.requis || !comptes[champ.field]" value="">—</option>
										<option v-for="compte in compta.comptes.options[champ.field]" :key="compte" :value="compte">{{ libelleCompte(compte) }}</option>
									</select>
									<p v-if="champ.aide" class="field-note">{{ champ.aide }}</p>
								</div>
							</div>
						</div>
						<div v-if="compta.droits.comptes" class="flex justify-end"><button type="button" class="btn-primary" :disabled="busy || !comptesDirty" @click="enregistrerComptes">Enregistrer</button></div>
					</section>

					<section id="tva" class="card reglages-card" aria-labelledby="t-tva">
						<div class="flex items-center gap-2">
							<h2 id="t-tva" class="flex-auto text-base font-semibold">TVA</h2>
							<button v-if="compta.droits.tva_creer.vente || compta.droits.tva_creer.achat" type="button" class="btn-secondary" :disabled="busy" @click="nouveauTaux = { sens: compta.droits.tva_creer.vente ? 'vente' : 'achat', taux: '' }"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Nouveau taux</button>
						</div>
						<div v-for="sens in TVA_SENS" :key="sens.key">
							<h3 class="compta-groupe">{{ sens.label }}</h3>
							<p class="text-sm text-ink-gray-6">{{ sens.help }} Le taux par défaut est repris par les nouvelles pièces ; on peut le changer pièce par pièce.</p>
							<table class="ref-table compta-table">
								<thead>
									<tr><th>Taux</th><th>Libellé</th><th class="sr-only">État</th><th><span class="sr-only">Actions</span></th></tr>
								</thead>
								<tbody>
									<tr v-for="taux in compta.tva[sens.key]" :key="taux.name" :class="!taux.actif && 'text-ink-gray-5'">
										<td class="tabular-nums">{{ formatTaux(taux.taux) }}</td>
										<td>{{ taux.titre }}<span v-if="taux.compte" class="block text-xs text-ink-gray-6">{{ libelleCompte(taux.compte) }}</span></td>
										<td><span v-if="taux.defaut" class="badge tone-green">par défaut</span><span v-else-if="!taux.actif" class="text-xs">désactivé</span></td>
										<td class="text-right">
											<template v-if="compta.droits.tva[sens.key]">
												<button v-if="taux.actif && !taux.defaut" type="button" class="btn-ghost" :disabled="busy" @click="actionTva(sens.key, taux, 'defaut')">Par défaut</button>
												<button v-if="taux.actif && !taux.defaut" type="button" class="btn-ghost" :disabled="busy" @click="actionTva(sens.key, taux, 'desactiver')">Désactiver</button>
												<button v-if="!taux.actif" type="button" class="btn-ghost" :disabled="busy" @click="actionTva(sens.key, taux, 'activer')">Réactiver</button>
											</template>
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</section>

					<section id="modes" class="card reglages-card" aria-labelledby="t-modes">
						<div class="flex items-center gap-2">
							<h2 id="t-modes" class="flex-auto text-base font-semibold">Modes de paiement</h2>
							<button v-if="compta.droits.modes_creer" type="button" class="btn-secondary" :disabled="busy" @click="nouveauMode = { nom: '', type: 'Bank', compte: '' }"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Nouveau mode</button>
						</div>
						<p class="text-sm text-ink-gray-6">Le compte où arrive l'argent encaissé, ou d'où part l'argent payé. Sans compte propre, c'est la banque ou la caisse par défaut. Chaque changement est enregistré aussitôt.</p>
						<table class="ref-table compta-table">
							<thead>
								<tr><th>Mode</th><th>Compte</th><th>Proposé</th></tr>
							</thead>
							<tbody>
								<tr v-for="mode in compta.modes" :key="mode.name" :class="!mode.actif && 'text-ink-gray-5'">
									<td>{{ mode.name }}<span class="block text-xs text-ink-gray-6">{{ MODE_TYPES.find((t) => t.value === mode.type)?.label }}</span></td>
									<td>
										<select v-search class="field-input" :value="mode.compte ?? ''" :disabled="!compta.droits.modes || busy" :aria-label="`Compte du mode ${mode.name}`" @change="changerMode(mode, { compte: ($event.target as HTMLSelectElement).value })">
											<option value="">{{ mode.repli ? `Par défaut : ${libelleCompte(mode.repli)}` : '— aucun —' }}</option>
											<option v-for="compte in compta.comptes_tresorerie" :key="compte" :value="compte">{{ libelleCompte(compte) }}</option>
										</select>
									</td>
									<td><input type="checkbox" :checked="mode.actif" :disabled="!compta.droits.modes || busy" :aria-label="`Proposer le mode ${mode.name}`" @change="changerMode(mode, { actif: ($event.target as HTMLInputElement).checked })" /></td>
								</tr>
							</tbody>
						</table>
					</section>

					<section id="exercices" class="card reglages-card" aria-labelledby="t-exercices">
						<div>
							<h2 id="t-exercices" class="text-base font-semibold">Exercices comptables</h2>
							<p class="text-sm text-ink-gray-6">Une pièce ne peut être validée que si sa date tombe dans un exercice. Créez le suivant avant la fin de l'année.</p>
						</div>
						<ul class="reglages-lines">
							<li v-for="exercice in compta.exercices" :key="exercice.name" class="reglages-line">
								<span class="flex-auto font-semibold">{{ exercice.name }}</span>
								<span class="text-sm tabular-nums">{{ formatDate(exercice.debut) }} → {{ formatDate(exercice.fin) }}</span>
								<span v-if="exercice.en_cours" class="badge tone-green">en cours</span>
							</li>
						</ul>
						<div v-if="compta.droits.exercices" class="flex justify-end">
							<button type="button" class="btn-secondary" :disabled="busy" @click="creerExercice"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Créer l'exercice {{ compta.exercice_suivant.name }}</button>
						</div>
					</section>

					<section id="timbre" class="card reglages-card" aria-labelledby="t-timbre">
						<div>
							<h2 id="t-timbre" class="text-base font-semibold">Droit de timbre</h2>
							<p class="text-sm text-ink-gray-6">Ajouté aux factures de vente payées en espèces, sur le montant TTC, au centime.</p>
						</div>
						<table class="ref-table compta-table">
							<thead>
								<tr><th>Montant TTC</th><th class="text-right">Taux</th></tr>
							</thead>
							<tbody>
								<tr v-for="(row, index) in compta.timbre.tranches" :key="index">
									<td>{{ tranche(index) }}</td>
									<td class="text-right tabular-nums">{{ formatTaux(row.taux) }}</td>
								</tr>
							</tbody>
						</table>
						<p class="text-sm">Minimum : {{ compta.timbre.minimum }} DA · Compte : {{ compta.timbre.compte_nom ? libelleCompte(compta.timbre.compte_nom) : `${compta.timbre.compte} (absent du plan)` }}</p>
						<p class="field-note">Barème de la loi de finances, livré avec l'application. Faites-le confirmer par votre comptable ; s'il change, demandez la mise à jour de l'application.</p>
					</section>
				</div>
			</template>
		</div>

		<FormDialog v-if="nouveauTaux" title="Nouveau taux de TVA" :dirty="Boolean(nouveauTaux.taux.trim())" :busy="busy" @close="nouveauTaux = null" @submit="creerTaux">
			<div class="form-grid">
				<fieldset class="form-field">
					<legend class="field-label">Pour</legend>
					<div class="flex gap-4 text-sm">
						<label v-if="compta?.droits.tva_creer.vente" class="flex items-center gap-1.5"><input v-model="nouveauTaux.sens" type="radio" value="vente" /> les ventes</label>
						<label v-if="compta?.droits.tva_creer.achat" class="flex items-center gap-1.5"><input v-model="nouveauTaux.sens" type="radio" value="achat" /> les achats</label>
					</div>
				</fieldset>
				<div class="form-field">
					<label class="field-label" for="tva-taux">Taux en % <span class="req">obligatoire</span></label>
					<input id="tva-taux" v-model="nouveauTaux.taux" class="field-input w-28 text-right tabular-nums" inputmode="decimal" placeholder="19" autocomplete="off" />
					<p class="field-note">Compté sur le compte de TVA {{ nouveauTaux.sens === 'vente' ? 'collectée (44571)' : 'déductible (44566)' }}. Il n'est pas mis par défaut.</p>
				</div>
			</div>
		</FormDialog>

		<FormDialog v-if="nouveauMode" title="Nouveau mode de paiement" :dirty="Boolean(nouveauMode.nom.trim())" :busy="busy" @close="nouveauMode = null" @submit="creerMode">
			<div class="form-grid">
				<div class="form-field">
					<label class="field-label" for="mode-nom">Nom <span class="req">obligatoire</span></label>
					<input id="mode-nom" v-model="nouveauMode.nom" class="field-input" placeholder="Ex. Versement CCP" autocomplete="off" />
				</div>
				<fieldset class="form-field">
					<legend class="field-label">Type</legend>
					<div class="flex gap-4 text-sm">
						<label v-for="type in MODE_TYPES" :key="type.value" class="flex items-center gap-1.5"><input v-model="nouveauMode.type" type="radio" :value="type.value" /> {{ type.label }}</label>
					</div>
					<p class="field-note">Banque : la référence (n° de chèque, de virement…) est demandée à chaque paiement.</p>
				</fieldset>
				<div class="form-field">
					<label class="field-label" for="mode-compte">Compte</label>
					<select v-search id="mode-compte" v-model="nouveauMode.compte" class="field-input">
						<option value="">Par défaut (banque ou caisse de la société)</option>
						<option v-for="compte in compta?.comptes_tresorerie" :key="compte" :value="compte">{{ libelleCompte(compte) }}</option>
					</select>
				</div>
			</div>
		</FormDialog>
		<AppToast :message="notice" tone="success" @close="notice = ''" />
	</BureauShell>
</template>
