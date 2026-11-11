import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { vSearch } from './lib/searchSelect'
import './index.css'

/**
 * En production, la page serveur pose le boot dans `window` (jinjaBootData). Sous `yarn dev`, on le demande au
 * serveur (mode développeur seulement) pour avoir le même utilisateur, les mêmes droits et le jeton CSRF.
 */
async function loadDevBoot() {
	if (!import.meta.env.DEV) return
	try {
		const response = await fetch('/api/method/unicare.www.bureau.get_context_for_dev', { credentials: 'include' })
		const boot = (await response.json()).message
		if (boot) Object.assign(window, boot)
	} catch {
		// Serveur injoignable : l'application s'ouvre sans session et propose la connexion.
	}
}

loadDevBoot().then(() => createApp(App).use(router).directive('search', vSearch).mount('#app'))
