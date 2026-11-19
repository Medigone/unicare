<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import LucideKeyRound from '~icons/lucide/key-round'
import LucideLogIn from '~icons/lucide/log-in'
import LucidePlus from '~icons/lucide/plus'
import LucideSearch from '~icons/lucide/search'
import FormDialog from '@shared/components/FormDialog.vue'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import { getUtilisateurs, saveRoles, saveUtilisateur, setMotDePasse } from '@/lib/api'
import { confirmAction } from '@/lib/confirm'
import { derniereConnexion, entreDansLeBureau, genererMotDePasse, initiales, MOT_DE_PASSE_MIN, rolesLabels, utilisateurErreur, type ReglagesUtilisateurs, type Utilisateur, type UtilisateurForm } from '@/lib/utilisateurs'

/**
 * Réglages › Utilisateurs : à gauche les comptes, à droite la fiche du compte choisi (identité, compte actif, rôles
 * en cartes à cocher, enregistrés d'un bloc) ; « Qui fait quoi » montre tous les comptes actifs face aux rôles et
 * enregistre plusieurs changements d'un coup. Les rôles posés sur le Desk et non proposés ici sont conservés.
 * Réservé, pour les modifications, à qui peut modifier les comptes.
 */
const reglages = ref<ReglagesUtilisateurs | null>(null)
const error = ref('')
const actionError = ref('')
const notice = ref('')
const busy = ref(false)
const ecran = ref<'comptes' | 'matrice'>('comptes')

async function load() {
	try {
		reglages.value = await getUtilisateurs()
		error.value = ''
	} catch (e) {
		if (!reglages.value) error.value = (e as Error).message
	}
}

const peutModifier = computed(() => reglages.value?.droits.modifier ?? false)
const rolesBureau = computed(() => reglages.value?.roles_bureau ?? [])
const tousRoles = computed(() => reglages.value?.roles.flatMap((d) => d.roles) ?? [])
const AVATARS = ['blue', 'green', 'amber', 'violet', 'orange', 'gray']
function avatarTon(row: Pick<Utilisateur, 'name' | 'actif'>) {
	if (!row.actif) return 'tone-gray'
	let h = 0
	for (const c of row.name) h = (h * 31 + c.charCodeAt(0)) % 997
	return `tone-${AVATARS[h % (AVATARS.length - 1)]}`
}

// Liste des comptes.
const vue = ref<'actifs' | 'desactives'>('actifs')
const recherche = ref('')
const plain = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
const liste = computed(() =>
	(reglages.value?.utilisateurs ?? [])
		.filter((row) => (vue.value === 'actifs' ? row.actif : !row.actif))
		.filter((row) => plain(`${row.nom} ${row.name}`).includes(plain(recherche.value.trim()))),
)
const compte = (key: 'actifs' | 'desactives') => (reglages.value?.utilisateurs ?? []).filter((row) => (key === 'actifs' ? row.actif : !row.actif)).length
function alerteDe(row: Utilisateur) {
	if (!row.actif) return { label: 'désactivé', ton: 'tone-gray' }
	if (!row.acces_bureau) return { label: 'hors bureau', ton: 'tone-amber' }
	if (!row.derniere_connexion) return { label: 'jamais connecté', ton: 'tone-gray' }
	return null
}

