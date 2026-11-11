import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { routes } from '@/router'

vi.mock('@/lib/api', async (original) => ({
	...(await original<typeof import('@/lib/api')>()),
	getReglagesProduction: vi.fn(async () => ({
		checklists: [{ name: 'Checklist standard', modified: '2026-08-13 14:37:17', actif: true, lignes: [{ controle: 'Ligne dégagée', obligatoire: true }], ordres: 6 }],
		parametres: { modified: '2026-11-11 19:34:16', warehouse_mp: 'Magasins - U', warehouse_conditionnement: 'Magasins - U', warehouse_atelier: 'Production - U', warehouse_pf: 'Produits finis - U', warehouse_rebuts: 'Rebus - U', tolerance: 5 },
		depots: ['Magasins - U', 'Production - U', 'Produits finis - U', 'Rebus - U'],
		can_edit_checklists: true,
		can_create_checklists: true,
		can_edit_parametres: true,
	})),
}))

describe('réglages de la production', () => {
	it('affiche les réglages enregistrés au chargement', async () => {
		const ReglagesProductionPage = (await import('./ReglagesProductionPage.vue')).default
		const router = createRouter({ history: createMemoryHistory(), routes })
		await router.push('/reglages-production')
		const wrapper = mount(ReglagesProductionPage, { global: { plugins: [router] } })
		await flushPromises()
		expect(wrapper.find<HTMLSelectElement>('select[data-search-select]').element.value).toBe('Magasins - U')
		expect(wrapper.find<HTMLInputElement>('#param-tolerance').element.value).toBe('5')
		expect(wrapper.find<HTMLInputElement>('input[aria-label="Contrôle 1"]').element.value).toBe('Ligne dégagée')
		expect(wrapper.text()).not.toContain('Aucune checklist')
		wrapper.unmount()
	})
})
