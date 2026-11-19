/** Réglages › Utilisateurs : comptes, rôles et mots de passe (unicare/api/bureau_utilisateurs.py). */

export interface Utilisateur {
	name: string
	nom: string
	prenom: string
	nom_famille: string
	actif: boolean
	derniere_connexion: string | null
	/** Rôles proposés par la page que le compte possède. */
	roles: string[]
	/** Autres rôles, posés sur le Desk : conservés tels quels. */
	autres_roles: number
	acces_bureau: boolean
	moi: boolean
	modified: string
}

export interface RoleChoix {
	role: string
	label: string
	aide: string
}

export interface ReglagesUtilisateurs {
	utilisateurs: Utilisateur[]
	roles: { domaine: string; roles: RoleChoix[] }[]
	/** Rôles qui ouvrent le bureau : sans l'un d'eux, le compte n'y entre pas. */
	roles_bureau: string[]
	/** Profils de la création : des rôles cochés d'un coup. */
	profils: { label: string; roles: string[] }[]
	droits: { creer: boolean; modifier: boolean }
}

export interface UtilisateurForm {
	email: string
	prenom: string
	nom_famille: string
	actif: boolean
	roles: string[]
	mot_de_passe: string
}

export const MOT_DE_PASSE_MIN = 8

/** Libellés en clair des rôles d'un compte, dans l'ordre de la page. */
export function rolesLabels(roles: string[], choix: ReglagesUtilisateurs['roles']): string[] {
	return choix.flatMap((domaine) => domaine.roles).filter((row) => roles.includes(row.role)).map((row) => row.label)
}

/** Erreur de saisie, ou null. `creation` : e-mail et mot de passe obligatoires. */
export function utilisateurErreur(form: UtilisateurForm, creation: boolean): string | null {
	if (creation && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return "Indiquez une adresse e-mail valide : c'est l'identifiant de connexion."
	if (!form.prenom.trim()) return 'Indiquez au moins le prénom.'
	if (creation && form.mot_de_passe.length < MOT_DE_PASSE_MIN) return `Le mot de passe doit faire au moins ${MOT_DE_PASSE_MIN} caractères.`
	return null
}

/** « il y a 3 jours », « aujourd'hui », ou « jamais ». */
export function derniereConnexion(iso: string | null, today = new Date()): string {
	if (!iso) return 'Jamais connecté'
	const day = new Date(iso.replace(' ', 'T'))
	const start = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
	const jours = Math.round((start(today) - start(day)) / 86_400_000)
	if (jours <= 0) return "Aujourd'hui"
	if (jours === 1) return 'Hier'
	if (jours < 30) return `Il y a ${jours} jours`
	return `Le ${new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' }).format(day)}`
}

/** Initiales d'un nom : « Nadia Hamdi » → « NH ». */
export function initiales(nom: string): string {
	const parts = nom.trim().split(/\s+/).filter(Boolean)
	return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : (parts[0]?.[1] ?? ''))).toUpperCase()
}

const MOTS = ['Cedre', 'Olive', 'Atlas', 'Jasmin', 'Tulipe', 'Figuier', 'Palmier', 'Grenade', 'Amande', 'Oasis', 'Dune', 'Saule']

/** Un mot de passe facile à dicter et difficile à deviner : « Olive-Atlas-4827 ». */
export function genererMotDePasse(alea: (n: number) => number = (n) => crypto.getRandomValues(new Uint32Array(1))[0] % n): string {
	const a = MOTS[alea(MOTS.length)]
	let b = MOTS[alea(MOTS.length)]
	if (b === a) b = MOTS[(MOTS.indexOf(a) + 1) % MOTS.length]
	return `${a}-${b}-${String(1000 + alea(9000))}`
}

/** Les rôles ouvrent-ils le bureau ? */
export function entreDansLeBureau(roles: string[], rolesBureau: string[]): boolean {
	return roles.some((role) => rolesBureau.includes(role))
}
