<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LucideChevronLeft from '~icons/lucide/chevron-left'
import LucideChevronRight from '~icons/lucide/chevron-right'
import LucidePencil from '~icons/lucide/pencil'
import AideContenu from '@/aide/AideContenu.vue'
import BureauShell from '@/components/BureauShell.vue'
import { getAideArticle } from '@/lib/api'
import { dureeLabel, type AideArticle } from '@/lib/aide'
import { formatDay } from '@/lib/display'

/** Un article du centre d'aide, en pleine page : sommaire, fil d'Ariane, articles voisins. */
const props = defineProps<{ slug: string }>()
const route = useRoute()
const router = useRouter()

const article = ref<AideArticle | null>(null)
const error = ref('')
const ancre = computed(() => route.hash.replace(/^#/, ''))

async function load() {
	error.value = ''
	try {
		article.value = await getAideArticle(props.slug)
		document.title = `${article.value.titre} · Aide`
		if (!ancre.value) window.scrollTo({ top: 0 })
	} catch (e) {
		article.value = null
		error.value = (e as Error).message
	}
}
watch(() => props.slug, load, { immediate: true })

function suivre(slug: string, cible: string) {
	router.push({ name: 'AideArticle', params: { slug }, hash: cible ? `#${cible}` : '' })
}

const crumbs = computed(() => [
	{ label: 'Aide', to: { name: 'Aide' } },
	...(article.value?.categorie ? [{ label: article.value.categorie.titre, to: { name: 'AideCategorie', params: { slug: article.value.categorie.slug } } }] : []),
	{ label: article.value?.titre ?? 'Article' },
])
</script>

<template>
	<BureauShell :crumbs="crumbs" active="aide">
		<div class="bureau-work tdb aide-centre">
			<p v-if="error" role="alert" class="card p-4 text-tone-red">
				{{ error }}
				<RouterLink :to="{ name: 'Aide' }" class="ml-1 font-semibold underline">Retour au centre d'aide</RouterLink>
			</p>
			<p v-else-if="!article" class="card p-4 text-ink-gray-6">Chargement de l'article…</p>
			<article v-else class="card aide-page">
				<header class="flex flex-wrap items-start gap-3">
					<div class="min-w-0 flex-[1_1_20rem]">
						<h1 class="text-[22px] font-semibold leading-tight text-ink-gray-9">{{ article.titre }}</h1>
						<p class="mt-1 text-xs text-ink-gray-6">
							<span v-if="article.statut === 'Brouillon'" class="badge tone-amber mr-1.5">Brouillon</span>
							{{ [dureeLabel(article.duree_lecture), article.date_revision && `revu le ${formatDay(article.date_revision)}`].filter(Boolean).join(' · ') }}
						</p>
					</div>
					<RouterLink v-if="article.peut_editer" :to="{ name: 'ReglagesAide', params: { slug: article.slug } }" class="btn-secondary"><LucidePencil class="h-3.5 w-3.5" aria-hidden="true" />Modifier</RouterLink>
				</header>
				<AideContenu :html="article.html" :sommaire="article.sommaire" :ancre="ancre" @article="suivre" />
				<nav v-if="article.precedent || article.suivant" class="aide-voisins" aria-label="Articles voisins">
					<RouterLink v-if="article.precedent" :to="{ name: 'AideArticle', params: { slug: article.precedent.slug } }" class="aide-voisin">
						<LucideChevronLeft class="h-4 w-4 flex-none" aria-hidden="true" /><span><small>Précédent</small>{{ article.precedent.titre }}</span>
					</RouterLink>
					<RouterLink v-if="article.suivant" :to="{ name: 'AideArticle', params: { slug: article.suivant.slug } }" class="aide-voisin is-next">
						<span><small>Suivant</small>{{ article.suivant.titre }}</span><LucideChevronRight class="h-4 w-4 flex-none" aria-hidden="true" />
					</RouterLink>
				</nav>
			</article>
		</div>
	</BureauShell>
</template>
