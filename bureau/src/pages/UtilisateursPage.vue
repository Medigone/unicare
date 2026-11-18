<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import LucidePlus from '~icons/lucide/plus'
import FormDialog from '@shared/components/FormDialog.vue'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import { getUtilisateurs, saveUtilisateur, setMotDePasse } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'
import { derniereConnexion, MOT_DE_PASSE_MIN, rolesLabels, utilisateurErreur, type ReglagesUtilisateurs, type Utilisateur, type UtilisateurForm } from '@/lib/utilisateurs'

/**
 * Réglages › Utilisateurs : les comptes, ce que chacun peut faire (rôles regroupés par domaine) et leur mot de passe.
 * Les rôles posés sur le Desk et non proposés ici sont conservés. Réservé à qui peut modifier les comptes.
 */
const reglages = ref<ReglagesUtilisateurs | null>(null)
const error = ref('')
const notice = ref('')
const busy = ref(false)
const afficherInactifs = ref(false)

async function load() {
	try {
		reglages.value = await getUtilisateurs()
		error.value = ''
	} catch (e) {
		if (!reglages.value) error.value = (e as Error).message
	}
}

const visibles = computed(() => (reglages.value?.utilisateurs ?? []).filter((row) => afficherInactifs.value || row.actif))
const inactifs = computed(() => (reglages.value?.utilisateurs ?? []).filter((row) => !row.actif).length)

// Fenêtre de création ou de modification.
const compte = ref<Utilisateur | null>(null)
const form = ref<UtilisateurForm | null>(null)
const formBase = ref('')
const formError = ref('')
const creation = computed(() => Boolean(form.value) && !compte.value)
const dirty = computed(() => Boolean(form.value) && JSON.stringify(form.value) !== formBase.value)
const sansBureau = computed(() => Boolean(form.value && reglages.value && form.value.actif && !form.value.roles.some((role) => reglages.value?.roles_bureau.includes(role))))

function ouvrir(row: Utilisateur | null) {
	compte.value = row
	form.value = row
		? { email: row.name, prenom: row.prenom, nom_famille: row.nom_famille, actif: row.actif, roles: [...row.roles], mot_de_passe: '' }
		: { email: '', prenom: '', nom_famille: '', actif: true, roles: [], mot_de_passe: '' }
	formBase.value = JSON.stringify(form.value)
	formError.value = ''
}
function fermer() {
	form.value = null
	compte.value = null
}
async function enregistrer() {
	const values = form.value
	if (!values || busy.value) return
	const erreur = utilisateurErreur(values, creation.value)
	if (erreur) {
		formError.value = erreur
		return
	}
	if (compte.value && compte.value.actif && !values.actif) {
		const ok = await confirmAction({ title: 'Désactiver le compte', message: `${compte.value.nom} ne pourra plus se connecter. Ses pièces et son historique restent.`, confirmLabel: 'Désactiver', danger: true })
		if (!ok) return
	}
	busy.value = true
	formError.value = ''
	try {
		const payload = creation.value ? values : { prenom: values.prenom, nom_famille: values.nom_famille, actif: values.actif, roles: values.roles }
		reglages.value = await saveUtilisateur(compte.value, payload)
		notice.value = creation.value ? `Compte de ${values.prenom} créé. Communiquez-lui son identifiant et son mot de passe.` : 'Compte enregistré.'
		fermer()
	} catch (e) {
		formError.value = (e as Error).message
		await load()
		const frais = reglages.value?.utilisateurs.find((row) => row.name === compte.value?.name)
		if (frais) compte.value = frais
	} finally {
		busy.value = false
	}
}

