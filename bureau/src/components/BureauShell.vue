<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideLogOut from '~icons/lucide/log-out'
import LucideMoon from '~icons/lucide/moon'
import LucideSun from '~icons/lucide/sun'
import AppShell from '@shared/components/AppShell.vue'
import { realtimeConnected } from '@shared/realtime'
import type { Crumb, NavGroup, NavModule } from '@shared/shell'
import GotoPalette from './GotoPalette.vue'
import HeaderMenu from './HeaderMenu.vue'
import { logout } from '@/lib/api'
import { initials } from '@/lib/display'
import { activePoste, availablePostes, moduleOf, moduleTarget, navFor, pagesFor, setPoste } from '@/lib/postes'
import { useAppTheme } from '@/lib/theme'

/** Coquille du poste de bureau : la même barre et le même menu sur toutes ses pages. `active` : l'`id` de l'entrée du menu. */
const props = defineProps<{ crumbs: Crumb[]; active?: string }>()

const router = useRouter()
const userName = window.user_fullname || window.user || ''
const theme = useAppTheme()
const nextThemeLabel = computed(() => (theme.resolved.value === 'dark' ? 'Passer en thème clair' : 'Passer en thème sombre'))
function toggleTheme() {
	theme.setPreference(theme.resolved.value === 'dark' ? 'light' : 'dark')
}

// Un seul poste : la barre du haut porte le nom de l'application ; le choix du poste n'apparaît qu'à partir de deux.
const postes = availablePostes()
const currentPoste = computed(() => activePoste())
function choosePoste(key: string) {
	setPoste(key)
	router.push({ name: 'Home' })
}

// Les modules du poste dans le rail ; le module ouvert est celui de la page affichée, et ses pages forment le second menu.
const modules = computed(() => navFor(currentPoste.value.key))
const currentModule = computed(() => moduleOf(modules.value, props.active))
const navModules = computed<NavModule[]>(() =>
	modules.value.map((module) => ({ id: module.id, label: module.label, icon: module.icon, ...moduleTarget(module), active: module.id === currentModule.value?.id })),
)
const pages = computed(() => pagesFor(currentPoste.value.key))
// Le fil d'Ariane commence par le module : « Achats / Factures d'achat ».
const shellCrumbs = computed<Crumb[]>(() => (currentModule.value?.groups.length ? [{ label: currentModule.value.label }, ...props.crumbs] : props.crumbs))
const navGroups = computed<NavGroup[]>(() =>
	(currentModule.value?.groups ?? []).map((group) => ({
		title: group.title,
		items: group.items.map(({ doctype: _doctype, ...item }) => ({ ...item, active: props.active === item.id })),
	})),
)
</script>

<template>
	<AppShell :poste="postes.length > 1 ? currentPoste.label : 'Unicare'" :modules="navModules" :module-label="currentModule?.groups.length ? currentModule.label : undefined" :groups="navGroups" :crumbs="shellCrumbs" :user-name="userName" :initials="initials(userName)" storage-key="bureau-menu">
		<template v-if="postes.length > 1" #poste>
			<HeaderMenu :label="currentPoste.label" value="" aria-label="Changer de poste">
				<template #default="{ close }">
					<button v-for="poste in postes" :key="poste.key" type="button" class="app-menu-item" :class="poste.key === currentPoste.key && 'font-semibold'" role="menuitemradio" :aria-checked="poste.key === currentPoste.key" @click="close(); choosePoste(poste.key)">{{ poste.label }}</button>
				</template>
			</HeaderMenu>
		</template>
		<template #search><GotoPalette :pages="pages" /></template>
		<template #status>
			<span class="live-status" :data-live="realtimeConnected" :title="realtimeConnected ? 'Les changements faits ailleurs arrivent seuls' : 'Les changements faits ailleurs n\'arrivent plus seuls : actualisez la page'">
				<i aria-hidden="true"></i>
				<span>{{ realtimeConnected ? 'À jour' : 'Temps réel coupé' }}</span>
			</span>
		</template>
		<template #account="{ close }">
			<button type="button" class="app-menu-item" role="menuitem" @click="toggleTheme(); close()">
				<LucideSun v-if="theme.resolved.value === 'dark'" class="h-3.5 w-3.5" aria-hidden="true" />
				<LucideMoon v-else class="h-3.5 w-3.5" aria-hidden="true" />
				{{ nextThemeLabel }}
			</button>
			<a href="/app" class="app-menu-item" role="menuitem" target="_blank" rel="noopener noreferrer" @click="close()">
				<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />
				Ouvrir le Desk
			</a>
			<div class="app-menu-sep"></div>
			<button type="button" class="app-menu-item" role="menuitem" @click="logout">
				<LucideLogOut class="h-3.5 w-3.5" aria-hidden="true" />
				Se déconnecter
			</button>
		</template>
		<slot />
	</AppShell>
</template>
