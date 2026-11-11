/**
 * Listes déroulantes avec recherche : la directive `v-search` habille un `<select>` d'un bouton et d'une liste qui se
 * filtre à chaque frappe (sans tenir compte des accents ni de la casse).
 *
 * Le `<select>` reste la source de vérité, masqué : `v-model` et `@change` marchent comme avant, les options se
 * relisent à chaque ouverture. Le bouton reprend son `id` (les `<label for>` le visent), ses classes et son état.
 */
import type { Directive } from 'vue'
import { normalize } from './goto'

export interface SelectChoice {
	value: string
	label: string
	disabled: boolean
}

/** Les choix dont le libellé contient chaque mot tapé, dans l'ordre d'origine. */
export function filterChoices(choices: SelectChoice[], query: string) {
	const words = normalize(query).split(/\s+/).filter(Boolean)
	if (!words.length) return choices
	return choices.filter((choice) => {
		const label = normalize(`${choice.label} ${choice.value}`)
		return words.every((word) => label.includes(word))
	})
}

interface State {
	trigger: HTMLButtonElement
	text: HTMLSpanElement
	popover: HTMLDivElement | null
	close: () => void
}

const states = new WeakMap<HTMLSelectElement, State>()
let counter = 0

const CHEVRON = '<svg class="search-select-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>'

function choicesOf(select: HTMLSelectElement): SelectChoice[] {
	return Array.from(select.options).map((option) => ({ value: option.value, label: option.text.trim(), disabled: option.disabled }))
}

function sync(select: HTMLSelectElement, state: State) {
	const option = select.selectedOptions[0]
	const label = option?.text.trim() ?? ''
	state.text.textContent = label || ' '
	state.text.classList.toggle('search-select-placeholder', !option || option.value === '')
	state.trigger.disabled = select.disabled
	state.trigger.className = `${select.className} search-select`
	state.trigger.title = label
	for (const name of ['aria-label', 'aria-invalid', 'aria-describedby']) {
		const value = select.getAttribute(name)
		if (value === null) state.trigger.removeAttribute(name)
		else state.trigger.setAttribute(name, value)
	}
}

function pick(select: HTMLSelectElement, state: State, value: string) {
	state.close()
	state.trigger.focus()
	if (select.value === value) return
	select.value = value
	select.dispatchEvent(new Event('input', { bubbles: true }))
	select.dispatchEvent(new Event('change', { bubbles: true }))
	sync(select, state)
}

