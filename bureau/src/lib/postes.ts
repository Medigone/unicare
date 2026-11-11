/** Postes du bureau : le menu de chacun et le poste actif, retenu par navigateur. Un poste n'accorde aucun droit. */
import { ref, type Component } from 'vue'
import LucideBuilding2 from '~icons/lucide/building-2'
import LucideBanknote from '~icons/lucide/banknote'
import LucideFactory from '~icons/lucide/factory'
import LucideFileText from '~icons/lucide/file-text'
import LucideWarehouse from '~icons/lucide/warehouse'
import LucideBoxes from '~icons/lucide/boxes'
import LucideLayers from '~icons/lucide/layers'
import LucideArrowLeftRight from '~icons/lucide/arrow-left-right'
import LucideClipboardCheck from '~icons/lucide/clipboard-check'
import LucideReceiptText from '~icons/lucide/receipt-text'
import LucidePackageCheck from '~icons/lucide/package-check'
import LucideClipboardList from '~icons/lucide/clipboard-list'
import LucideFileInput from '~icons/lucide/file-input'
import LucideReceipt from '~icons/lucide/receipt'
import LucideShoppingCart from '~icons/lucide/shopping-cart'
import LucideTruck from '~icons/lucide/truck'
import LucideLayoutDashboard from '~icons/lucide/layout-dashboard'
import LucidePackage from '~icons/lucide/package'
import LucideChartColumn from '~icons/lucide/chart-column'
import LucideSettings2 from '~icons/lucide/settings-2'
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

// Le menu d'un poste se range par MODULE : le rail de gauche montre les modules, le second menu les pages du module
// ouvert. Une page reprise dans le bureau s'ajoute ici, dans son module, avec le document qui en règle la lecture.
// Une fiche de base va dans le module qui l'utilise le plus (Clients : Ventes ; Fournisseurs : Achats ; Articles : Stock).
// Les écrans pas encore repris s'ouvrent sur le Desk (`href: '/app/...'`).
export interface PosteModule {
	id: string
	label: string
	icon: Component
	/** Module qui est lui-même une page (Accueil) : pas de second menu. */
	to?: { name: string }
	/** Tableau de bord du module : première entrée de son menu, et page ouverte par le clic sur le module. */
	dashboard?: { name: string }
	groups: PosteNavGroup[]
}

