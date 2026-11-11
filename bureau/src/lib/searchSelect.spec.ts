import { describe, expect, it } from 'vitest'
import { createApp, defineComponent, h, nextTick, ref, withDirectives } from 'vue'
import { filterChoices, vSearch } from './searchSelect'

const choices = [
	{ value: '', label: 'Choisir…', disabled: false },
	{ value: 'FU-000001', label: 'Shampoing Vrac', disabled: false },
	{ value: 'CO-000002', label: 'Étiquette Shampoing 250 Ml', disabled: false },
	{ value: 'CO-000001', label: 'Bouteille 250 Ml', disabled: false },
]

describe('listes déroulantes avec recherche', () => {
	it('filtre sans tenir compte des accents ni de la casse, mot par mot', () => {
		expect(filterChoices(choices, 'etiq').map((c) => c.value)).toEqual(['CO-000002'])
		expect(filterChoices(choices, '250 bouteille').map((c) => c.value)).toEqual(['CO-000001'])
		expect(filterChoices(choices, 'fu-0000').map((c) => c.value)).toEqual(['FU-000001'])
		expect(filterChoices(choices, '  ')).toHaveLength(4)
		expect(filterChoices(choices, 'zzz')).toEqual([])
	})

	it('habille le select, filtre en tapant et garde v-model', async () => {
		const value = ref('')
		const Demo = defineComponent({
			setup: () => () =>
				h('div', [
					h('label', { for: 'matiere' }, 'Matière'),
					withDirectives(
						h('select', { id: 'matiere', class: 'field-input', value: value.value, onChange: (event: Event) => (value.value = (event.target as HTMLSelectElement).value) }, choices.map((c) => h('option', { value: c.value }, c.label))),
						[[vSearch]],
					),
				]),
		})
		const root = document.createElement('div')
		document.body.append(root)
		const app = createApp(Demo)
		app.mount(root)
		await nextTick()
		const trigger = root.querySelector<HTMLButtonElement>('button.search-select')!
		expect(trigger.id).toBe('matiere')
		expect(trigger.textContent).toContain('Choisir…')
		trigger.click()
		const input = document.querySelector<HTMLInputElement>('.search-select-input')!
		input.value = 'bout'
		input.dispatchEvent(new Event('input'))
		expect(Array.from(document.querySelectorAll('.search-select-option')).map((li) => li.textContent)).toEqual(['Bouteille 250 Ml'])
		input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
		await nextTick()
		expect(value.value).toBe('CO-000001')
		expect(document.querySelector('.search-select-pop')).toBeNull()
		expect(trigger.textContent).toContain('Bouteille 250 Ml')
		app.unmount()
		root.remove()
	})
})
