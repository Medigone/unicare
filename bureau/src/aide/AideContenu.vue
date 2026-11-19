<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { lienArticle, sommaireUtile, type AideTitre } from '@/lib/aide'

/**
 * Le corps d'un article. Le HTML est assaini par le serveur à l'enregistrement (liste blanche bleach) : il s'affiche
 * tel quel. Un lien vers un autre article passe par `article` au lieu de recharger la page.
 */
const props = defineProps<{ html: string; sommaire?: AideTitre[]; ancre?: string; compact?: boolean }>()
const emit = defineEmits<{ article: [slug: string, ancre: string] }>()

const root = ref<HTMLElement | null>(null)

function allerA(ancre: string) {
	if (!ancre) return
	const cible = root.value?.querySelector(`[id="${CSS.escape(ancre)}"]`)
	cible?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
}

function onClick(event: MouseEvent) {
	const lien = (event.target as Element | null)?.closest('a')
	if (!lien || event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return
	const href = lien.getAttribute('href') || ''
	if (href.startsWith('#')) {
		event.preventDefault()
		allerA(href.slice(1))
		return
	}
	const article = lienArticle(href)
	if (article) {
		event.preventDefault()
		emit('article', article.slug, article.ancre)
	} else if (/^https?:/.test(href)) {
		lien.setAttribute('target', '_blank')
		lien.setAttribute('rel', 'noopener noreferrer')
	}
}

watch(
	() => [props.html, props.ancre] as const,
	async ([, ancre]) => {
		await nextTick()
		if (ancre) allerA(ancre)
	},
	{ immediate: true },
)
</script>

<template>
	<div class="aide-contenu" :class="compact && 'is-compact'">
		<nav v-if="sommaireUtile(sommaire)" class="aide-sommaire" aria-label="Sommaire de l'article">
			<span class="aide-sommaire-titre">Sur cette page</span>
			<a v-for="titre in sommaire" :key="titre.id" :href="`#${titre.id}`" @click.prevent="allerA(titre.id)">{{ titre.titre }}</a>
		</nav>
		<!-- eslint-disable-next-line vue/no-v-html -- HTML assaini par le serveur (unicare/aide/rendu.py) -->
		<div ref="root" class="aide-body" @click="onClick" v-html="html"></div>
	</div>
</template>
