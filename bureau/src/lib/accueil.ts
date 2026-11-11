/** Accueil du bureau (unicare/api/bureau_accueil.py) : types et petites règles d'affichage. */
import type { Indicateur } from './tableaux'

export type Ton = 'red' | 'amber' | 'blue' | 'gray'

export interface AFaire {
	module: string
	nature: string
	fiche: string
	name: string
	titre: string
	detail: string | null
	badge: string | null
	ton: Ton
	/** Ce qu'il y a à faire : le libellé du bouton (« Encaisser », « Démarrer »…). */
	action: string
}

export interface PourVous {
	name: string
	texte: string
	type: 'mention' | 'alerte'
	de: string | null
	lu: boolean
	quand: string
	fiche: string | null
	document: string | null
	module: string
}

export interface Recent {
	nature: string
	fiche: string
	name: string
	libelle: string | null
	quand: string
}

export interface Accueil {
	jour: string
	prenom: string
	a_faire: { retard: AFaire[]; aujourdhui: AFaire[]; a_valider: AFaire[]; totaux: { retard: number; aujourdhui: number; a_valider: number } }
	pour_vous: PourVous[]
	non_lus: number
	recents: Recent[]
	mois: (Indicateur & { module: string; tableau: string })[]
}

/** La phrase du bonjour : ce qui attend, en une ligne. */
export function resumeJournee(totaux: Accueil['a_faire']['totaux']) {
	const parts: string[] = []
	if (totaux.retard) parts.push(`${totaux.retard} ${totaux.retard > 1 ? 'choses' : 'chose'} en retard`)
	if (totaux.aujourdhui) parts.push(`${totaux.aujourdhui} pour aujourd'hui`)
	if (totaux.a_valider) parts.push(`${totaux.a_valider} brouillon${totaux.a_valider > 1 ? 's' : ''} à valider`)
	if (!parts.length) return 'Rien en attente : tout est à jour.'
	const last = parts.pop()
	return `${parts.length ? `${parts.join(', ')} et ${last}` : last}.`
}

/** Moment relatif court : « 10:42 », « hier », « lun. », « 3 nov. ». */
export function quandText(value: string, now = new Date()) {
	const date = new Date(value.replace(' ', 'T'))
	const start = new Date(now.getFullYear(), now.getMonth(), now.getDate())
	const days = Math.floor((start.getTime() - new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()) / 86_400_000)
	if (days <= 0) return new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' }).format(date)
	if (days === 1) return 'hier'
	if (days < 7) return new Intl.DateTimeFormat('fr-FR', { weekday: 'short' }).format(date)
	return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' }).format(date)
}
