/** Versions d'une pièce : la pièce d'origine et celles qui en sont refaites après annulation (« Modifier » du Desk). */

export interface VersionRef {
	name: string
	docstatus: number
	status: string
}

export interface Versions {
	/** La pièce annulée dont celle-ci est la nouvelle version. */
	origine: VersionRef | null
	/** Les nouvelles versions faites de celle-ci, la plus ancienne d'abord. */
	suivantes: VersionRef[]
}

/** Pièces qui ont des versions : le module serveur qui les refait. */
export type VersionModule = 'devis' | 'commandes' | 'livraisons' | 'factures' | 'paiements' | 'devis_fournisseur' | 'commandes_achat' | 'receptions' | 'factures_achat'

/** La version qui remplace une pièce annulée, si elle existe encore (brouillon ou validée). */
export function openVersion(versions: Versions | null | undefined) {
	return versions?.suivantes.find((entry) => entry.docstatus < 2) ?? null
}