// Fiche du compte choisi : copie de travail, enregistrée d'un bloc.
const selection = ref<string | null>(null)
const choisi = computed(() => reglages.value?.utilisateurs.find((row) => row.name === selection.value) ?? null)
const fiche = ref<UtilisateurForm | null>(null)
const ficheBase = ref('')
const ficheError = ref('')
const ficheDirty = computed(() => Boolean(fiche.value) && JSON.stringify(fiche.value) !== ficheBase.value)
function chargerFiche(row: Utilisateur | null) {
	fiche.value = row ? { email: row.name, prenom: row.prenom, nom_famille: row.nom_famille, actif: row.actif, roles: [...row.roles], mot_de_passe: '' } : null
	ficheBase.value = JSON.stringify(fiche.value)
	ficheError.value = ''
}
async function choisir(row: Utilisateur) {
	if (row.name === selection.value) return
	if (ficheDirty.value && !(await confirmAction({ title: 'Modifications non enregistrées', message: `Les changements faits sur ${choisi.value?.nom} seront perdus.`, confirmLabel: 'Abandonner', danger: true }))) return
	selection.value = row.name
	chargerFiche(row)
}
watch(reglages, (fresh) => {
	if (!fresh) return
	const actuel = fresh.utilisateurs.find((row) => row.name === selection.value)
	if (!actuel) {
		const premier = fresh.utilisateurs.find((row) => row.actif) ?? fresh.utilisateurs[0] ?? null
		selection.value = premier?.name ?? null
		chargerFiche(premier)
	} else if (!ficheDirty.value) chargerFiche(actuel)
})
const ficheBureau = computed(() => Boolean(fiche.value && entreDansLeBureau(fiche.value.roles, rolesBureau.value)))
const ficheDomaines = computed(() => (reglages.value?.roles ?? []).filter((d) => d.roles.some((r) => fiche.value?.roles.includes(r.role))).map((d) => d.domaine))
function basculerRole(role: string) {
	if (!fiche.value) return
	const i = fiche.value.roles.indexOf(role)
	if (i >= 0) fiche.value.roles.splice(i, 1)
	else fiche.value.roles.push(role)
}
async function enregistrerFiche() {
	const row = choisi.value
	const values = fiche.value
	if (!row || !values || busy.value) return
	const erreur = utilisateurErreur(values, false)
	if (erreur) {
		ficheError.value = erreur
		return
	}
	if (row.actif && !values.actif && !(await confirmAction({ title: 'Désactiver le compte', message: `${row.nom} ne pourra plus se connecter. Ses pièces et son historique restent.`, confirmLabel: 'Désactiver', danger: true }))) return
	busy.value = true
	ficheError.value = ''
	try {
		ficheBase.value = JSON.stringify(values)
		reglages.value = await saveUtilisateur(row, { prenom: values.prenom, nom_famille: values.nom_famille, actif: values.actif, roles: values.roles })
		notice.value = `Compte de ${values.prenom} enregistré.`
	} catch (e) {
		ficheBase.value = ''
		ficheError.value = (e as Error).message
		await load()
	} finally {
		busy.value = false
	}
}

