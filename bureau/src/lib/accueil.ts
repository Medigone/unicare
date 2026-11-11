/** Accueil du bureau (unicare/api/bureau_accueil.py) : types et petites règles d'affichage. */
import type { Indicateur } from './tableaux'
import type { Component } from 'vue'
import LucideArrowLeftRight from '~icons/lucide/arrow-left-right'
import LucideBanknote from '~icons/lucide/banknote'
import LucideBookOpen from '~icons/lucide/book-open'
import LucideBuilding2 from '~icons/lucide/building-2'
import LucideClipboardCheck from '~icons/lucide/clipboard-check'
import LucideClipboardList from '~icons/lucide/clipboard-list'
import LucideFactory from '~icons/lucide/factory'
import LucideFileInput from '~icons/lucide/file-input'
import LucideFileText from '~icons/lucide/file-text'
import LucideLayers from '~icons/lucide/layers'
import LucidePackage from '~icons/lucide/package'
import LucidePackageCheck from '~icons/lucide/package-check'
import LucideReceipt from '~icons/lucide/receipt'
import LucideReceiptText from '~icons/lucide/receipt-text'
import LucideShoppingCart from '~icons/lucide/shopping-cart'
import LucideTruck from '~icons/lucide/truck'

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
	module: string
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

/** Icône de chaque pièce, d'après sa fiche, et teinte de son module : on reconnaît la ligne d'un coup d'œil. */

export const FICHE_ICONS: Record<string, Component> = {
	DevisFiche: LucideFileText,
	CommandeFiche: LucideShoppingCart,
	LivraisonFiche: LucideTruck,
	FactureFiche: LucideReceipt,
	Client: LucideBuilding2,
	DevisFournisseurFiche: LucideFileInput,
	CommandeAchatFiche: LucideClipboardList,
	ReceptionFiche: LucidePackageCheck,
	FactureAchatFiche: LucideReceiptText,
	Fournisseur: LucideTruck,
	PaiementFiche: LucideBanknote,
	MouvementFiche: LucideArrowLeftRight,
	InventaireFiche: LucideClipboardCheck,
	Lot: LucideLayers,
	Article: LucidePackage,
	OrdreFiche: LucideFactory,
	RecetteFiche: LucideBookOpen,
}

export const MODULE_TONES: Record<string, string> = {
	Ventes: 'tone-blue',
	Achats: 'tone-violet',
	Trésorerie: 'tone-green',
	Stock: 'tone-orange',
	Production: 'tone-amber',
}

export function ficheIcon(fiche: string) {
	return FICHE_ICONS[fiche] ?? LucideFileText
}
