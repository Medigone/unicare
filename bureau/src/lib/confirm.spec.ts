import { describe, expect, it } from 'vitest'
import { confirmAction, confirmRequest, settleConfirm } from './confirm'

const request = { title: 'Valider la facture', message: 'La facture sera validée.', confirmLabel: 'Valider la facture' }

describe('confirmation des actions', () => {
	it('rend vrai quand la personne confirme', async () => {
		const answer = confirmAction(request)
		expect(confirmRequest.value?.title).toBe('Valider la facture')
		settleConfirm(true)
		await expect(answer).resolves.toBe(true)
		expect(confirmRequest.value).toBeNull()
	})

	it('rend faux quand la personne renonce', async () => {
		const answer = confirmAction(request)
		settleConfirm(false)
		await expect(answer).resolves.toBe(false)
	})

	it('une nouvelle demande abandonne la précédente', async () => {
		const first = confirmAction(request)
		const second = confirmAction({ ...request, title: 'Clôturer', danger: true })
		await expect(first).resolves.toBe(false)
		expect(confirmRequest.value?.danger).toBe(true)
		settleConfirm(true)
		await expect(second).resolves.toBe(true)
	})
})