// Création.
const creation = ref<(UtilisateurForm & { profil: string | null }) | null>(null)
const creationError = ref('')
function ouvrirCreation() {
	creation.value = { email: '', prenom: '', nom_famille: '', actif: true, roles: [], mot_de_passe: genererMotDePasse(), profil: null }
	creationError.value = ''
}
function appliquerProfil(profil: { label: string; roles: string[] }) {
	if (!creation.value) return
	creation.value.profil = profil.label
	creation.value.roles = [...profil.roles]
}
function basculerRoleCreation(role: string) {
	if (!creation.value) return
	const i = creation.value.roles.indexOf(role)
	if (i >= 0) creation.value.roles.splice(i, 1)
	else creation.value.roles.push(role)
	creation.value.profil = null
}
async function creer() {
	const values = creation.value
	if (!values || busy.value) return
	const erreur = utilisateurErreur(values, true)
	if (erreur) {
		creationError.value = erreur
		return
	}
	busy.value = true
	try {
		reglages.value = await saveUtilisateur(null, { email: values.email, prenom: values.prenom, nom_famille: values.nom_famille, mot_de_passe: values.mot_de_passe, roles: values.roles })
		notice.value = `Compte de ${values.prenom} créé. Communiquez-lui son identifiant et son mot de passe.`
		const cree = reglages.value.utilisateurs.find((row) => row.name === values.email.trim().toLowerCase())
		creation.value = null
		vue.value = 'actifs'
		if (cree) {
			selection.value = cree.name
			chargerFiche(cree)
		}
	} catch (e) {
		creationError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}

// Mot de passe.
const motDePasse = ref<{ compte: Utilisateur; valeur: string; error: string } | null>(null)
const copie = ref(false)
async function copier(texte: string) {
	try {
		await navigator.clipboard.writeText(texte)
		copie.value = true
		setTimeout(() => (copie.value = false), 1500)
	} catch {
		// Le navigateur refuse : le texte reste sélectionnable dans le champ.
	}
}
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

// Qui fait quoi : brouillon des rôles par compte actif, enregistré d'un coup.
const matrice = reactive<Record<string, string[]>>({})
const actifs = computed(() => (reglages.value?.utilisateurs ?? []).filter((row) => row.actif))
function ouvrirMatrice() {
	for (const key of Object.keys(matrice)) delete matrice[key]
	for (const row of actifs.value) matrice[row.name] = [...row.roles]
	ecran.value = 'matrice'
}
const rolesMatrice = (row: Utilisateur) => matrice[row.name] ?? row.roles
function caseModifiee(row: Utilisateur, role: string) {
	return rolesMatrice(row).includes(role) !== row.roles.includes(role)
}
function basculerCase(row: Utilisateur, role: string) {
	const roles = [...rolesMatrice(row)]
	const i = roles.indexOf(role)
	if (i >= 0) roles.splice(i, 1)
	else roles.push(role)
	matrice[row.name] = roles
}
const changementsMatrice = computed(() => actifs.value.filter((row) => tousRoles.value.some((r) => caseModifiee(row, r.role))))
const nbCasesModifiees = computed(() => actifs.value.reduce((n, row) => n + tousRoles.value.filter((r) => caseModifiee(row, r.role)).length, 0))
const totalParRole = (role: string) => actifs.value.filter((row) => rolesMatrice(row).includes(role)).length
async function enregistrerMatrice() {
	if (busy.value || !changementsMatrice.value.length) return
	busy.value = true
	actionError.value = ''
	try {
		reglages.value = await saveRoles(changementsMatrice.value.map((row) => ({ name: row.name, modified: row.modified, roles: rolesMatrice(row) })))
		notice.value = `${nbCasesModifiees.value} changement${nbCasesModifiees.value > 1 ? 's' : ''} de rôle enregistré${nbCasesModifiees.value > 1 ? 's' : ''}.`
		for (const row of actifs.value) matrice[row.name] = [...row.roles]
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
async function quitterMatrice() {
	if (nbCasesModifiees.value && !(await confirmAction({ title: 'Changements non enregistrés', message: `${nbCasesModifiees.value} changement${nbCasesModifiees.value > 1 ? 's' : ''} de rôle seront perdus.`, confirmLabel: 'Abandonner', danger: true }))) return
	ecran.value = 'comptes'
}

onMounted(load)
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Réglages' }, { label: 'Utilisateurs' }]" active="utilisateurs">
		<div class="bureau-work tdb">
			<div class="flex flex-wrap items-end gap-3">
				<div class="min-w-0 flex-[1_1_24rem]">
					<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">{{ ecran === 'matrice' ? 'Qui fait quoi' : 'Utilisateurs' }}</h1>
					<p class="text-sm text-ink-gray-6">{{ ecran === 'matrice' ? 'Les comptes actifs face aux rôles du bureau. Cliquez sur une case pour donner ou retirer un rôle ; rien n\'est enregistré avant « Enregistrer ».' : "Qui se connecte, et ce que chacun peut faire. L'identifiant de connexion est l'adresse e-mail." }}</p>
				</div>
				<template v-if="reglages && ecran === 'comptes'">
					<button type="button" class="btn-secondary" @click="ouvrirMatrice">Qui fait quoi</button>
					<button v-if="reglages.droits.creer" type="button" class="btn-primary" :disabled="busy" @click="ouvrirCreation"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Nouvel utilisateur</button>
				</template>
				<template v-else-if="reglages">
					<span class="text-sm" :class="nbCasesModifiees ? 'font-medium text-tone-amber' : 'text-ink-gray-6'">{{ nbCasesModifiees ? `${nbCasesModifiees} changement${nbCasesModifiees > 1 ? 's' : ''} non enregistré${nbCasesModifiees > 1 ? 's' : ''}` : 'Aucun changement' }}</span>
					<button type="button" class="btn-secondary" :disabled="busy" @click="quitterMatrice">Retour aux comptes</button>
					<button v-if="peutModifier" type="button" class="btn-primary" :disabled="busy || !nbCasesModifiees" @click="enregistrerMatrice">Enregistrer</button>
				</template>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!reglages" class="card p-4 text-ink-gray-6">Chargement des comptes…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<!-- Comptes : liste et fiche -->
			<div v-if="reglages && ecran === 'comptes'" class="tarifs-layout">
				<nav class="card tarifs-liste" aria-label="Comptes">
					<label class="bureau-search">
						<LucideSearch class="h-3.5 w-3.5" aria-hidden="true" />
						<input v-model="recherche" class="field-input" type="search" aria-label="Chercher un utilisateur" placeholder="Nom ou adresse" />
					</label>
					<div class="seg self-start" role="group" aria-label="Afficher">
						<button type="button" :aria-pressed="vue === 'actifs'" @click="vue = 'actifs'">Actifs<span class="ml-1 tabular-nums text-ink-gray-6">{{ compte('actifs') }}</span></button>
						<button type="button" :aria-pressed="vue === 'desactives'" @click="vue = 'desactives'">Désactivés<span class="ml-1 tabular-nums text-ink-gray-6">{{ compte('desactives') }}</span></button>
					</div>
					<div class="tarifs-groupe">
						<button v-for="row in liste" :key="row.name" type="button" class="tarif-item util-item" :aria-current="row.name === selection ? 'page' : undefined" @click="choisir(row)">
							<span class="util-avatar" :class="avatarTon(row)" aria-hidden="true">{{ initiales(row.nom) }}</span>
							<span class="min-w-0 flex-auto">
								<span class="block truncate font-semibold">{{ row.nom }}<span v-if="row.moi" class="font-normal text-ink-gray-6"> (vous)</span></span>
								<span class="block truncate text-xs text-ink-gray-6">{{ rolesLabels(row.roles, reglages.roles).join(' · ') || 'Aucun rôle' }}</span>
							</span>
							<span v-if="alerteDe(row)" class="badge flex-none" :class="alerteDe(row)!.ton">{{ alerteDe(row)!.label }}</span>
						</button>
						<p v-if="!liste.length" class="px-2.5 text-sm text-ink-gray-6">{{ recherche.trim() ? 'Aucun compte ne correspond.' : vue === 'actifs' ? 'Aucun compte actif.' : 'Aucun compte désactivé.' }}</p>
					</div>
				</nav>

				<section v-if="choisi && fiche" class="card tarifs-detail overflow-hidden" aria-labelledby="t-fiche">
					<div class="tarifs-head flex-row flex-wrap items-center gap-3.5">
						<span class="util-avatar util-avatar-lg" :class="avatarTon({ name: choisi.name, actif: fiche.actif })" aria-hidden="true">{{ initiales(choisi.nom) }}</span>
						<div class="min-w-0 flex-[1_1_16rem]">
							<h2 id="t-fiche" class="text-lg font-semibold">{{ choisi.nom }}<span v-if="choisi.moi" class="text-sm font-normal text-ink-gray-6"> (vous)</span></h2>
							<p class="text-sm text-ink-gray-7">{{ choisi.name }}</p>
							<p class="text-xs text-ink-gray-6">Dernière connexion : {{ derniereConnexion(choisi.derniere_connexion).toLowerCase() }}</p>
						</div>
						<div v-if="peutModifier" class="flex flex-wrap items-center gap-2.5">
							<label class="flex items-center gap-2 text-sm font-medium" :title="choisi.moi ? 'Vous ne pouvez pas désactiver votre propre compte' : undefined">
								<input v-model="fiche.actif" type="checkbox" role="switch" class="table-panel-switch" :disabled="choisi.moi || busy" />
								{{ fiche.actif ? 'Compte actif' : 'Compte désactivé' }}
							</label>
							<button type="button" class="btn-secondary" :disabled="busy" @click="motDePasse = { compte: choisi, valeur: genererMotDePasse(), error: '' }"><LucideKeyRound class="h-3.5 w-3.5" aria-hidden="true" />Changer le mot de passe</button>
						</div>
					</div>
					<div class="flex flex-col gap-3.5 px-4 pb-4 pt-1">
						<div class="tarifs-bandeau" :class="!fiche.actif ? 'tone-gray' : ficheBureau ? 'tone-green' : 'tone-amber'">
							<LucideLogIn class="h-4 w-4 flex-none" aria-hidden="true" />
							<span class="flex-auto">{{ !fiche.actif ? 'Compte désactivé : la personne ne peut plus se connecter. Son historique est conservé.' : ficheBureau ? `Entre dans le bureau · ${fiche.roles.length} rôle${fiche.roles.length > 1 ? 's' : ''} · ${ficheDomaines.join(', ')}` : "Sans rôle du bureau, ce compte n'entrera pas dans le bureau : cochez au moins un rôle ci-dessous." }}</span>
						</div>
						<div v-if="peutModifier" class="form-grid">
							<div class="form-field">
								<label class="field-label" for="u-prenom">Prénom <span class="req">obligatoire</span></label>
								<input id="u-prenom" v-model="fiche.prenom" class="field-input" autocomplete="off" />
							</div>
							<div class="form-field">
								<label class="field-label" for="u-nom">Nom</label>
								<input id="u-nom" v-model="fiche.nom_famille" class="field-input" autocomplete="off" />
							</div>
						</div>
						<h3 class="text-base font-semibold">Ce que la personne peut faire</h3>
						<div v-for="domaine in reglages.roles" :key="domaine.domaine" class="util-domaine">
							<span class="stock-groupe-titre m-0 pt-2.5">{{ domaine.domaine }}</span>
							<div class="util-roles">
								<label v-for="choix in domaine.roles" :key="choix.role" class="util-role" :class="fiche.roles.includes(choix.role) && 'is-on'">
									<input type="checkbox" class="mt-0.5" :checked="fiche.roles.includes(choix.role)" :disabled="!peutModifier || busy || (choisi.moi && choix.role === 'System Manager')" @change="basculerRole(choix.role)" />
									<span>
										<span class="block font-semibold">{{ choix.label }}</span>
										<span class="block text-xs text-ink-gray-6">{{ choix.aide }}</span>
									</span>
								</label>
							</div>
						</div>
						<p v-if="choisi.autres_roles" class="field-note">Ce compte a aussi {{ choisi.autres_roles }} rôle{{ choisi.autres_roles > 1 ? 's' : '' }} posé{{ choisi.autres_roles > 1 ? 's' : '' }} sur le Desk ; ils restent inchangés.</p>
						<p v-if="ficheError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ ficheError }}</p>
					</div>
					<div v-if="peutModifier" class="stock-barre" :class="ficheDirty && 'is-dirty'">
						<span class="flex-auto text-sm" :class="ficheDirty ? 'font-medium text-tone-amber' : 'text-ink-gray-6'">{{ ficheDirty ? `Modifications non enregistrées pour ${choisi.nom}` : 'Aucune modification' }}</span>
						<button type="button" class="btn-ghost" :disabled="busy || !ficheDirty" @click="chargerFiche(choisi)">Annuler</button>
						<button type="button" class="btn-primary" :disabled="busy || !ficheDirty" @click="enregistrerFiche">Enregistrer</button>
					</div>
					<p v-else class="field-note px-4 pb-4">Lecture seule : seul un administrateur modifie les comptes.</p>
				</section>
			</div>

			<!-- Qui fait quoi -->
			<div v-else-if="reglages" class="card overflow-x-auto">
				<table class="util-matrice">
					<thead>
						<tr>
							<th rowspan="2" class="text-left">Personne</th>
							<th v-for="domaine in reglages.roles" :key="domaine.domaine" :colspan="domaine.roles.length" class="util-dom">{{ domaine.domaine }}</th>
						</tr>
						<tr>
							<template v-for="domaine in reglages.roles" :key="domaine.domaine">
								<th v-for="(choix, index) in domaine.roles" :key="choix.role" :class="index === 0 && 'util-sep'" :title="choix.aide">{{ choix.label }}</th>
							</template>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in actifs" :key="row.name">
							<th scope="row" class="text-left">
								<span class="flex items-center gap-2">
									<span class="util-avatar util-avatar-sm" :class="avatarTon(row)" aria-hidden="true">{{ initiales(row.nom) }}</span>
									<span class="whitespace-nowrap font-medium">{{ row.nom }}</span>
									<span v-if="!entreDansLeBureau(rolesMatrice(row), rolesBureau)" class="badge tone-amber">hors bureau</span>
								</span>
							</th>
							<template v-for="domaine in reglages.roles" :key="domaine.domaine">
								<td v-for="(choix, index) in domaine.roles" :key="choix.role" :class="[index === 0 && 'util-sep', caseModifiee(row, choix.role) && 'is-modifie']">
									<input type="checkbox" class="util-case" :checked="rolesMatrice(row).includes(choix.role)" :disabled="!peutModifier || busy || (row.moi && choix.role === 'System Manager')" :aria-label="`${choix.label} (${domaine.domaine}) pour ${row.nom}`" @change="basculerCase(row, choix.role)" />
								</td>
							</template>
						</tr>
						<tr class="util-totaux">
							<th scope="row" class="text-left font-medium text-ink-gray-6">Personnes</th>
							<template v-for="domaine in reglages.roles" :key="domaine.domaine">
								<td v-for="(choix, index) in domaine.roles" :key="choix.role" class="tabular-nums" :class="[index === 0 && 'util-sep', totalParRole(choix.role) ? 'text-ink-gray-8' : 'font-semibold text-tone-red']">{{ totalParRole(choix.role) }}</td>
							</template>
						</tr>
					</tbody>
				</table>
				<p class="field-note px-4 py-3">Un zéro en rouge veut dire que personne ne peut faire ce travail. Une case changée est surlignée jusqu'à l'enregistrement.</p>
			</div>
		</div>

		<FormDialog v-if="creation" title="Nouvel utilisateur" :dirty="Boolean(creation.email.trim() || creation.prenom.trim())" :busy="busy" @close="creation = null" @submit="creer">
			<div class="form-grid">
				<div class="form-field">
					<label class="field-label" for="c-email">Adresse e-mail <span class="req">obligatoire</span></label>
					<input id="c-email" v-model="creation.email" type="email" class="field-input" autocomplete="off" placeholder="prenom.nom@exemple.dz" />
					<p class="field-note">C'est son identifiant de connexion ; il ne se change plus ensuite.</p>
				</div>
				<div class="form-field">
					<label class="field-label" for="c-prenom">Prénom <span class="req">obligatoire</span></label>
					<input id="c-prenom" v-model="creation.prenom" class="field-input" autocomplete="off" />
				</div>
				<div class="form-field">
					<label class="field-label" for="c-nom">Nom</label>
					<input id="c-nom" v-model="creation.nom_famille" class="field-input" autocomplete="off" />
				</div>
				<div class="form-field">
					<label class="field-label" for="c-mdp">Mot de passe <span class="req">obligatoire</span></label>
					<div class="flex gap-2">
						<input id="c-mdp" v-model="creation.mot_de_passe" type="text" class="field-input min-w-0 flex-auto font-mono" autocomplete="new-password" spellcheck="false" />
						<button type="button" class="btn-secondary" @click="creation.mot_de_passe = genererMotDePasse()">Générer</button>
						<button type="button" class="btn-ghost" @click="copier(creation.mot_de_passe)">{{ copie ? 'Copié' : 'Copier' }}</button>
					</div>
					<p class="field-note">Au moins {{ MOT_DE_PASSE_MIN }} caractères. Communiquez-le à la personne ; elle pourra le changer.</p>
				</div>
			</div>
			<div v-if="reglages?.profils.length" class="mt-4 flex flex-col gap-2">
				<span class="field-label">Partir d'un profil</span>
				<div class="flex flex-wrap gap-1.5">
					<button v-for="profil in reglages.profils" :key="profil.label" type="button" class="util-profil" :aria-pressed="creation.profil === profil.label" @click="appliquerProfil(profil)">{{ profil.label }}</button>
				</div>
				<p class="field-note">Un profil coche des rôles d'un coup ; ajustez ensuite à la main.</p>
			</div>
			<fieldset class="mt-3 flex flex-col gap-2 rounded-control border border-[var(--outline-gray-2)] px-3 py-2.5">
				<legend class="field-label px-1">Rôles</legend>
				<div v-for="domaine in reglages?.roles" :key="domaine.domaine" class="util-domaine util-domaine-compact">
					<span class="stock-groupe-titre m-0">{{ domaine.domaine }}</span>
					<div class="flex flex-wrap gap-x-4 gap-y-1.5">
						<label v-for="choix in domaine.roles" :key="choix.role" class="flex items-center gap-1.5 text-sm" :title="choix.aide">
							<input type="checkbox" :checked="creation.roles.includes(choix.role)" @change="basculerRoleCreation(choix.role)" />{{ choix.label }}
						</label>
					</div>
				</div>
			</fieldset>
			<p class="mt-3 rounded-control px-3 py-2 text-sm" :class="entreDansLeBureau(creation.roles, rolesBureau) ? 'tone-green' : 'tone-amber'">{{ entreDansLeBureau(creation.roles, rolesBureau) ? `Entrera dans le bureau avec ${creation.roles.length} rôle${creation.roles.length > 1 ? 's' : ''}.` : "Sans rôle du bureau, ce compte n'entrera pas dans le bureau." }}</p>
			<p v-if="creationError" role="alert" class="mt-3 rounded-control tone-red px-3 py-2 text-sm">{{ creationError }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="creer">{{ busy ? 'Création…' : 'Créer le compte' }}</button>
			</template>
		</FormDialog>

		<FormDialog v-if="motDePasse" :title="`Mot de passe de ${motDePasse.compte.nom}`" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour enregistrer" @close="motDePasse = null" @submit="changerMotDePasse">
			<div class="form-field">
				<label class="field-label" for="u-nouveau-mdp">Nouveau mot de passe</label>
				<div class="flex gap-2">
					<input id="u-nouveau-mdp" v-model="motDePasse.valeur" type="text" class="field-input min-w-0 flex-auto font-mono" autocomplete="new-password" spellcheck="false" @input="motDePasse.error = ''" />
					<button type="button" class="btn-secondary" @click="motDePasse.valeur = genererMotDePasse()">Générer</button>
					<button type="button" class="btn-ghost" @click="copier(motDePasse.valeur)">{{ copie ? 'Copié' : 'Copier' }}</button>
				</div>
				<p class="field-note">L'ancien ne fonctionnera plus. Communiquez le nouveau à la personne.</p>
			</div>
			<p v-if="motDePasse.error" role="alert" class="mt-3 rounded-control tone-red px-3 py-2 text-sm">{{ motDePasse.error }}</p>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="changerMotDePasse">Changer le mot de passe</button>
			</template>
		</FormDialog>
		<AppToast :message="notice" tone="success" @close="notice = ''" />
	</BureauShell>
</template>
