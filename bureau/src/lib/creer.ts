/**
 * Création rapide, de n'importe quelle page : le bouton « Créer » de l'accueil et les raccourcis N puis une lettre.
 * Chaque entrée ouvre la fenêtre de création de son écran ; une fois créé, on arrive sur la fiche.
 */
import { ref, type Component } from 'vue'
import LucideArrowLeftRight from '~icons/lucide/arrow-left-right'
import LucideBanknote from '~icons/lucide/banknote'
import LucideBookOpen from '~icons/lucide/book-open'
import LucideBuilding2 from '~icons/lucide/building-2'
import LucideClipboardCheck from '~icons/lucide/clipboard-check'
import LucideClipboardList from '~icons/lucide/clipboard-list'
import LucideFactory from '~icons/lucide/factory'
import LucideFileInput from '~icons/lucide/file-input'
import LucideFileText from '~icons/lucide/file-text'
import LucidePackage from '~icons/lucide/package'
import LucideShoppingCart from '~icons/lucide/shopping-cart'
import LucideTruck from '~icons/lucide/truck'
import { canCreate } from './droits'

export type CreerKey = 'devis' | 'commande' | 'paiement' | 'ordre' | 'client' | 'commande_achat' | 'devis_fournisseur' | 'fournisseur' | 'mouvement' | 'inventaire' | 'article' | 'recette'

export interface CreerItem {
	key: CreerKey
	label: string
	hint?: string
	groupe: 'frequent' | 'Ventes' | 'Achats' | 'Stock et production'
	/** Raccourci : N puis cette lettre. */
	lettre?: string
	doctype: string
	/** La fiche ouverte après la création. */
	fiche: string
	icon: Component
}

export const CREER_ITEMS: CreerItem[] = [
	{ key: 'devis', label: 'Devis', hint: 'pour un client', groupe: 'frequent', lettre: 'd', doctype: 'Quotation', fiche: 'DevisFiche', icon: LucideFileText },
	{ key: 'commande', label: 'Commande client', hint: 'à livrer', groupe: 'frequent', lettre: 'c', doctype: 'Sales Order', fiche: 'CommandeFiche', icon: LucideShoppingCart },
	{ key: 'paiement', label: 'Paiement', hint: 'encaisser ou payer', groupe: 'frequent', lettre: 'p', doctype: 'Payment Entry', fiche: 'PaiementFiche', icon: LucideBanknote },
	{ key: 'ordre', label: 'Ordre de production', hint: 'produit, quantité, date', groupe: 'frequent', lettre: 'o', doctype: 'Ordre de Conditionnement', fiche: 'OrdreFiche', icon: LucideFactory },
	{ key: 'client', label: 'Client', groupe: 'Ventes', lettre: 'l', doctype: 'Customer', fiche: 'Client', icon: LucideBuilding2 },
	{ key: 'commande_achat', label: "Commande d'achat", groupe: 'Achats', lettre: 'a', doctype: 'Purchase Order', fiche: 'CommandeAchatFiche', icon: LucideClipboardList },
	{ key: 'devis_fournisseur', label: 'Devis fournisseur', groupe: 'Achats', lettre: 'u', doctype: 'Supplier Quotation', fiche: 'DevisFournisseurFiche', icon: LucideFileInput },
	{ key: 'fournisseur', label: 'Fournisseur', groupe: 'Achats', lettre: 'f', doctype: 'Supplier', fiche: 'Fournisseur', icon: LucideTruck },
	{ key: 'mouvement', label: 'Mouvement de stock', groupe: 'Stock et production', lettre: 'm', doctype: 'Stock Entry', fiche: 'MouvementFiche', icon: LucideArrowLeftRight },
	{ key: 'inventaire', label: 'Inventaire', groupe: 'Stock et production', lettre: 'i', doctype: 'Stock Reconciliation', fiche: 'InventaireFiche', icon: LucideClipboardCheck },
	{ key: 'article', label: 'Article', groupe: 'Stock et production', lettre: 'r', doctype: 'Item', fiche: 'Article', icon: LucidePackage },
	{ key: 'recette', label: 'Recette', groupe: 'Stock et production', lettre: 'e', doctype: 'Recette de Conditionnement', fiche: 'RecetteFiche', icon: LucideBookOpen },
]

/** Les entrées que ce rôle peut créer. */
export function creerItems() {
	return CREER_ITEMS.filter((item) => canCreate(item.doctype))
}

/** L'entrée d'une lettre (raccourci N puis lettre), parmi celles que ce rôle peut créer. */
export function itemForLetter(letter: string, items = creerItems()) {
	return items.find((item) => item.lettre === letter.toLowerCase())
}

/** La fenêtre de création ouverte, partagée par le bouton et les raccourcis. */
export const creating = ref<CreerKey | null>(null)

export function creer(key: CreerKey) {
	creating.value = key
}
