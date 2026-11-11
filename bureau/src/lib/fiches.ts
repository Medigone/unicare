/** La fiche du bureau qui ouvre une pièce, d'après son doctype. Sans fiche (écriture comptable…) : le Desk, en dernier recours. */
import { deskUrl } from './display'

export const FICHE_ROUTES: Record<string, string> = {
	Customer: 'Client',
	Supplier: 'Fournisseur',
	Item: 'Article',
	Warehouse: 'Depot',
	Batch: 'Lot',
	Quotation: 'DevisFiche',
	'Sales Order': 'CommandeFiche',
	'Delivery Note': 'LivraisonFiche',
	'Sales Invoice': 'FactureFiche',
	'Supplier Quotation': 'DevisFournisseurFiche',
	'Purchase Order': 'CommandeAchatFiche',
	'Purchase Receipt': 'ReceptionFiche',
	'Purchase Invoice': 'FactureAchatFiche',
	'Payment Entry': 'PaiementFiche',
	'Stock Entry': 'MouvementFiche',
	'Stock Reconciliation': 'InventaireFiche',
	'Ordre de Conditionnement': 'OrdreFiche',
	'Recette de Conditionnement': 'RecetteFiche',
}

export function ficheTo(doctype: string, name: string) {
	const route = FICHE_ROUTES[doctype]
	return route ? { name: route, params: { id: name } } : null
}

/** Lien d'une pièce : la fiche du bureau, ou l'adresse du Desk pour une pièce que le bureau n'affiche pas. */
export function pieceLink(doctype: string, name: string): { to: { name: string; params: { id: string } } } | { href: string } {
	const to = ficheTo(doctype, name)
	return to ? { to } : { href: deskUrl(doctype, name) }
}