export const NAV: Record<string, PosteModule[]> = {
	conditionnement: [
		{ id: 'accueil', label: 'Accueil', icon: LucideLayoutDashboard, to: { name: 'Home' }, groups: [] },
		{
			id: 'ventes',
			label: 'Ventes',
			icon: LucideShoppingCart,
			dashboard: { name: 'TableauVentes' },
			groups: [
				{
					title: 'Pièces',
					items: [
						{ id: 'devis', label: 'Devis', icon: LucideFileText, to: { name: 'DevisListe' }, doctype: 'Quotation' },
						{ id: 'commandes', label: 'Commandes', icon: LucideShoppingCart, to: { name: 'Commandes' }, doctype: 'Sales Order' },
						{ id: 'livraisons', label: 'Bons de livraison', icon: LucideTruck, to: { name: 'Livraisons' }, doctype: 'Delivery Note' },
						{ id: 'factures', label: 'Factures', icon: LucideReceipt, to: { name: 'Factures' }, doctype: 'Sales Invoice' },
					],
				},
				{ title: 'Référentiel', items: [{ id: 'clients', label: 'Clients', icon: LucideBuilding2, to: { name: 'Clients' }, doctype: 'Customer' }] },
			],
		},
		{
			id: 'achats',
			label: 'Achats',
			icon: LucideTruck,
			dashboard: { name: 'TableauAchats' },
			groups: [
				{
					title: 'Pièces',
					items: [
						{ id: 'devis-fournisseurs', label: 'Devis fournisseur', icon: LucideFileInput, to: { name: 'DevisFournisseurListe' }, doctype: 'Supplier Quotation' },
						{ id: 'commandes-achat', label: "Commandes d'achat", icon: LucideClipboardList, to: { name: 'CommandesAchat' }, doctype: 'Purchase Order' },
						{ id: 'receptions', label: 'Réceptions', icon: LucidePackageCheck, to: { name: 'Receptions' }, doctype: 'Purchase Receipt' },
						{ id: 'factures-achat', label: "Factures d'achat", icon: LucideReceiptText, to: { name: 'FacturesAchat' }, doctype: 'Purchase Invoice' },
					],
				},
				{ title: 'Référentiel', items: [{ id: 'fournisseurs', label: 'Fournisseurs', icon: LucideFactory, to: { name: 'Fournisseurs' }, doctype: 'Supplier' }] },
			],
		},
		{
			id: 'stock',
			label: 'Stock',
			icon: LucidePackage,
			dashboard: { name: 'TableauStock' },
			groups: [
				{
					title: 'Suivi',
					items: [
						{ id: 'etat-stock', label: 'État du stock', icon: LucideBoxes, to: { name: 'EtatStock' }, doctype: 'Bin' },
						{ id: 'mouvements', label: 'Mouvements', icon: LucideArrowLeftRight, to: { name: 'Mouvements' }, doctype: 'Stock Entry' },
						{ id: 'inventaires', label: 'Inventaires', icon: LucideClipboardCheck, to: { name: 'Inventaires' }, doctype: 'Stock Reconciliation' },
						{ id: 'lots', label: 'Lots', icon: LucideLayers, to: { name: 'Lots' }, doctype: 'Batch' },
					],
				},
				{
					title: 'Référentiel',
					items: [
						{ id: 'articles', label: 'Articles', icon: LucidePackage, to: { name: 'Articles' }, doctype: 'Item' },
						{ id: 'depots', label: 'Dépôts', icon: LucideWarehouse, to: { name: 'Depots' }, doctype: 'Warehouse' },
					],
				},
			],
		},
		{
			id: 'tresorerie',
			label: 'Trésorerie',
			icon: LucideBanknote,
			dashboard: { name: 'TableauTresorerie' },
			groups: [{ title: 'Règlements', items: [{ id: 'paiements', label: 'Paiements', icon: LucideBanknote, to: { name: 'Paiements' }, doctype: 'Payment Entry' }] }],
		},
		{
			id: 'production',
			label: 'Production',
			icon: LucideFactory,
			dashboard: { name: 'TableauProduction' },
			groups: [
				{
					title: 'Pièces',
					items: [{ id: 'ordres', label: 'Ordres de conditionnement', icon: LucideFactory, to: { name: 'Ordres' }, doctype: 'Ordre de Conditionnement' }],
				},
				{
					title: 'Référentiel',
					items: [{ id: 'recettes', label: 'Recettes', icon: LucideFileText, to: { name: 'Recettes' }, doctype: 'Recette de Conditionnement' }],
				},
				{
					title: 'Réglages',
					items: [{ id: 'reglages-production', label: 'Checklists et paramètres', icon: LucideSettings2, to: { name: 'ReglagesProduction' }, doctype: 'Checklist Ordre Conditionnement' }],
				},
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

/** L'entrée « Tableau de bord » d'un module (son `id` : `tableau-<module>`). */
export function dashboardItem(module: PosteModule): PosteNavItem | undefined {
	return module.dashboard && { id: `tableau-${module.id}`, label: 'Tableau de bord', icon: LucideChartColumn, to: module.dashboard }
}

/**
 * Modules d'un poste, sans les pages que le rôle ne peut pas lire, ni les groupes et modules restés vides.
 * Le tableau de bord passe en tête (groupe sans titre) tant qu'il reste au moins une page lisible dans le module.
 */
export function navFor(key: string): PosteModule[] {
	return (NAV[key] ?? [])
		.map((module) => {
			const groups = module.groups.map((group) => ({ ...group, items: group.items.filter((item) => canRead(item.doctype)) })).filter((group) => group.items.length)
			const dashboard = dashboardItem(module)
			return { ...module, groups: dashboard && groups.length ? [{ title: '', items: [dashboard] }, ...groups] : groups }
		})
		.filter((module) => module.to || module.groups.length)
}

/** Le module qui contient cette page (ou qui est cette page) ; à défaut, le premier. */
export function moduleOf(modules: PosteModule[], pageId?: string) {
	return modules.find((module) => module.id === pageId || module.groups.some((group) => group.items.some((item) => item.id === pageId))) ?? modules[0]
}

/** Où mène le clic sur un module : sa page, sinon sa première page (son tableau de bord quand il en a un). */
export function moduleTarget(module: PosteModule): { to?: { name: string }; href?: string } {
	if (module.to) return { to: module.to }
	const first = module.groups[0]?.items[0]
	return first ? { to: first.to, href: first.href } : {}
}

/** Toutes les pages du poste, avec leur module : pour la recherche « Aller à… ». */
export function pagesFor(key: string) {
	return navFor(key).flatMap((module) =>
		module.to ? [{ id: module.id, label: module.label, module: '', icon: module.icon, to: module.to, href: undefined as string | undefined }] : module.groups.flatMap((group) => group.items.map((item) => ({ id: item.id, label: item.label, module: module.label, icon: item.icon, to: item.to, href: item.href }))),
	)
}
