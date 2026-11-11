<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucidePanelLeft from '~icons/lucide/panel-left'
import BrandMark from './BrandMark.vue'
import { useSidebarCollapse, type Crumb, type NavGroup, type NavModule } from '../shell'

/**
 * Coquille commune : barre du haut, rail des modules, menu des pages du module ouvert, et zone de contenu.
 * Sur téléphone, le rail devient la barre du bas et les pages du module une bande sous la barre du haut.
 */
const props = defineProps<{
	poste: string
	/** Les modules du rail, dans l'ordre. */
	modules: NavModule[]
	/** Le module ouvert : son nom en tête du second menu. */
	moduleLabel?: string
	/** Les pages du module ouvert ; aucune (Accueil) : pas de second menu. */
	groups: NavGroup[]
	crumbs: Crumb[]
	userName: string
	initials: string
	/** Clé de mémoire du repli du menu, propre à chaque application. */
	storageKey: string
}>()

const { collapsed, toggle } = useSidebarCollapse(props.storageKey)
const hasPanel = computed(() => props.groups.length > 0)
const accountOpen = ref(false)
const accountRoot = ref<HTMLElement | null>(null)
const lastCrumb = computed(() => props.crumbs.length - 1)

function closeAccount() {
	accountOpen.value = false
}
function onPointerDown(event: PointerEvent) {
	if (accountOpen.value && !accountRoot.value?.contains(event.target as Node)) closeAccount()
}
function onKeydown(event: KeyboardEvent) {
	if (event.key === 'Escape') closeAccount()
}
onMounted(() => {
	document.addEventListener('pointerdown', onPointerDown)
	document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
	document.removeEventListener('pointerdown', onPointerDown)
	document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
	<div class="app-shell" :data-collapsed="collapsed" :data-panel="hasPanel">
		<header class="app-topbar">
			<button v-if="hasPanel" type="button" class="app-icon-bare app-collapse" :aria-label="collapsed ? 'Ouvrir le menu du module' : 'Replier le menu du module'" :title="collapsed ? 'Ouvrir le menu du module' : 'Replier le menu du module'" :aria-expanded="!collapsed" @click="toggle">
				<LucidePanelLeft class="h-4 w-4" aria-hidden="true" />
			</button>
			<span title="Unicare"><BrandMark mark-only /></span>
			<slot name="poste"><span class="app-poste">{{ poste }}</span></slot>
			<nav class="app-crumbs" aria-label="Fil d'Ariane">
				<template v-for="(crumb, index) in crumbs" :key="index">
					<span class="app-crumb-sep" aria-hidden="true">/</span>
					<span v-if="index === lastCrumb || !crumb.to" :aria-current="index === lastCrumb ? 'page' : undefined" class="app-crumb-now">{{ crumb.label }}</span>
					<RouterLink v-else :to="crumb.to as string" class="app-crumb-link">{{ crumb.label }}</RouterLink>
				</template>
			</nav>
			<span class="flex-auto"></span>
			<slot name="search" />
			<slot name="status" />
			<div ref="accountRoot" class="relative flex-none">
				<button type="button" class="app-avatar" :aria-label="`Mon compte : ${userName}`" :title="userName" aria-haspopup="menu" :aria-expanded="accountOpen" @click="accountOpen = !accountOpen">{{ initials }}</button>
				<div v-if="accountOpen" class="app-menu app-menu-right" role="menu">
					<p class="app-menu-title">{{ userName }}</p>
					<slot name="account" :close="closeAccount" />
				</div>
			</div>
		</header>

		<nav class="app-rail" aria-label="Modules">
			<template v-for="module in modules" :key="module.id">
				<RouterLink v-if="module.to" :to="module.to as string" class="app-rail-item" :aria-current="module.active ? 'true' : undefined" :title="module.label">
					<span class="app-rail-icon"><component :is="module.icon" class="h-5 w-5" aria-hidden="true" /><span v-if="module.alert" class="app-rail-alert" aria-hidden="true"></span></span>
					<span class="app-rail-label">{{ module.label }}</span>
				</RouterLink>
				<a v-else :href="module.href" target="_blank" rel="noopener noreferrer" class="app-rail-item" :title="`${module.label} : s'ouvre sur le Desk`">
					<span class="app-rail-icon"><component :is="module.icon" class="h-5 w-5" aria-hidden="true" /></span>
					<span class="app-rail-label">{{ module.label }}</span>
				</a>
			</template>
		</nav>

		<nav v-if="hasPanel" class="app-sidebar" :aria-label="`Pages du module ${moduleLabel ?? ''}`">
			<p v-if="moduleLabel" class="app-module-title">{{ moduleLabel }}</p>
			<div v-for="group in groups" :key="group.title" class="app-nav-group">
				<p class="app-nav-title">{{ group.title }}</p>
				<template v-for="item in group.items" :key="item.id">
					<RouterLink v-if="item.to" :to="item.to as string" class="app-nav-item" :title="item.label" :aria-current="item.active ? 'page' : undefined">
						<component :is="item.icon" class="h-4 w-4 flex-none" aria-hidden="true" />
						<span class="app-nav-label">{{ item.label }}</span>
						<span v-if="item.count" class="app-nav-count" :class="item.alert && 'app-nav-count-alert'">{{ item.count }}</span>
					</RouterLink>
					<a v-else :href="item.href" target="_blank" rel="noopener noreferrer" class="app-nav-item" :title="`${item.label} : s'ouvre sur le Desk`">
						<component :is="item.icon" class="h-4 w-4 flex-none" aria-hidden="true" />
						<span class="app-nav-label">{{ item.label }}<span class="sr-only"> (s'ouvre sur le Desk, dans une nouvelle fenêtre)</span></span>
						<LucideArrowUpRight class="app-nav-out h-3.5 w-3.5" aria-hidden="true" />
					</a>
				</template>
			</div>
		</nav>

		<div class="app-main">
			<slot />
		</div>
	</div>
</template>
