<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import LucideArrowLeft from '~icons/lucide/arrow-left'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronLeft from '~icons/lucide/chevron-left'
import LucideChevronRight from '~icons/lucide/chevron-right'
import LucideSearch from '~icons/lucide/search'
import LucideX from '~icons/lucide/x'
import AideContenu from './AideContenu.vue'
import { getAideAccueil, getAideArticle, rechercherAide } from '@/lib/api'
import { aidePanneau, dureeLabel, ecranCourant, type AideAccueil, type AideArticle, type AideCarte, type AideRecherche } from '@/lib/aide'

/** Le panneau « ? » : l'aide de l'écran ouvert d'abord, puis la recherche et toutes les rubriques, et la lecture sur place. */
const router = useRouter()
const root = ref<HTMLElement | null>(null)
const champ = ref<HTMLInputElement | null>(null)

const accueil = ref<AideAccueil | null>(null)
const article = ref<AideArticle | null>(null)
const ancre = ref('')
const q = ref('')
const resultats = ref<AideRecherche | null>(null)
const error = ref('')
const chargement = ref(false)
const ouvertes = ref<string[]>([])

const slug = computed(() => aidePanneau.value || '')
const enLecture = computed(() => Boolean(slug.value))

async function chargerAccueil() {
	try {
		accueil.value = await getAideAccueil(ecranCourant.value)
		error.value = ''
	} catch (e) {
		error.value = (e as Error).message
	}
}

async function chargerArticle(cible: string) {
	chargement.value = true
	try {
		article.value = await getAideArticle(cible)
		error.value = ''
		await nextTick()
		root.value?.querySelector('.aide-panneau-body')?.scrollTo({ top: 0 })
	} catch (e) {
		error.value = (e as Error).message
		article.value = null
	} finally {
		chargement.value = false
	}
}

watch(
	slug,
	(cible) => {
		if (cible) chargerArticle(cible)
		else article.value = null
	},
	{ immediate: true },
)
watch(ecranCourant, () => {
	if (!enLecture.value) chargerAccueil()
})

let minuteur: ReturnType<typeof setTimeout> | null = null
let demande = 0
watch(q, (valeur) => {
	if (minuteur) clearTimeout(minuteur)
	const texte = valeur.trim()
	if (texte.length < 2) {
		resultats.value = null
		return
	}
	minuteur = setTimeout(async () => {
		const numero = ++demande
		try {
			const reponse = await rechercherAide(texte, ecranCourant.value)
			if (numero === demande) resultats.value = reponse
		} catch (e) {
			if (numero === demande) error.value = (e as Error).message
		}
	}, 200)
})

function lire(carte: Pick<AideCarte, 'slug'>, cible = '') {
	ancre.value = cible
	aidePanneau.value = carte.slug
}
function retour() {
	aidePanneau.value = ''
	nextTick(() => champ.value?.focus())
}
function fermer() {
	aidePanneau.value = null
}
function centre() {
	const cible = slug.value
	fermer()
	router.push(cible ? { name: 'AideArticle', params: { slug: cible } } : { name: 'Aide', query: q.value.trim() ? { q: q.value.trim() } : {} })
}
function basculer(cle: string) {
	ouvertes.value = ouvertes.value.includes(cle) ? ouvertes.value.filter((c) => c !== cle) : [...ouvertes.value, cle]
}

const vide = computed(() => resultats.value && !resultats.value.page.length && !resultats.value.autres.length)

// Échap ferme ; « / » va à la recherche ; un clic hors du panneau le ferme (le bouton « ? » le gère lui-même).
function saisie(target: EventTarget | null) {
	return target instanceof Element && Boolean(target.closest('input, textarea, select, [contenteditable]'))
}
function onKeydown(event: KeyboardEvent) {
	if (document.querySelector('.dialog-scrim')) return
	if (event.key === 'Escape') {
		event.preventDefault()
		fermer()
	} else if (event.key === '/' && !saisie(event.target) && !event.ctrlKey && !event.metaKey && !event.altKey) {
		event.preventDefault()
		if (enLecture.value) retour()
		else champ.value?.focus()
	}
}
function onPointerDown(event: PointerEvent) {
	const target = event.target
	if (event.button !== 0 || !(target instanceof Element) || root.value?.contains(target)) return
	if (!target.closest('.aide-bouton, .dialog-scrim, .app-menu')) fermer()
}

const retourFocus = document.activeElement as HTMLElement | null
onMounted(() => {
	document.addEventListener('keydown', onKeydown)
	document.addEventListener('pointerdown', onPointerDown)
	chargerAccueil()
	if (!enLecture.value) nextTick(() => champ.value?.focus())
	else nextTick(() => root.value?.focus())
})
onBeforeUnmount(() => {
	document.removeEventListener('keydown', onKeydown)
	document.removeEventListener('pointerdown', onPointerDown)
	if (minuteur) clearTimeout(minuteur)
	if (retourFocus?.isConnected) retourFocus.focus()
})
</script>

