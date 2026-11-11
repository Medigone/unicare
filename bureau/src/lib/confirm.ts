/**
 * Confirmation avant une action du cycle d'une pièce (valider, créer la pièce suivante, changer de statut…).
 * `confirmAction` ouvre la fenêtre commune (ConfirmHost, montée une fois dans App.vue) et rend `true` si la
 * personne confirme. Une nouvelle demande remplace celle en cours, qui rend `false`.
 */
import { readonly, shallowRef } from 'vue'

export interface ConfirmRequest {
	title: string
	message: string
	/** Libellé du bouton qui confirme : l'action elle-même (« Valider la facture »), jamais « OK ». */
	confirmLabel: string
	/** Action difficile à défaire : le bouton est rouge. */
	danger?: boolean
}

interface Pending extends ConfirmRequest {
	resolve: (confirmed: boolean) => void
}

const pending = shallowRef<Pending | null>(null)

export const confirmRequest = readonly(pending)

export function confirmAction(request: ConfirmRequest): Promise<boolean> {
	pending.value?.resolve(false)
	return new Promise((resolve) => {
		pending.value = { ...request, resolve }
	})
}

export function settleConfirm(confirmed: boolean) {
	const current = pending.value
	pending.value = null
	current?.resolve(confirmed)
}
