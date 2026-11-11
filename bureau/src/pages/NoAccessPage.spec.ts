import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '@/App.vue'
import { setPoste } from '@/lib/postes'
import { routes } from '@/router'
import HomePage from './HomePage.vue'

// Une page protégée par son document, comme le seront les pages métier.
const testRoutes = [{ path: '/essai-garde', name: 'EssaiGarde', component: HomePage, meta: { doctype: 'Ordre de Conditionnement' } }, ...routes]

async function open(path: string) {
	const router = createRouter({ history: createMemoryHistory(), routes: testRoutes })
	await router.push(path)
	await router.isReady()
	const wrapper = mount(App, { global: { plugins: [router] }, attachTo: document.body })
	await flushPromises()
	return { wrapper, router }
}

beforeEach(() => {
	window.user = 'magasin@example.com'
	window.user_fullname = 'Samia Benali'
	window.can_access = true
	vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ message: {} }), { status: 200, headers: { 'Content-Type': 'application/json' } })))
})

afterEach(() => {
	document.body.innerHTML = ''
	delete window.postes
	delete window.droits
	window.user = null
	window.user_fullname = null
	window.can_access = false
	setPoste('')
	localStorage.clear()
	vi.unstubAllGlobals()
})

describe('garde des pages et choix du poste', () => {
	it("dit qu'une page n'est pas accessible et garde son adresse", async () => {
		window.droits = { 'Ordre de Conditionnement': { read: false, create: false } }
		const { wrapper, router } = await open('/essai-garde?page=2')
		expect(wrapper.text()).toContain("Cette page n'est pas accessible")
		expect(router.currentRoute.value.fullPath).toBe('/essai-garde?page=2')
		wrapper.unmount()
	})

	it('ouvre la page quand le rôle lit le document', async () => {
		window.droits = { 'Ordre de Conditionnement': { read: true, create: false } }
		const { wrapper } = await open('/essai-garde')
		expect(wrapper.text()).not.toContain("Cette page n'est pas accessible")
		expect(wrapper.text()).toContain('Bonjour Samia')
		wrapper.unmount()
	})

	it("affiche le nom de l'application avec un seul poste", async () => {
		window.postes = [{ key: 'conditionnement', label: 'Conditionnement' }]
		const { wrapper } = await open('/')
		expect(wrapper.find('.app-poste').text()).toBe('Unicare')
		expect(wrapper.find('[aria-label="Changer de poste"]').exists()).toBe(false)
		wrapper.unmount()
	})

	it('propose le choix du poste quand le compte en a plusieurs', async () => {
		window.postes = [
			{ key: 'conditionnement', label: 'Conditionnement' },
			{ key: 'autre', label: 'Autre' },
		]
		const { wrapper } = await open('/')
		await wrapper.find('[aria-label="Changer de poste"]').trigger('click')
		const autre = wrapper.findAll('[role="menuitemradio"]').find((item) => item.text() === 'Autre')
		await autre!.trigger('click')
		await flushPromises()
		expect(localStorage.getItem('bureau-poste')).toBe('autre')
		wrapper.unmount()
	})

	it('renvoie une adresse inconnue vers l\'accueil', async () => {
		const { wrapper, router } = await open('/nulle-part')
		expect(router.currentRoute.value.name).toBe('Home')
		wrapper.unmount()
	})
})
