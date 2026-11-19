<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import LucideCircleAlert from '~icons/lucide/circle-alert'
import LucideCircleCheck from '~icons/lucide/circle-check'
import LucideLock from '~icons/lucide/lock'
import LucidePlus from '~icons/lucide/plus'
import LucideTrash2 from '~icons/lucide/trash-2'
import LucideTriangleAlert from '~icons/lucide/triangle-alert'
import FormDialog from '@shared/components/FormDialog.vue'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import { createExercice, createTva, deleteMode, getCompta, saveComptes, saveMode, setTva } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'
import { ETAT_LABELS, formatDate, formatTaux, libelleCompte, MODE_TYPES, pireEtat, SECTIONS, TVA_SENS, type BilanEtat, type ComptaSection, type ModePaiement, type ModeType, type ReglagesCompta, type TauxTva, type TvaSens } from '@/lib/compta'

/**
 * Réglages › Comptabilité et trésorerie : à gauche, une section par partie (vue d'ensemble, comptes par défaut, TVA,
 * modes de paiement, exercices, droit de timbre), chacune avec la couleur de son point du bilan ; à droite, la
 * section ouverte. Chaque partie est modifiable selon les droits ERP du rôle ; sinon elle s'affiche en lecture seule.
 */
const section = ref<ComptaSection>('bilan')
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
const pointsARegler = computed(() => (compta.value?.bilan ?? []).filter((point) => point.etat !== 'ok').sort((a, b) => (a.etat === 'manque' ? 0 : 1) - (b.etat === 'manque' ? 0 : 1)))
const pointsOk = computed(() => (compta.value?.bilan ?? []).filter((point) => point.etat === 'ok'))
const pointExercice = computed(() => compta.value?.bilan.find((point) => point.code === 'exercice'))

/** La colonne de gauche : chaque section, sa couleur (le pire de ses points) et une phrase courte. */
const navSections = computed(() => {
	const c = compta.value
	if (!c) return []
	const etatDe = (codes: string[]): BilanEtat => pireEtat(c.bilan.filter((point) => codes.includes(point.code)).map((point) => point.etat))
	const enCours = c.exercices.find((row) => row.en_cours)
	const resumes: Record<ComptaSection, string> = {
		bilan: aRegler.value ? `${aRegler.value} point${aRegler.value > 1 ? 's' : ''} à regarder` : 'Tout est en place',
		comptes: etatDe(['comptes']) === 'ok' ? `${c.comptes.groupes.flatMap((g) => g.champs).filter((champ) => champ.valeur).length} comptes posés` : 'Comptes à renseigner',
		tva: (() => {
			const defaut = c.tva.vente.find((row) => row.defaut && row.actif)
			return defaut ? `Ventes : ${defaut.titre}` : 'Sans taux par défaut'
		})(),
		modes: etatDe(['modes']) === 'manque' ? 'Un mode sans compte' : etatDe(['modes']) === 'attention' ? 'Modes sans compte propre' : `${c.modes.filter((m) => m.actif).length} modes proposés`,
		exercices: enCours ? (etatDe(['exercice']) === 'attention' ? `${enCours.name} finit le ${formatDate(enCours.fin)}` : `${enCours.name} en cours`) : 'Aucun exercice en cours',
		timbre: etatDe(['timbre']) === 'ok' ? `Minimum ${c.timbre.minimum} DA` : 'Compte absent',
	}
	return SECTIONS.map((item) => ({ ...item, etat: item.key === 'bilan' ? pireEtat(c.bilan.map((p) => p.etat)) : etatDe(item.points), resume: resumes[item.key] }))
})

const comptesModifies = computed(() => {
	const base = JSON.parse(comptesBase.value) as Record<string, string>
	return Object.keys(comptes.value).filter((field) => comptes.value[field] !== base[field]).length
})
function annulerComptes() {
	comptes.value = JSON.parse(comptesBase.value)
}
function compteModifie(field: string) {
	return comptes.value[field] !== (JSON.parse(comptesBase.value) as Record<string, string>)[field]
}

async function enregistrerComptes() {
	const modified = compta.value?.societe.modified ?? ''
	await run(() => saveComptes(modified, comptes.value), 'Comptes par défaut enregistrés.', () => (comptesBase.value = JSON.stringify(comptes.value)))
}

