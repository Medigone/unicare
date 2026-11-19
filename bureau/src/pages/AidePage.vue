<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LucideBookOpen from '~icons/lucide/book-open'
import LucideChevronRight from '~icons/lucide/chevron-right'
import LucideCircleAlert from '~icons/lucide/circle-alert'
import LucideCircleHelp from '~icons/lucide/circle-help'
import LucideFactory from '~icons/lucide/factory'
import LucideGauge from '~icons/lucide/gauge'
import LucideLandmark from '~icons/lucide/landmark'
import LucideList from '~icons/lucide/list'
import LucidePackage from '~icons/lucide/package'
import LucidePencil from '~icons/lucide/pencil'
import LucideSearch from '~icons/lucide/search'
import LucideSettings from '~icons/lucide/settings'
import LucideShoppingCart from '~icons/lucide/shopping-cart'
import LucideTag from '~icons/lucide/tag'
import LucideTruck from '~icons/lucide/truck'
import LucideUsers from '~icons/lucide/users'
import LucideX from '~icons/lucide/x'
import BureauShell from '@/components/BureauShell.vue'
import { getAideAccueil, getAideCategorie, rechercherAide } from '@/lib/api'
import { aidePanneau, dureeLabel, ouvrirAide, rangerRubriques, SUGGESTIONS, surligner, type AideAccueil, type AideCategorie, type AideRecherche } from '@/lib/aide'

/** Le centre d'aide : les rubriques (`/aide`), une rubrique (`/aide/c/:slug`), la recherche (`?q=`). */
const props = defineProps<{ slug?: string }>()
const route = useRoute()
const router = useRouter()

const ICONES: Record<string, Component> = {
	'shopping-cart': LucideShoppingCart,
	truck: LucideTruck,
	package: LucidePackage,
	factory: LucideFactory,
	tag: LucideTag,
	list: LucideList,
	gauge: LucideGauge,
	landmark: LucideLandmark,
	users: LucideUsers,
	settings: LucideSettings,
}
/** Les réglages : trois articles par carte, le reste derrière « Les n articles ». */
const APERCU_REGLAGES = 3

const accueil = ref<AideAccueil | null>(null)
const categorie = ref<AideCategorie | null>(null)
const resultats = ref<AideRecherche | null>(null)
const error = ref('')
const q = ref(typeof route.query.q === 'string' ? route.query.q : '')
const filtre = ref('')
const champ = ref<HTMLInputElement | null>(null)

async function load() {
	error.value = ''
	try {
		if (props.slug) categorie.value = await getAideCategorie(props.slug)
		else categorie.value = null
		// l'accueil sert aussi à nommer la rubrique des résultats, et au bouton « Modifier l'aide »
		accueil.value = accueil.value ?? (await getAideAccueil())
	} catch (e) {
		error.value = (e as Error).message
	}
}

let minuteur: ReturnType<typeof setTimeout> | null = null
let demande = 0
async function chercher(texte: string) {
	filtre.value = ''
	if (texte.trim().length < 2) {
		resultats.value = null
		return
	}
	const numero = ++demande
	try {
		const reponse = await rechercherAide(texte.trim())
		if (numero === demande) resultats.value = reponse
	} catch (e) {
		if (numero === demande) error.value = (e as Error).message
	}
}
watch(q, (texte) => {
	if (minuteur) clearTimeout(minuteur)
	minuteur = setTimeout(() => {
		router.replace({ query: texte.trim() ? { q: texte.trim() } : {} })
		chercher(texte)
	}, 200)
})
watch(() => props.slug, load)
// « / » va à la recherche, sauf pendant une saisie, sous une fenêtre ou quand le panneau d'aide a la main
function onKeydown(event: KeyboardEvent) {
	if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey || aidePanneau.value !== null || !champ.value) return
	const cible = event.target as HTMLElement | null
	if (cible?.closest('input, textarea, select, [contenteditable]') || document.querySelector('.dialog-scrim')) return
	event.preventDefault()
	champ.value.focus()
}
onMounted(() => {
	load()
	if (q.value) chercher(q.value)
	document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
	document.removeEventListener('keydown', onKeydown)
	if (minuteur) clearTimeout(minuteur)
})

function suggerer(mot: string) {
	q.value = mot
	champ.value?.focus()
}
function effacer() {
	q.value = ''
	champ.value?.focus()
}