<template>
	<aside ref="root" class="aide-panneau" role="dialog" aria-modal="false" aria-labelledby="aide-panneau-titre" tabindex="-1">
		<div class="bureau-drawer-head">
			<button v-if="enLecture" type="button" class="icon-btn" aria-label="Revenir à l'aide de la page" @click="retour"><LucideArrowLeft class="h-4 w-4" aria-hidden="true" /></button>
			<h2 id="aide-panneau-titre" class="flex-auto truncate text-base font-semibold">{{ enLecture ? article?.categorie?.titre || 'Aide' : 'Aide' }}</h2>
			<button type="button" class="btn-ghost" @click="centre">
				{{ enLecture ? 'Pleine page' : "Centre d'aide" }}
				<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />
			</button>
			<button type="button" class="icon-btn" aria-label="Fermer l'aide" @click="fermer"><LucideX class="h-4 w-4" aria-hidden="true" /></button>
		</div>

		<div class="aide-panneau-body">
			<p v-if="error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ error }}</p>

			<!-- Lecture d'un article -->
			<template v-if="enLecture">
				<p v-if="chargement && !article" class="py-8 text-center text-ink-gray-6">Chargement de l'article…</p>
				<article v-else-if="article" class="flex flex-col gap-3" :aria-busy="chargement">
					<header>
						<h3 class="text-lg font-semibold leading-snug">{{ article.titre }}</h3>
						<p class="mt-0.5 text-xs text-ink-gray-6">
							<span v-if="article.statut === 'Brouillon'" class="badge tone-amber mr-1.5">Brouillon</span>{{ dureeLabel(article.duree_lecture) }}
						</p>
					</header>
					<AideContenu :html="article.html" :sommaire="article.sommaire" :ancre="ancre" compact @article="(cible, a) => lire({ slug: cible }, a)" />
					<nav v-if="article.precedent || article.suivant" class="aide-voisins" aria-label="Articles voisins">
						<button v-if="article.precedent" type="button" class="aide-voisin" @click="lire(article.precedent)">
							<LucideChevronLeft class="h-4 w-4 flex-none" aria-hidden="true" /><span><small>Précédent</small>{{ article.precedent.titre }}</span>
						</button>
						<button v-if="article.suivant" type="button" class="aide-voisin is-next" @click="lire(article.suivant)">
							<span><small>Suivant</small>{{ article.suivant.titre }}</span><LucideChevronRight class="h-4 w-4 flex-none" aria-hidden="true" />
						</button>
					</nav>
				</article>
			</template>

			<!-- Accueil du panneau -->
			<template v-else>
				<label class="bureau-search aide-recherche">
					<LucideSearch class="h-3.5 w-3.5" aria-hidden="true" />
					<input ref="champ" v-model="q" class="field-input" type="search" aria-label="Chercher dans l'aide" placeholder="Chercher dans l'aide…" />
				</label>

				<template v-if="resultats">
					<p v-if="vide" class="py-4 text-center text-sm text-ink-gray-6">Aucun article ne parle de « {{ q.trim() }} ».</p>
					<section v-if="resultats.page.length" class="aide-groupe" aria-labelledby="aide-r-page">
						<h3 id="aide-r-page" class="aide-groupe-titre">Sur cette page</h3>
						<button v-for="carte in resultats.page" :key="carte.slug" type="button" class="aide-lien" @click="lire(carte)">
							<span class="font-medium">{{ carte.titre }}</span><span v-if="carte.resume" class="aide-lien-resume">{{ carte.resume }}</span>
						</button>
					</section>
					<section v-if="resultats.autres.length" class="aide-groupe" aria-labelledby="aide-r-autres">
						<h3 id="aide-r-autres" class="aide-groupe-titre">{{ resultats.page.length ? 'Ailleurs dans le bureau' : 'Résultats' }}</h3>
						<button v-for="carte in resultats.autres" :key="carte.slug" type="button" class="aide-lien" @click="lire(carte)">
							<span class="font-medium">{{ carte.titre }}</span><span v-if="carte.resume" class="aide-lien-resume">{{ carte.resume }}</span>
						</button>
					</section>
				</template>

				<template v-else-if="accueil">
					<section v-if="accueil.sur_cette_page.length" class="aide-groupe" aria-labelledby="aide-page">
						<h3 id="aide-page" class="aide-groupe-titre">Sur cette page</h3>
						<button v-for="carte in accueil.sur_cette_page" :key="carte.slug" type="button" class="aide-lien" @click="lire(carte)">
							<span class="font-medium">{{ carte.titre }}</span><span v-if="carte.resume" class="aide-lien-resume">{{ carte.resume }}</span>
						</button>
					</section>
					<section class="aide-groupe" aria-labelledby="aide-rubriques">
						<h3 id="aide-rubriques" class="aide-groupe-titre">Toutes les rubriques</h3>
						<div v-for="cat in accueil.categories" :key="cat.slug" class="aide-rubrique">
							<button type="button" class="aide-rubrique-tete" :aria-expanded="ouvertes.includes(cat.slug)" @click="basculer(cat.slug)">
								<LucideChevronRight class="aide-chevron h-3.5 w-3.5 flex-none" aria-hidden="true" />
								<span class="flex-auto">{{ cat.titre }}</span>
								<span class="text-xs tabular-nums text-ink-gray-6">{{ cat.articles.length }}</span>
							</button>
							<div v-if="ouvertes.includes(cat.slug)" class="flex flex-col">
								<button v-for="carte in cat.articles" :key="carte.slug" type="button" class="aide-lien is-sub" @click="lire(carte)">{{ carte.titre }}</button>
							</div>
						</div>
					</section>
				</template>
				<p v-else-if="!error" class="py-8 text-center text-ink-gray-6">Chargement de l'aide…</p>
				<p class="mt-auto text-xs text-ink-gray-6">Astuce : <kbd>?</kbd> ouvre l'aide de n'importe quelle page, <kbd>/</kbd> va à la recherche.</p>
			</template>
		</div>
	</aside>
</template>
