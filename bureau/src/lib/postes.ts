/** Postes du bureau : le menu de chacun et le poste actif, retenu par navigateur. Un poste n'accorde aucun droit. */
import { ref, type Component } from 'vue'
import LucideBuilding2 from '~icons/lucide/building-2'
import LucideBanknote from '~icons/lucide/banknote'
import LucideFileText from '~icons/lucide/file-text'
import LucideReceipt from '~icons/lucide/receipt'
import LucideShoppingCart from '~icons/lucide/shopping-cart'
import LucideTruck from '~icons/lucide/truck'
import LucideLayoutDashboard from '~icons/lucide/layout-dashboard'
import LucidePackage from '~icons/lucide/package'
import { canRead } from './droits'

export interface Poste {
	key: string
	label: string
}

export interface PosteNavItem {
	id: string
	label: string
	icon: Component
	to?: { name: string }
	href?: string
	/** Sans droit de lecture sur ce document (ou aucun de ceux-ci), l'entrée n'apparaît pas. */
	doctype?: string | string[]
}

export interface PosteNavGroup {
	title: string
	items: PosteNavItem[]
}

/** Même clé que `POSTES` côté serveur (unicare/api/bureau_postes.py). */
const CONDITIONNEMENT: Poste = { key: 'conditionnement', label: 'Conditionnement' }
const STORAGE_KEY = 'bureau-poste'

// Chaque page reprise dans le poste ajoute ici son entrée, avec le document qui en règle la lecture.
// Les écrans pas encore repris peuvent s'ouvrir sur le Desk (`href: '/app/...'`).
export const NAV: Record<string, PosteNavGroup[]> = {
	conditionnement: [
		{
			title: 'Mon travail',
			items: [{ id: 'accueil', label: 'Accueil', icon: LucideLayoutDashboard, to: { name: 'Home' } }],
		},
		{
			title: 'Ventes',
			items: [
				{ id: 'devis', label: 'Devis', icon: LucideFileText, to: { name: 'DevisListe' }, doctype: 'Quotation' },
				{ id: 'commandes', label: 'Commandes', icon: LucideShoppingCart, to: { name: 'Commandes' }, doctype: 'Sales Order' },
				{ id: 'livraisons', label: 'Bons de livraison', icon: LucideTruck, to: { name: 'Livraisons' }, doctype: 'Delivery Note' },
				{ id: 'factures', label: 'Factures', icon: LucideReceipt, to: { name: 'Factures' }, doctype: 'Sales Invoice' },
			],
		},
		{
			title: 'Trésorerie',
			items: [{ id: 'paiements', label: 'Paiements', icon: LucideBanknote, to: { name: 'Paiements' }, doctype: 'Payment Entry' }],
		},
		{
			title: 'Référentiel',
			items: [
				{ id: 'clients', label: 'Clients', icon: LucideBuilding2, to: { name: 'Clients' }, doctype: 'Customer' },
				{ id: 'articles', label: 'Articles', icon: LucidePackage, to: { name: 'Articles' }, doctype: 'Item' },
			],
		},
	],
}

function readStored() {
	try {
		return localStorage.getItem(STORAGE_KEY)
	} catch {
		return null
	}
}

const storedKey = ref(readStored())

/** Sans liste du serveur (développement), le bureau ouvre le poste Conditionnement. */
export function availablePostes(): Poste[] {
	return window.postes?.length ? window.postes : [CONDITIONNEMENT]
}

/** Un choix retenu qui n'appartient plus à ce compte est ignoré. */
export function activePoste(): Poste {
	const postes = availablePostes()
	return postes.find((poste) => poste.key === storedKey.value) ?? postes[0]
}

export function setPoste(key: string) {
	storedKey.value = key
	try {
		localStorage.setItem(STORAGE_KEY, key)
	} catch {
		// Stockage indisponible : le choix vaut pour cette session.
	}
}

/** Menu d'un poste, sans les entrées que le rôle ne peut pas lire ni les groupes restés vides. */
export function navFor(key: string): PosteNavGroup[] {
	return (NAV[key] ?? [])
		.map((group) => ({ ...group, items: group.items.filter((item) => canRead(item.doctype)) }))
		.filter((group) => group.items.length)
}