const rubriques = computed(() => rangerRubriques(accueil.value?.categories ?? []))
const nomRubrique = (slug: string) => accueil.value?.categories.find((c) => c.slug === slug)?.titre ?? ''
const total = computed(() => accueil.value?.categories.reduce((n, c) => n + c.articles.length, 0) ?? 0)
const demarrage = computed(() => accueil.value?.categories.find((c) => c.slug === 'reglages')?.articles.find((a) => a.slug.endsWith('-vue-d-ensemble')) ?? null)

const trouves = computed(() => (resultats.value ? [...resultats.value.page, ...resultats.value.autres] : []))
const filtres = computed(() => {
	const compte = new Map<string, number>()
	for (const carte of trouves.value) compte.set(carte.categorie, (compte.get(carte.categorie) ?? 0) + 1)
	return [...compte].map(([slug, n]) => ({ slug, n, titre: nomRubrique(slug) }))
})
const affiches = computed(() => (filtre.value ? trouves.value.filter((c) => c.categorie === filtre.value) : trouves.value))
const meilleur = computed(() => affiches.value[0] ?? null)
const suivants = computed(() => affiches.value.slice(1))

const crumbs = computed(() => (categorie.value ? [{ label: 'Aide', to: { name: 'Aide' } }, { label: categorie.value.titre }] : [{ label: 'Aide' }]))
</script>