function open(select: HTMLSelectElement, state: State, initial = '') {
	if (state.popover || select.disabled) return
	const id = `search-select-${++counter}`
	const popover = document.createElement('div')
	popover.className = 'search-select-pop'
	const input = document.createElement('input')
	input.className = 'search-select-input'
	input.type = 'text'
	input.placeholder = 'Rechercher…'
	input.autocomplete = 'off'
	input.setAttribute('role', 'combobox')
	input.setAttribute('aria-expanded', 'true')
	input.setAttribute('aria-controls', `${id}-list`)
	input.setAttribute('aria-label', `Rechercher : ${state.trigger.getAttribute('aria-label') || select.labels?.[0]?.textContent?.trim() || 'choix'}`)
	const list = document.createElement('ul')
	list.className = 'search-select-list'
	list.id = `${id}-list`
	list.setAttribute('role', 'listbox')
	popover.append(input, list)
	document.body.append(popover)
	state.popover = popover
	state.trigger.setAttribute('aria-expanded', 'true')

	const all = choicesOf(select)
	let shown: SelectChoice[] = all
	let cursor = 0

	function render() {
		shown = filterChoices(all, input.value)
		list.replaceChildren()
		if (!shown.length) {
			const empty = document.createElement('li')
			empty.className = 'search-select-empty'
			empty.textContent = 'Aucun résultat'
			list.append(empty)
			input.removeAttribute('aria-activedescendant')
			return
		}
		shown.forEach((choice, index) => {
			const item = document.createElement('li')
			item.id = `${id}-${index}`
			item.className = 'search-select-option'
			item.setAttribute('role', 'option')
			item.setAttribute('aria-selected', String(index === cursor))
			if (choice.value === select.value) item.dataset.current = 'true'
			if (choice.disabled) item.setAttribute('aria-disabled', 'true')
			if (choice.value === '') item.classList.add('search-select-placeholder')
			item.textContent = choice.label || ' '
			item.addEventListener('mousedown', (event) => event.preventDefault())
			item.addEventListener('click', () => !choice.disabled && pick(select, state, choice.value))
			item.addEventListener('pointerenter', () => move(index - cursor))
			list.append(item)
		})
		input.setAttribute('aria-activedescendant', `${id}-${cursor}`)
		list.children[cursor]?.scrollIntoView({ block: 'nearest' })
	}
	function move(offset: number) {
		if (!shown.length) return
		cursor = (cursor + offset + shown.length) % shown.length
		Array.from(list.children).forEach((item, index) => item.setAttribute('aria-selected', String(index === cursor)))
		input.setAttribute('aria-activedescendant', `${id}-${cursor}`)
		list.children[cursor]?.scrollIntoView({ block: 'nearest' })
	}
	function place() {
		const rect = state.trigger.getBoundingClientRect()
		const below = window.innerHeight - rect.bottom
		popover.style.minWidth = `${Math.max(rect.width, 200)}px`
		popover.style.left = `${Math.min(rect.left, window.innerWidth - Math.max(rect.width, 200) - 8)}px`
		if (below < 300 && rect.top > below) {
			popover.style.top = ''
			popover.style.bottom = `${window.innerHeight - rect.top + 4}px`
		} else {
			popover.style.bottom = ''
			popover.style.top = `${rect.bottom + 4}px`
		}
	}

	input.value = initial
	cursor = Math.max(0, all.findIndex((choice) => choice.value === select.value))
	if (initial) cursor = 0
	render()
	place()
	input.focus()

	input.addEventListener('input', () => {
		cursor = 0
		render()
	})
	input.addEventListener('keydown', (event) => {
		// Échap ferme la liste, pas la fenêtre qui la contient.
		event.stopPropagation()
		if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
			event.preventDefault()
			move(event.key === 'ArrowDown' ? 1 : -1)
		} else if (event.key === 'Enter') {
			event.preventDefault()
			const choice = shown[cursor]
			if (choice && !choice.disabled) pick(select, state, choice.value)
		} else if (event.key === 'Escape') {
			event.preventDefault()
			state.close()
			state.trigger.focus()
		} else if (event.key === 'Tab') {
			state.close()
			state.trigger.focus()
		}
	})
	const onPointer = (event: PointerEvent) => {
		const target = event.target as Node
		if (!popover.contains(target) && !state.trigger.contains(target)) state.close()
	}
	const onScroll = (event: Event) => {
		if (!popover.contains(event.target as Node)) state.close()
	}
	document.addEventListener('pointerdown', onPointer, true)
	window.addEventListener('scroll', onScroll, true)
	window.addEventListener('resize', state.close)
	state.close = () => {
		document.removeEventListener('pointerdown', onPointer, true)
		window.removeEventListener('scroll', onScroll, true)
		window.removeEventListener('resize', state.close)
		popover.remove()
		state.popover = null
		state.trigger.setAttribute('aria-expanded', 'false')
		state.close = () => {}
	}
}

export const vSearch: Directive<HTMLSelectElement> = {
	mounted(select) {
		const trigger = document.createElement('button')
		trigger.type = 'button'
		trigger.setAttribute('aria-haspopup', 'listbox')
		trigger.setAttribute('aria-expanded', 'false')
		// Les `<label for>` visent désormais le bouton : le `<select>` masqué n'est plus focalisable.
		if (select.id) {
			trigger.id = select.id
			select.removeAttribute('id')
		}
		const text = document.createElement('span')
		text.className = 'search-select-value'
		trigger.append(text)
		trigger.insertAdjacentHTML('beforeend', CHEVRON)
		select.after(trigger)
		select.style.display = 'none'
		select.dataset.searchSelect = 'true'
		const state: State = { trigger, text, popover: null, close: () => {} }
		states.set(select, state)
		trigger.addEventListener('click', () => (state.popover ? state.close() : open(select, state)))
		trigger.addEventListener('keydown', (event) => {
			if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
				event.preventDefault()
				open(select, state)
			} else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey && event.key !== ' ') {
				event.preventDefault()
				open(select, state, event.key)
			}
		})
		sync(select, state)
	},
	updated(select) {
		const state = states.get(select)
		if (state) sync(select, state)
	},
	beforeUnmount(select) {
		const state = states.get(select)
		if (!state) return
		state.close()
		state.trigger.remove()
		states.delete(select)
	},
}
