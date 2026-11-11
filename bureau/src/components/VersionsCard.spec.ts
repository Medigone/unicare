import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { openVersion, type Versions } from '@/lib/versions'
import VersionsCard from './VersionsCard.vue'

const none: Versions = { origine: null, suivantes: [] }
const stubs = { RouterLink: { props: ['to'], template: '<a :data-to="to.params.id"><slot /></a>' }, StatusPill: true }
const card = (props: { versions: Versions; docstatus: number; canAmend: boolean }) => mount(VersionsCard, { props: { fiche: 'FactureAchatFiche', ...props }, global: { stubs } })

describe('versions des pièces', () => {
	it('trouve la version qui remplace une pièce annulée', () => {
		expect(openVersion(none)).toBeNull()
		expect(openVersion({ origine: null, suivantes: [{ name: 'F-1', docstatus: 2, status: 'Cancelled' }, { name: 'F-2', docstatus: 0, status: 'Draft' }] })?.name).toBe('F-2')
	})

	it('propose la nouvelle version sur une pièce annulée', async () => {
		const wrapper = card({ versions: none, docstatus: 2, canAmend: true })
		expect(wrapper.text()).toContain('Pièce annulée.')
		await wrapper.get('button').trigger('click')
		expect(wrapper.emitted('amend')).toHaveLength(1)
	})

	it('mène à la version existante au lieu d’en proposer une autre', () => {
		const wrapper = card({ versions: { origine: null, suivantes: [{ name: 'F-1', docstatus: 0, status: 'Draft' }] }, docstatus: 2, canAmend: false })
		expect(wrapper.find('button').exists()).toBe(false)
		expect(wrapper.text()).toContain('Remplacée par')
		expect(wrapper.get('a').attributes('data-to')).toBe('F-1')
	})

	it("rappelle la pièce d'origine et ne montre rien pour une pièce ordinaire", () => {
		expect(card({ versions: { origine: { name: 'F', docstatus: 2, status: 'Cancelled' }, suivantes: [] }, docstatus: 0, canAmend: false }).text()).toContain('Nouvelle version de')
		expect(card({ versions: none, docstatus: 1, canAmend: false }).text()).toBe('')
	})
})
