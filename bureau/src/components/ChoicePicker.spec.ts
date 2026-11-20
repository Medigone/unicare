import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ChoicePicker from './ChoicePicker.vue'

type Choice = { name: string; label: string }
const open = async (found: Choice[], createLabel?: string) => {
	vi.useFakeTimers()
	const wrapper = mount(ChoicePicker, { props: { search: vi.fn(async () => found), inputId: 'client', createLabel }, attachTo: document.body })
	const input = wrapper.find('input')
	await input.setValue('ABC')
	await vi.advanceTimersByTimeAsync(250)
	await flushPromises()
	return { wrapper, input }
}

describe('choix d’un client, avec création', () => {
	afterEach(() => {
		vi.useRealTimers()
		document.body.innerHTML = ''
	})

	it('sans résultat : Entrée crée avec le texte tapé', async () => {
		const { wrapper, input } = await open([], 'Créer le client')
		expect(wrapper.text()).toContain('Aucun résultat.')
		expect(wrapper.find('[role="option"]').text()).toBe('Créer le client « ABC »')
		await input.trigger('keydown', { key: 'Enter' })
		expect(wrapper.emitted('create')).toEqual([['ABC']])
		expect(wrapper.emitted('pick')).toBeUndefined()
		wrapper.unmount()
	})

	it('avec résultats : la création suit, atteinte au clavier', async () => {
		const { wrapper, input } = await open([{ name: 'C1', label: 'ABC PHARM' }], 'Créer le client')
		const options = wrapper.findAll('[role="option"]')
		expect(options.map((option) => option.text())).toEqual(['ABC PHARM', 'Créer le client « ABC »'])
		await input.trigger('keydown', { key: 'Enter' })
		expect(wrapper.emitted('pick')).toEqual([[{ name: 'C1', label: 'ABC PHARM' }]])
		wrapper.unmount()

		const second = await open([{ name: 'C1', label: 'ABC PHARM' }], 'Créer le client')
		await second.input.trigger('keydown', { key: 'ArrowDown' })
		await second.input.trigger('keydown', { key: 'Enter' })
		expect(second.wrapper.emitted('create')).toEqual([['ABC']])
		second.wrapper.unmount()
	})

	it('sans droit de création : aucune option de création', async () => {
		const { wrapper, input } = await open([])
		expect(wrapper.findAll('[role="option"]')).toHaveLength(0)
		await input.trigger('keydown', { key: 'Enter' })
		expect(wrapper.emitted('create')).toBeUndefined()
		wrapper.unmount()
	})
})
