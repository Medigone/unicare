<script setup lang="ts">
import { conditionsFromQuery } from '@/lib/filters'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LucideArrowLeft from '~icons/lucide/arrow-left'
import LucideChevronLeft from '~icons/lucide/chevron-left'
import LucideChevronRight from '~icons/lucide/chevron-right'
import { closeRealtime, connectRealtime, isForeignChange, throttledReload, type RealtimeEvent } from '@shared/realtime'
import type { Crumb } from '@shared/shell'
import BureauShell from '@/components/BureauShell.vue'
import OrdreDrawer from '@/components/OrdreDrawer.vue'
import OrdreList from '@/components/OrdreList.vue'
import OrdreView from '@/components/OrdreView.vue'
import { DEFAULT_ORDRE_VIEW, ORDRE_VIEWS, type OrdreView as OrdreViewKey } from '@/lib/ordres'
import { useOrdres } from '@/lib/useOrdres'

const props = defineProps<{ id?: string }>()
const route = useRoute()
const router = useRouter()

// La vue, la page et l'aperçu restent dans l'adresse : un rechargement ou le retour d'une fiche ramène au même endroit.
function viewFromRoute() {
	const value = route.query.vue
	return ORDRE_VIEWS.some((view) => view.key === value) ? (value as OrdreViewKey) : undefined
}
function pageFromRoute() {
	const value = Number(route.query.page)
	return Number.isInteger(value) && value > 1 ? value - 1 : 0
}
const state = useOrdres({ view: viewFromRoute(), page: pageFromRoute() })
// Un lien de l'accueil arrive avec ses filtres dans l'adresse.
state.conditions.value = conditionsFromQuery(route.query.filtres)
function listQuery(extra: Record<string, string> = {}) {
	return {
		...(state.view.value === DEFAULT_ORDRE_VIEW ? {} : { vue: state.view.value }),
		...(state.page.value > 0 ? { page: String(state.page.value + 1) } : {}),
		...extra,
	}
}
const preview = computed(() => (typeof route.query.apercu === 'string' ? route.query.apercu : undefined))

function showPreview(name?: string) {
	return router.replace({ name: 'Ordres', query: listQuery(name ? { apercu: name } : {}) })
}
function openFiche(name: string) {
	router.push({ name: 'OrdreFiche', params: { id: name } })
}
function backToList() {
	if (props.id) state.reveal(props.id)
	router.push({ name: 'Ordres', query: listQuery(props.id ? { apercu: props.id } : {}) })
}
// Ordre supprimé : retour à la liste, sans lui.
function onDeleted() {
	router.push({ name: 'Ordres', query: listQuery() })
	state.load()
}
watch([state.view, state.page], () => {
	if (!props.id) router.replace({ name: 'Ordres', query: listQuery(preview.value ? { apercu: preview.value } : {}) })
})

// L'adresse commande aussi la vue : un lien y mène sans recharger la page. Une fiche garde la vue de la liste qu'elle a quittée.
watch([() => route.name, () => route.query.vue], () => {
	if (route.name === 'Ordres') state.view.value = viewFromRoute() ?? DEFAULT_ORDRE_VIEW
})

const drawer = ref<InstanceType<typeof OrdreDrawer> | null>(null)
const fiche = ref<InstanceType<typeof OrdreView> | null>(null)
const crumbs = computed<Crumb[]>(() => {
	if (!props.id) return [{ label: 'Ordres de production' }]
	const label = props.id
	return [{ label: 'Ordres de production', to: { name: 'Ordres' } }, { label }]
})

// Position dans la liste affichée, commune à l'aperçu et à la fiche.
const active = computed(() => props.id ?? preview.value)
const index = computed(() => state.names.value.indexOf(active.value ?? ''))
const position = computed(() => (index.value >= 0 ? `${index.value + 1} sur ${state.total.value}` : 'Hors de la vue'))
const noPrev = computed(() => index.value <= 0)
const noNext = computed(() => index.value < 0 || index.value >= state.names.value.length - 1)
async function go(offset: number) {
	const target = state.names.value[index.value + offset]
	if (!target) return
	// L'adresse d'abord : changer de page la réécrit, et doit y trouver le nouvel élément.
	if (props.id) await router.replace({ name: 'OrdreFiche', params: { id: target } })
	else await showPreview(target)
	state.reveal(target)
}

// Temps réel : ce qui change ailleurs (Desk, collègue) remonte sans recharger la page.
const reload = throttledReload(
	() => {
		state.load()
		fiche.value?.refresh()
		drawer.value?.refresh()
	},
	{ delayMs: 1000, minIntervalMs: 4000 },
)
onMounted(() => {
	connectRealtime<RealtimeEvent>(
		'unicare_bureau_update',
		(event) => {
			if (isForeignChange(event, window.user)) reload()
		},
		reload,
	)
})
onBeforeUnmount(closeRealtime)
</script>

<template>
	<BureauShell :crumbs="crumbs" active="ordres">
		<div class="bureau-work">
			<!-- Masquée et non retirée : la liste garde son défilement pendant qu'une fiche est ouverte. -->
			<OrdreList v-show="!id" :state="state" :selected="id ? undefined : preview" @pick="showPreview" @open="openFiche" @changed="state.load(); drawer?.refresh()">
				<template #drawer>
					<OrdreDrawer v-if="!id && preview" :id="preview" ref="drawer" :position="position" :no-prev="noPrev" :no-next="noNext" @prev="go(-1)" @next="go(1)" @close="showPreview()" @open="openFiche(preview!)" @changed="state.load()" />
				</template>
			</OrdreList>

			<template v-if="id">
				<div class="flex flex-none flex-wrap items-center justify-between gap-2">
					<button type="button" class="btn-ghost" @click="backToList">
						<LucideArrowLeft class="h-3.5 w-3.5" aria-hidden="true" />
						Ordres de production
					</button>
					<div class="flex items-center gap-1.5">
						<span class="text-xs text-ink-gray-6">{{ position }}</span>
						<button type="button" class="icon-btn" aria-label="Ordre précédent" :disabled="noPrev" @click="go(-1)"><LucideChevronLeft class="h-4 w-4" aria-hidden="true" /></button>
						<button type="button" class="icon-btn" aria-label="Ordre suivant" :disabled="noNext" @click="go(1)"><LucideChevronRight class="h-4 w-4" aria-hidden="true" /></button>
					</div>
				</div>
				<OrdreView :id="id" ref="fiche" @changed="state.load()" @deleted="onDeleted" />
			</template>
		</div>
	</BureauShell>
</template>