// Mot de passe.
const motDePasse = ref<{ compte: Utilisateur; valeur: string; error: string } | null>(null)
async function changerMotDePasse() {
	const state = motDePasse.value
	if (!state || busy.value) return
	if (state.valeur.length < MOT_DE_PASSE_MIN) {
		state.error = `Le mot de passe doit faire au moins ${MOT_DE_PASSE_MIN} caractères.`
		return
	}
	busy.value = true
	try {
		reglages.value = await setMotDePasse(state.compte, state.valeur)
		notice.value = `Mot de passe de ${state.compte.nom} changé.`
		motDePasse.value = null
	} catch (e) {
		state.error = (e as Error).message
		await load()
		const frais = reglages.value?.utilisateurs.find((row) => row.name === state.compte.name)
		if (frais) state.compte = frais
	} finally {
		busy.value = false
	}
}

onMounted(load)
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Réglages' }, { label: 'Utilisateurs' }]" active="utilisateurs">
		<div class="bureau-work tdb">
			<div>
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Utilisateurs</h1>
				<p class="text-sm text-ink-gray-6">Qui se connecte, et ce que chacun peut faire. L'identifiant de connexion est l'adresse e-mail.</p>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!reglages" class="card p-4 text-ink-gray-6">Chargement des comptes…</p>

			<section v-if="reglages" class="card reglages-card" aria-labelledby="t-comptes">
				<div class="flex flex-wrap items-center gap-2">
					<h2 id="t-comptes" class="flex-auto text-base font-semibold">Comptes</h2>
					<label v-if="inactifs" class="flex items-center gap-1.5 text-sm"><input v-model="afficherInactifs" type="checkbox" /> Afficher les {{ inactifs }} compte{{ inactifs > 1 ? 's' : '' }} désactivé{{ inactifs > 1 ? 's' : '' }}</label>
					<button v-if="reglages.droits.creer" type="button" class="btn-secondary" :disabled="busy" @click="ouvrir(null)"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Nouvel utilisateur</button>
				</div>
				<div class="overflow-x-auto">
					<table class="ref-table compta-table">
						<thead>
							<tr><th>Nom</th><th>Rôles</th><th>Dernière connexion</th><th><span class="sr-only">Actions</span></th></tr>
						</thead>
						<tbody>
							<tr v-for="row in visibles" :key="row.name" :class="!row.actif && 'text-ink-gray-5'">
								<td>
									<span class="font-medium">{{ row.nom }}</span><span v-if="row.moi" class="text-xs text-ink-gray-6"> (vous)</span>
									<small class="block text-ink-gray-6">{{ row.name }}</small>
								</td>
								<td>
									<span v-if="!row.actif" class="badge tone-gray">désactivé</span>
									<span v-else-if="!row.acces_bureau" class="badge tone-amber">n'entre pas dans le bureau</span>
									<span class="block text-sm">{{ rolesLabels(row.roles, reglages.roles).join(' · ') || 'Aucun rôle' }}</span>
									<small v-if="row.autres_roles" class="block text-ink-gray-6">et {{ row.autres_roles }} autre{{ row.autres_roles > 1 ? 's' : '' }} rôle{{ row.autres_roles > 1 ? 's' : '' }} (Desk)</small>
								</td>
								<td class="whitespace-nowrap text-sm">{{ derniereConnexion(row.derniere_connexion) }}</td>
								<td class="whitespace-nowrap text-right">
									<template v-if="reglages.droits.modifier">
										<button type="button" class="btn-ghost" :disabled="busy" @click="ouvrir(row)">Modifier</button>
										<button type="button" class="btn-ghost" :disabled="busy" @click="motDePasse = { compte: row, valeur: '', error: '' }">Mot de passe</button>
									</template>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
				<p v-if="!reglages.droits.modifier" class="field-note">Lecture seule : seul un administrateur modifie les comptes.</p>
			</section>
		</div>

		<FormDialog v-if="form" :title="creation ? 'Nouvel utilisateur' : `Modifier ${compte?.nom}`" :dirty="dirty" :busy="busy" :hint="creation ? 'Ctrl + Entrée pour créer' : 'Ctrl + Entrée pour enregistrer'" @close="fermer" @submit="enregistrer">
			<div class="form-grid">
				<div v-if="creation" class="form-field">
					<label class="field-label" for="u-email">Adresse e-mail <span class="req">obligatoire</span></label>
					<input id="u-email" v-model="form.email" type="email" class="field-input" autocomplete="off" placeholder="prenom.nom@exemple.dz" />
					<p class="field-note">C'est son identifiant de connexion ; il ne se change plus ensuite.</p>
				</div>
				<div class="form-field">
					<label class="field-label" for="u-prenom">Prénom <span class="req">obligatoire</span></label>
					<input id="u-prenom" v-model="form.prenom" class="field-input" autocomplete="off" />
				</div>
				<div class="form-field">
					<label class="field-label" for="u-nom">Nom</label>
					<input id="u-nom" v-model="form.nom_famille" class="field-input" autocomplete="off" />
				</div>
				<div v-if="creation" class="form-field">
					<label class="field-label" for="u-mdp">Mot de passe <span class="req">obligatoire</span></label>
					<input id="u-mdp" v-model="form.mot_de_passe" type="text" class="field-input" autocomplete="new-password" spellcheck="false" />
					<p class="field-note">Au moins {{ MOT_DE_PASSE_MIN }} caractères, difficile à deviner. Communiquez-le à la personne ; elle pourra le changer.</p>
				</div>
				<label v-if="!creation" class="flex items-center gap-2 text-sm"><input v-model="form.actif" type="checkbox" :disabled="compte?.moi" /> Compte actif (peut se connecter)</label>
			</div>
			<fieldset class="mt-4 flex flex-col gap-3">
				<legend class="field-label">Ce que la personne peut faire</legend>
				<div v-for="domaine in reglages?.roles" :key="domaine.domaine">
					<h3 class="compta-groupe">{{ domaine.domaine }}</h3>
					<label v-for="choix in domaine.roles" :key="choix.role" class="flex items-start gap-2 py-0.5 text-sm">
						<input v-model="form.roles" type="checkbox" class="mt-0.5" :value="choix.role" :disabled="compte?.moi && choix.role === 'System Manager'" />
						<span><b>{{ choix.label }}</b> — {{ choix.aide }}</span>
					</label>
				</div>
				<p v-if="sansBureau" class="rounded-control tone-amber px-3 py-2 text-sm">Sans rôle de la partie Production ni Administrateur, ce compte n'entrera pas dans le bureau : il n'aura que le Desk.</p>
				<p v-if="compte?.autres_roles" class="field-note">Ce compte a aussi {{ compte.autres_roles }} rôle{{ compte.autres_roles > 1 ? 's' : '' }} posé{{ compte.autres_roles > 1 ? 's' : '' }} sur le Desk ; ils restent inchangés.</p>
			</fieldset>
			<p v-if="formError" role="alert" class="mt-3 rounded-control tone-red px-3 py-2 text-sm">{{ formError }}</p>
		</FormDialog>

		<FormDialog v-if="motDePasse" :title="`Mot de passe de ${motDePasse.compte.nom}`" :dirty="Boolean(motDePasse.valeur)" :busy="busy" hint="Ctrl + Entrée pour enregistrer" @close="motDePasse = null" @submit="changerMotDePasse">
			<div class="form-field">
				<label class="field-label" for="u-nouveau-mdp">Nouveau mot de passe</label>
				<input id="u-nouveau-mdp" v-model="motDePasse.valeur" type="text" class="field-input" autocomplete="new-password" spellcheck="false" @input="motDePasse.error = ''" />
				<p class="field-note">L'ancien ne fonctionnera plus. Communiquez le nouveau à la personne.</p>
			</div>
			<p v-if="motDePasse.error" role="alert" class="mt-3 rounded-control tone-red px-3 py-2 text-sm">{{ motDePasse.error }}</p>
		</FormDialog>
		<AppToast :message="notice" tone="success" @close="notice = ''" />
	</BureauShell>
</template>