<template>
	<BureauShell :crumbs="crumbs" active="aide">
		<div class="bureau-work tdb aide-centre">
			<div class="flex flex-wrap items-start justify-between gap-3">
				<div class="min-w-0 flex-[1_1_24rem]">
					<h1 class="text-[22px] font-semibold leading-tight text-ink-gray-9">{{ categorie ? categorie.titre : "Centre d'aide" }}</h1>
					<p class="mt-0.5 text-sm text-ink-gray-6">
						{{ categorie ? categorie.description : `Comment faire chaque tâche du bureau, pas à pas : ${total} articles en ${accueil?.categories.length ?? 0} rubriques.` }}
					</p>
				</div>
				<RouterLink v-if="accueil?.peut_editer" :to="{ name: 'ReglagesAide' }" class="btn-secondary"><LucidePencil class="h-3.5 w-3.5" aria-hidden="true" />Modifier l'aide</RouterLink>
			</div>

			<div v-if="!categorie" class="aide-recherche-bloc">
				<label class="aide-recherche-grande">
					<LucideSearch class="h-[18px] w-[18px] flex-none text-ink-gray-6" aria-hidden="true" />
					<input ref="champ" v-model="q" type="search" aria-label="Chercher dans l'aide" placeholder="Que voulez-vous faire ? Ex. : facturer, inventaire, mot de passe…" />
					<button v-if="q" type="button" class="icon-btn" aria-label="Effacer la recherche" @click="effacer"><LucideX class="h-4 w-4" aria-hidden="true" /></button>
					<kbd v-else aria-hidden="true">/</kbd>
				</label>
				<div v-if="!resultats" class="flex flex-wrap items-center gap-2">
					<span class="text-[13px] text-ink-gray-6">Souvent cherché :</span>
					<button v-for="mot in SUGGESTIONS" :key="mot" type="button" class="aide-puce" @click="suggerer(mot)">{{ mot }}</button>
				</div>
			</div>

			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>

			<!-- Recherche -->
			<template v-if="!categorie && resultats">
				<div class="flex flex-wrap items-center gap-2" aria-live="polite">
					<p class="mr-2 text-sm text-ink-gray-7">
						<template v-if="trouves.length"><strong class="font-semibold text-ink-gray-9">{{ trouves.length }} article{{ trouves.length > 1 ? 's' : '' }}</strong> pour « {{ q.trim() }} »</template>
						<template v-else>Aucun article ne parle de « {{ q.trim() }} ».</template>
					</p>
					<template v-if="filtres.length > 1">
						<button type="button" class="aide-puce" :class="{ 'is-on': !filtre }" :aria-pressed="!filtre" @click="filtre = ''">Toutes les rubriques</button>
						<button v-for="f in filtres" :key="f.slug" type="button" class="aide-puce" :class="{ 'is-on': filtre === f.slug }" :aria-pressed="filtre === f.slug" @click="filtre = f.slug">{{ f.titre }} · {{ f.n }}</button>
					</template>
				</div>

				<section v-if="meilleur" class="card aide-meilleur" aria-labelledby="aide-meilleur">
					<p class="aide-surtitre">Meilleur résultat · {{ nomRubrique(meilleur.categorie) }}</p>
					<h2 id="aide-meilleur" class="text-lg font-semibold">
						<RouterLink :to="{ name: 'AideArticle', params: { slug: meilleur.slug } }" class="hover:underline">
							<template v-for="(m, i) in surligner(meilleur.titre, q)" :key="i"><mark v-if="m.trouve">{{ m.texte }}</mark><template v-else>{{ m.texte }}</template></template>
						</RouterLink>
					</h2>
					<p class="max-w-[48rem] text-sm leading-relaxed text-ink-gray-7">{{ meilleur.resume }}</p>
					<p v-if="meilleur.extrait && !meilleur.titre.toLowerCase().includes(q.trim().toLowerCase())" class="aide-extrait">
						<template v-for="(m, i) in surligner(meilleur.extrait, q)" :key="i"><mark v-if="m.trouve">{{ m.texte }}</mark><template v-else>{{ m.texte }}</template></template>
					</p>
					<nav v-if="meilleur.sommaire?.length" class="aide-ancres" aria-label="Sections de l'article">
						<span class="text-xs text-ink-gray-6">Aller à :</span>
						<RouterLink v-for="s in meilleur.sommaire" :key="s.id" :to="{ name: 'AideArticle', params: { slug: meilleur.slug }, hash: `#${s.id}` }">{{ s.titre }}</RouterLink>
					</nav>
				</section>

				<section v-if="suivants.length" class="card aide-liste" aria-labelledby="aide-aussi">
					<h2 id="aide-aussi" class="aide-liste-titre">Aussi dans l'aide</h2>
					<RouterLink v-for="carte in suivants" :key="carte.slug" :to="{ name: 'AideArticle', params: { slug: carte.slug } }" class="aide-ligne">
						<span class="min-w-0 flex-auto">
							<span class="block text-sm font-semibold">
								<template v-for="(m, i) in surligner(carte.titre, q)" :key="i"><mark v-if="m.trouve">{{ m.texte }}</mark><template v-else>{{ m.texte }}</template></template>
							</span>
							<span class="aide-extrait block">
								<template v-for="(m, i) in surligner(carte.extrait || carte.resume, q)" :key="i"><mark v-if="m.trouve">{{ m.texte }}</mark><template v-else>{{ m.texte }}</template></template>
							</span>
						</span>
						<span class="flex-none text-xs text-ink-gray-6">{{ nomRubrique(carte.categorie) }}</span>
					</RouterLink>
				</section>

				<p class="text-[13px] text-ink-gray-6">
					Pas ce que vous cherchez ? Essayez un autre mot, ou <button type="button" class="underline hover:text-ink-gray-9" @click="effacer">parcourez les rubriques</button>. Sur une page du bureau, <kbd class="aide-kbd">?</kbd> montre d'abord
					l'aide de cette page.
				</p>
			</template>

			<!-- Une rubrique -->
			<section v-else-if="categorie" class="card aide-liste">
				<RouterLink v-for="(carte, index) in categorie.articles" :key="carte.slug" :to="{ name: 'AideArticle', params: { slug: carte.slug } }" class="aide-ligne">
					<span class="aide-num" aria-hidden="true">{{ index + 1 }}</span>
					<span class="min-w-0 flex-auto">
						<span class="block font-semibold">{{ carte.titre }}</span>
						<span v-if="carte.resume" class="block text-sm text-ink-gray-6">{{ carte.resume }}</span>
					</span>
					<span class="flex-none text-xs text-ink-gray-6">{{ dureeLabel(carte.duree_lecture) }}</span>
					<LucideChevronRight class="h-4 w-4 flex-none text-ink-gray-5" aria-hidden="true" />
				</RouterLink>
			</section>

			<!-- Les rubriques -->
			<template v-else-if="accueil">
				<section class="aide-section" aria-labelledby="aide-demarrer">
					<h2 id="aide-demarrer" class="aide-section-titre">Pour bien démarrer</h2>
					<div class="aide-departs">
						<RouterLink v-if="demarrage" :to="{ name: 'AideArticle', params: { slug: demarrage.slug } }" class="aide-depart">
							<span class="aide-ico is-mini"><LucideBookOpen class="h-4 w-4" aria-hidden="true" /></span>
							<span><strong>Première mise en route</strong><span>L'ordre à suivre pour tout régler la première fois.</span></span>
						</RouterLink>
						<button type="button" class="aide-depart" @click="ouvrirAide()">
							<span class="aide-ico is-mini"><LucideCircleHelp class="h-4 w-4" aria-hidden="true" /></span>
							<span><strong>L'aide de l'écran ouvert</strong><span>Sur n'importe quelle page, <kbd class="aide-kbd">?</kbd> ouvre les articles de cette page.</span></span>
						</button>
						<button type="button" class="aide-depart" @click="suggerer('messages')">
							<span class="aide-ico is-mini"><LucideCircleAlert class="h-4 w-4" aria-hidden="true" /></span>
							<span><strong>Un message vous bloque ?</strong><span>Chaque rubrique explique ses messages et ses raccourcis.</span></span>
						</button>
					</div>
				</section>

				<section v-if="rubriques.quotidien.length" class="aide-section" aria-labelledby="aide-quotidien">
					<h2 id="aide-quotidien" class="aide-section-titre">Au quotidien <span>Les circuits, étape par étape</span></h2>
					<div class="aide-rubriques">
						<article v-for="cat in rubriques.quotidien" :key="cat.slug" class="card aide-carte" :aria-labelledby="`aide-c-${cat.slug}`">
							<div class="aide-carte-tete">
								<span class="aide-ico"><component :is="ICONES[cat.icone] ?? LucideBookOpen" class="h-[18px] w-[18px]" aria-hidden="true" /></span>
								<h3 class="flex-auto text-base font-semibold">
									<RouterLink :id="`aide-c-${cat.slug}`" :to="{ name: 'AideCategorie', params: { slug: cat.slug } }" class="hover:underline">{{ cat.titre }}</RouterLink>
								</h3>
								<span class="aide-compte">{{ cat.articles.length }} articles</span>
							</div>
							<p class="text-[13px] text-ink-gray-6">{{ cat.description }}</p>
							<ol class="aide-etapes">
								<li v-for="(carte, index) in cat.etapes" :key="carte.slug">
									<RouterLink :to="{ name: 'AideArticle', params: { slug: carte.slug } }"><span class="aide-etape-num" aria-hidden="true">{{ index + 1 }}</span>{{ carte.titre }}</RouterLink>
								</li>
							</ol>
							<div class="aide-carte-pied">
								<RouterLink v-if="cat.vueEnsemble" :to="{ name: 'AideArticle', params: { slug: cat.vueEnsemble.slug } }">Vue d'ensemble</RouterLink>
								<RouterLink v-if="cat.messages" :to="{ name: 'AideArticle', params: { slug: cat.messages.slug } }">Messages et raccourcis ›</RouterLink>
							</div>
						</article>
					</div>
				</section>

				<section v-if="rubriques.reglages.length" class="aide-section" aria-labelledby="aide-reglages">
					<h2 id="aide-reglages" class="aide-section-titre">Réglages <span>Une fois pour toutes, puis de temps en temps</span></h2>
					<div class="aide-rubriques is-large">
						<article v-for="cat in rubriques.reglages" :key="cat.slug" class="card aide-carte" :aria-labelledby="`aide-c-${cat.slug}`">
							<div class="aide-carte-tete">
								<span class="aide-ico"><component :is="ICONES[cat.icone] ?? LucideBookOpen" class="h-[18px] w-[18px]" aria-hidden="true" /></span>
								<div class="min-w-0 flex-auto">
									<h3 class="text-[15px] font-semibold">
										<RouterLink :id="`aide-c-${cat.slug}`" :to="{ name: 'AideCategorie', params: { slug: cat.slug } }" class="hover:underline">{{ cat.titre }}</RouterLink>
									</h3>
									<p class="text-[13px] text-ink-gray-6">{{ cat.description }}</p>
								</div>
								<span class="aide-compte" :aria-label="`${cat.articles.length} articles`">{{ cat.articles.length }}</span>
							</div>
							<ul class="aide-etapes">
								<li v-for="carte in cat.etapes.slice(0, APERCU_REGLAGES)" :key="carte.slug">
									<RouterLink :to="{ name: 'AideArticle', params: { slug: carte.slug } }">{{ carte.titre }}</RouterLink>
								</li>
							</ul>
							<div class="aide-carte-pied">
								<RouterLink v-if="cat.vueEnsemble" :to="{ name: 'AideArticle', params: { slug: cat.vueEnsemble.slug } }">Vue d'ensemble</RouterLink>
								<RouterLink :to="{ name: 'AideCategorie', params: { slug: cat.slug } }">Les {{ cat.articles.length }} articles ›</RouterLink>
							</div>
						</article>
					</div>
				</section>
			</template>
			<p v-else-if="!error" class="card p-4 text-ink-gray-6">Chargement de l'aide…</p>
		</div>
	</BureauShell>
</template>