// TVA : un sens à la fois.
const tvaSens = ref<TvaSens>('vente')
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
async function supprimerMode(mode: ModePaiement) {
	if (!(await confirmAction({ title: 'Supprimer le mode de paiement', message: `« ${mode.name} » sera supprimé. Il n'a jamais servi à un paiement.`, confirmLabel: 'Supprimer', danger: true }))) return
	await run(() => deleteMode(mode), `Mode « ${mode.name} » supprimé.`)
}
const modesBloques = computed(() => (compta.value?.modes ?? []).filter((mode) => mode.actif && !mode.compte && !mode.repli))
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
	if (SECTIONS.some((item) => item.key === ancre)) section.value = ancre as ComptaSection
}

onMounted(load)
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Réglages' }, { label: 'Comptabilité et trésorerie' }]" active="compta">
		<div class="bureau-work tdb">
			<div>
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Comptabilité et trésorerie</h1>
				<p class="text-sm text-ink-gray-6">Réglages de la société {{ compta?.societe.name }} : comptes, TVA, modes de paiement, exercices et droit de timbre. Chaque partie se modifie selon les droits de votre rôle.</p>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!compta" class="card p-4 text-ink-gray-6">Chargement des réglages…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<div v-if="compta" class="tarifs-layout">
				<nav class="card tarifs-liste" aria-label="Sections">
					<div class="tarifs-groupe">
						<button v-for="item in navSections" :key="item.key" type="button" class="tarif-item" :aria-current="section === item.key ? 'page' : undefined" @click="section = item.key">
							<span class="font-semibold">{{ item.label }}</span>
							<span class="flex items-center gap-1.5 text-xs text-ink-gray-6">
								<span class="compta-pastille" :class="`is-${item.etat}`" aria-hidden="true"></span>
								{{ item.resume }}<span class="sr-only"> ({{ ETAT_LABELS[item.etat] }})</span>
							</span>
						</button>
					</div>
				</nav>

				<!-- Vue d'ensemble -->
				<section v-if="section === 'bilan'" class="card tarifs-detail overflow-hidden" aria-labelledby="t-bilan">
					<div class="tarifs-head border-b-0">
						<div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
							<h2 id="t-bilan" class="text-lg font-semibold">État de la configuration</h2>
							<span class="text-ink-gray-6">{{ compta.bilan.length - aRegler }} point{{ compta.bilan.length - aRegler > 1 ? 's' : '' }} sur {{ compta.bilan.length }} en place</span>
						</div>
						<div class="compta-segments" aria-hidden="true">
							<span v-for="point in compta.bilan" :key="point.code" :class="`is-${point.etat}`"></span>
						</div>
						<p class="text-xs text-ink-gray-6">Tant qu'un point rouge reste, certaines pièces ne peuvent pas être validées, ou partent sans TVA, sans timbre ou sans compte.</p>
					</div>
					<template v-if="pointsARegler.length">
						<h3 class="compta-bande">À régler</h3>
						<div v-for="point in pointsARegler" :key="point.code" class="compta-point" :class="point.etat === 'manque' && 'is-manque'">
							<LucideCircleAlert v-if="point.etat === 'manque'" class="compta-point-icone text-tone-red" aria-hidden="true" />
							<LucideTriangleAlert v-else class="compta-point-icone compta-orange" aria-hidden="true" />
							<div class="min-w-0 flex-auto">
								<p class="font-semibold">{{ point.label }} <span class="badge ml-1" :class="point.etat === 'manque' ? 'tone-red' : 'tone-orange'">{{ ETAT_LABELS[point.etat] }}</span></p>
								<p class="text-sm text-ink-gray-7">{{ point.detail }}</p>
							</div>
							<button v-if="point.code === 'exercice' && compta.droits.exercices" type="button" class="btn-primary shrink-0" :disabled="busy" @click="creerExercice">Créer l'exercice {{ compta.exercice_suivant.name }}</button>
							<RouterLink v-if="point.ancre === 'tarifs'" :to="{ name: 'Tarifs' }" class="btn-secondary shrink-0">Régler</RouterLink>
							<button v-else type="button" class="btn-secondary shrink-0" @click="allerA(point.ancre)">Régler</button>
						</div>
					</template>
					<h3 class="compta-bande">En place</h3>
					<div class="compta-ok">
						<div v-for="point in pointsOk" :key="point.code" class="flex items-start gap-2.5 px-4 py-3">
							<LucideCircleCheck class="mt-0.5 h-4 w-4 flex-none text-tone-green" aria-hidden="true" />
							<div class="min-w-0">
								<p class="font-semibold">{{ point.label }}</p>
								<p class="text-xs text-ink-gray-6">{{ point.detail }}</p>
							</div>
						</div>
					</div>
				</section>

				<!-- Comptes par défaut -->
				<section v-else-if="section === 'comptes'" class="card tarifs-detail overflow-hidden" aria-labelledby="t-comptes">
					<div class="tarifs-head border-b-0 pb-1">
						<h2 id="t-comptes" class="text-lg font-semibold">Comptes par défaut</h2>
						<p class="text-sm text-ink-gray-6">Les comptes que les pièces reprennent quand l'article, le client ou le fournisseur n'en précise pas.<template v-if="!compta.droits.comptes"> Lecture seule pour votre rôle.</template></p>
					</div>
					<div class="compta-groupes">
						<div v-for="groupe in compta.comptes.groupes" :key="groupe.titre" class="compta-groupe-carte">
							<h3 class="stock-groupe-titre mt-0">{{ groupe.titre }}</h3>
							<div v-for="champ in groupe.champs" :key="champ.field" class="form-field">
								<label class="field-label flex items-center gap-1.5" :for="`compte-${champ.field}`">
									{{ champ.label }} <span v-if="champ.requis" class="req">obligatoire</span>
									<span v-if="compteModifie(champ.field)" class="badge tone-amber">modifié</span>
								</label>
								<select v-search :id="`compte-${champ.field}`" v-model="comptes[champ.field]" class="field-input" :disabled="!compta.droits.comptes">
									<option v-if="!champ.requis || !comptes[champ.field]" value="">—</option>
									<option v-for="compte in compta.comptes.options[champ.field]" :key="compte" :value="compte">{{ libelleCompte(compte) }}</option>
								</select>
								<p v-if="champ.aide" class="field-note">{{ champ.aide }}</p>
							</div>
						</div>
					</div>
					<div v-if="compta.droits.comptes" class="stock-barre" :class="comptesDirty && 'is-dirty'">
						<span class="flex-auto text-sm" :class="comptesDirty ? 'font-medium text-tone-amber' : 'text-ink-gray-6'">{{ comptesDirty ? `${comptesModifies} compte${comptesModifies > 1 ? 's' : ''} modifié${comptesModifies > 1 ? 's' : ''}, non enregistré${comptesModifies > 1 ? 's' : ''}` : 'Aucune modification' }}</span>
						<button type="button" class="btn-ghost" :disabled="busy || !comptesDirty" @click="annulerComptes">Annuler</button>
						<button type="button" class="btn-primary" :disabled="busy || !comptesDirty" @click="enregistrerComptes">Enregistrer</button>
					</div>
				</section>

				<!-- TVA -->
				<section v-else-if="section === 'tva'" class="card tarifs-detail overflow-hidden" aria-labelledby="t-tva">
					<div class="tarifs-head">
						<div class="flex flex-wrap items-start gap-3">
							<div class="min-w-0 flex-[1_1_20rem]">
								<h2 id="t-tva" class="text-lg font-semibold">TVA</h2>
								<p class="text-sm text-ink-gray-6">Les taux proposés par la liste « TVA » des pièces. Le taux par défaut est présélectionné sur chaque nouvelle pièce ; on peut le changer pièce par pièce.</p>
							</div>
							<button v-if="compta.droits.tva_creer.vente || compta.droits.tva_creer.achat" type="button" class="btn-secondary" :disabled="busy" @click="nouveauTaux = { sens: compta.droits.tva_creer[tvaSens] ? tvaSens : compta.droits.tva_creer.vente ? 'vente' : 'achat', taux: '' }"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Nouveau taux</button>
						</div>
						<div class="seg self-start" role="group" aria-label="Sens">
							<button v-for="sens in TVA_SENS" :key="sens.key" type="button" :aria-pressed="tvaSens === sens.key" @click="tvaSens = sens.key">{{ sens.key === 'vente' ? 'Ventes' : 'Achats' }}</button>
						</div>
						<p class="text-xs text-ink-gray-6">{{ TVA_SENS.find((s) => s.key === tvaSens)?.help }}</p>
					</div>
					<div class="overflow-x-auto">
						<table class="ref-table tarifs-table listes-table">
							<thead>
								<tr><th>Par défaut</th><th>Taux</th><th>Libellé et compte</th><th>Proposé</th></tr>
							</thead>
							<tbody>
								<tr v-for="taux in compta.tva[tvaSens]" :key="taux.name" :class="[taux.defaut && 'compta-defaut', !taux.actif && 'text-ink-gray-6']">
									<td><input type="radio" :name="`tva-defaut-${tvaSens}`" :checked="taux.defaut" :disabled="!compta.droits.tva[tvaSens] || !taux.actif || busy" :aria-label="`Taux par défaut : ${taux.titre}`" @change="actionTva(tvaSens, taux, 'defaut')" /></td>
									<td class="text-base font-semibold tabular-nums">{{ formatTaux(taux.taux) }}</td>
									<td>
										<span class="font-medium text-ink-gray-9">{{ taux.titre }}</span>
										<span v-if="taux.defaut" class="badge tone-green ml-1.5">par défaut</span>
										<span v-if="taux.compte" class="block text-xs text-ink-gray-6">{{ libelleCompte(taux.compte) }}</span>
									</td>
									<td>
										<label class="flex items-center gap-2 text-sm" :title="taux.defaut ? 'Le taux par défaut reste proposé' : undefined">
											<input type="checkbox" role="switch" class="table-panel-switch" :checked="taux.actif" :disabled="!compta.droits.tva[tvaSens] || taux.defaut || busy" :aria-label="`Proposer ${taux.titre}`" @change="actionTva(tvaSens, taux, taux.actif ? 'desactiver' : 'activer')" />
											{{ taux.actif ? 'Proposé' : 'Retiré' }}
										</label>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
					<p class="field-note px-4 py-3">Un taux retiré n'est plus proposé sur les nouvelles pièces ; les pièces existantes le gardent. Le taux par défaut ne se retire pas : choisissez-en d'abord un autre.</p>
				</section>

				<!-- Modes de paiement -->
				<section v-else-if="section === 'modes'" class="card tarifs-detail overflow-hidden" aria-labelledby="t-modes">
					<div class="tarifs-head">
						<div class="flex flex-wrap items-start gap-3">
							<div class="min-w-0 flex-[1_1_20rem]">
								<h2 id="t-modes" class="text-lg font-semibold">Modes de paiement</h2>
								<p class="text-sm text-ink-gray-6">Le compte où arrive l'argent encaissé, ou d'où part l'argent payé. Sans compte propre, c'est la banque ou la caisse par défaut. Chaque changement est enregistré aussitôt.</p>
							</div>
							<button v-if="compta.droits.modes_creer" type="button" class="btn-secondary" :disabled="busy" @click="nouveauMode = { nom: '', type: 'Bank', compte: '' }"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Nouveau mode</button>
						</div>
						<div v-if="modesBloques.length" role="status" class="tarifs-bandeau tone-red">
							<span class="flex-auto"><b>{{ modesBloques.map((m) => `« ${m.name} »`).join(', ') }}</b> {{ modesBloques.length > 1 ? "n'ont" : "n'a" }} ni compte ni compte de repli : un paiement par ce mode ne peut pas être enregistré. Choisissez son compte ci-dessous.</span>
						</div>
					</div>
					<div class="overflow-x-auto">
						<table class="ref-table tarifs-table listes-table">
							<thead>
								<tr><th>Mode</th><th>Type</th><th>Compte</th><th>Utilisé par</th><th>Proposé</th><th><span class="sr-only">Actions</span></th></tr>
							</thead>
							<tbody>
								<tr v-for="mode in compta.modes" :key="mode.name" :class="[mode.actif && !mode.compte && !mode.repli && 'stock-sous', !mode.actif && 'text-ink-gray-6']">
									<td class="font-medium text-ink-gray-9">{{ mode.name }}</td>
									<td><span class="badge" :class="mode.type === 'Cash' ? 'tone-green' : mode.type === 'Bank' ? 'tone-blue' : 'tone-gray'">{{ MODE_TYPES.find((t) => t.value === mode.type)?.label }}</span></td>
									<td>
										<select v-search class="field-input" :value="mode.compte ?? ''" :disabled="!compta.droits.modes || busy" :aria-label="`Compte du mode ${mode.name}`" @change="changerMode(mode, { compte: ($event.target as HTMLSelectElement).value })">
											<option value="">{{ mode.repli ? `Par défaut : ${libelleCompte(mode.repli)}` : '— aucun —' }}</option>
											<option v-for="compte in compta.comptes_tresorerie" :key="compte" :value="compte">{{ libelleCompte(compte) }}</option>
										</select>
										<small v-if="mode.actif && !mode.compte && !mode.repli" class="block font-medium text-tone-red">Aucun compte : à choisir</small>
									</td>
									<td class="whitespace-nowrap tabular-nums" :class="!mode.usages && 'text-ink-gray-6'">{{ mode.usages ? `${mode.usages} paiement${mode.usages > 1 ? 's' : ''}` : 'Jamais utilisé' }}</td>
									<td>
										<label class="flex items-center gap-2 text-sm">
											<input type="checkbox" role="switch" class="table-panel-switch" :checked="mode.actif" :disabled="!compta.droits.modes || busy" :aria-label="`Proposer le mode ${mode.name}`" @change="changerMode(mode, { actif: ($event.target as HTMLInputElement).checked })" />
											{{ mode.actif ? 'Proposé' : 'Retiré' }}
										</label>
									</td>
									<td class="text-right">
										<button v-if="compta.droits.modes_supprimer" type="button" class="app-icon-bare text-tone-red" :disabled="busy || mode.usages > 0" :aria-label="`Supprimer le mode ${mode.name}`" :title="mode.usages ? `Utilisé par ${mode.usages} paiement${mode.usages > 1 ? 's' : ''} : retirez-le plutôt` : 'Supprimer'" @click="supprimerMode(mode)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
					<p class="field-note px-4 py-3">Banque : la référence (n° de chèque, de virement) est demandée à chaque paiement. Un mode retiré n'est plus proposé ; les paiements passés le gardent. Seul un mode jamais utilisé se supprime.</p>
				</section>

				<!-- Exercices -->
				<section v-else-if="section === 'exercices'" class="card tarifs-detail" aria-labelledby="t-exercices">
					<div class="tarifs-head">
						<h2 id="t-exercices" class="text-lg font-semibold">Exercices comptables</h2>
						<p class="text-sm text-ink-gray-6">Une pièce ne peut être validée que si sa date tombe dans un exercice. Créez le suivant avant la fin de l'année.</p>
						<p v-if="pointExercice && pointExercice.etat !== 'ok'" class="tarifs-bandeau" :class="pointExercice.etat === 'manque' ? 'tone-red' : 'tone-orange'">{{ pointExercice.detail }}</p>
					</div>
					<ul class="reglages-lines px-4">
						<li v-for="exercice in compta.exercices" :key="exercice.name" class="reglages-line">
							<span class="flex-auto font-semibold">{{ exercice.name }}</span>
							<span class="text-sm tabular-nums">{{ formatDate(exercice.debut) }} → {{ formatDate(exercice.fin) }}</span>
							<span v-if="exercice.en_cours" class="badge tone-green">en cours</span>
						</li>
					</ul>
					<div v-if="compta.droits.exercices" class="flex justify-end px-4 py-3">
						<button type="button" class="btn-primary" :disabled="busy" @click="creerExercice"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Créer l'exercice {{ compta.exercice_suivant.name }}</button>
					</div>
				</section>

				<!-- Droit de timbre -->
				<section v-else class="card tarifs-detail" aria-labelledby="t-timbre">
					<div class="tarifs-head">
						<h2 id="t-timbre" class="flex items-center gap-1.5 text-lg font-semibold"><LucideLock class="h-4 w-4 text-ink-gray-6" aria-hidden="true" />Droit de timbre</h2>
						<p class="text-sm text-ink-gray-6">Ajouté aux factures de vente payées en espèces, sur le montant TTC, au centime.</p>
					</div>
					<div class="overflow-x-auto px-4">
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
					</div>
					<p class="px-4 pt-3 text-sm">Minimum : {{ compta.timbre.minimum }} DA · Compte : {{ compta.timbre.compte_nom ? libelleCompte(compta.timbre.compte_nom) : `${compta.timbre.compte} (absent du plan)` }}</p>
					<p class="field-note px-4 pb-4">Barème de la loi de finances, livré avec l'application. Faites-le confirmer par votre comptable ; s'il change, demandez la mise à jour de l'application.</p>
				</section>
			</div>
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
