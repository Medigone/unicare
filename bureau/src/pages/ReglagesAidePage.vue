<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucidePlus from '~icons/lucide/plus'
import LucideSearch from '~icons/lucide/search'
import LucideTrash2 from '~icons/lucide/trash-2'
import FormDialog from '@shared/components/FormDialog.vue'
import AideContenu from '@/aide/AideContenu.vue'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import { apercuAide, createArticleAide, deleteArticleAide, getArticleAideEdition, listArticlesAide, saveArticleAide } from '@/lib/api'
import { CONVENTIONS, dureeLabel, ecransLabels, filtrerArticlesAide, type AideApercu, type AideEdition, type AideListe, type AideValeurs } from '@/lib/aide'
import { confirmAction } from '@/lib/confirm'
import { activePoste, pagesFor } from '@/lib/postes'

/** Réglages › Aide : les articles du centre d'aide, rangés par rubrique, et leur éditeur Markdown avec aperçu. */
const route = useRoute()
const router = useRouter()

const liste = ref<AideListe | null>(null)
const error = ref('')
const actionError = ref('')
const notice = ref('')
const busy = ref(false)
const recherche = ref('')
const vue = ref<'tous' | 'Publié' | 'Brouillon'>('tous')

const article = ref<AideEdition | null>(null)
const fiche = ref<Required<AideValeurs> | null>(null)
const onglet = ref<'ecrire' | 'apercu'>('ecrire')
const apercu = ref<AideApercu | null>(null)

const ecrans = computed(() => pagesFor(activePoste().key).map((page) => ({ id: page.id, label: page.module ? `${page.module} · ${page.label}` : page.label })))

async function load() {
	try {
		liste.value = await listArticlesAide()
		error.value = ''
	} catch (e) {
		if (!liste.value) error.value = (e as Error).message
	}
}

function versFiche(doc: AideEdition): Required<AideValeurs> {
	return { titre: doc.titre, categorie: doc.categorie, statut: doc.statut, ordre: doc.ordre, resume: doc.resume, contenu_markdown: doc.contenu_markdown, ecrans: [...doc.ecrans], mots_cles: doc.mots_cles }
}
const ficheDirty = computed(() => Boolean(article.value && fiche.value && JSON.stringify(fiche.value) !== JSON.stringify(versFiche(article.value))))

async function ouvrir(slug: string) {
	if (slug === article.value?.slug) return
	if (ficheDirty.value && !(await confirmAction({ title: 'Quitter cet article ?', message: 'Les modifications non enregistrées seront perdues.', confirmLabel: 'Quitter sans enregistrer', danger: true }))) return
	actionError.value = ''
	try {
		const doc = await getArticleAideEdition(slug)
		article.value = doc
		fiche.value = versFiche(doc)
		apercu.value = { html: doc.html, sommaire: [], duree_lecture: doc.duree_lecture }
		if (route.query.article !== slug) router.replace({ query: { article: slug } })
	} catch (e) {
		actionError.value = (e as Error).message
	}
}

const groupes = computed(() => {
	if (!liste.value) return []
	const articles = filtrerArticlesAide(liste.value.articles, recherche.value, vue.value)
	return liste.value.categories.map((cat) => ({ ...cat, articles: articles.filter((a) => a.categorie === cat.slug) })).filter((cat) => cat.articles.length)
})
const compte = (statut: 'tous' | 'Publié' | 'Brouillon') => (liste.value ? filtrerArticlesAide(liste.value.articles, '', statut).length : 0)

// Aperçu : rendu par le serveur, comme à l'enregistrement, une fois la frappe posée.
let minuteur: ReturnType<typeof setTimeout> | null = null
let demande = 0
watch(
	() => fiche.value?.contenu_markdown,
	(markdown, avant) => {
		if (markdown === undefined || avant === undefined) return
		if (minuteur) clearTimeout(minuteur)
		minuteur = setTimeout(async () => {
			const numero = ++demande
			try {
				const rendu = await apercuAide(markdown)
				if (numero === demande) apercu.value = rendu
			} catch {
				/* l'aperçu reste le précédent */
			}
		}, 350)
	},
)

function basculerEcran(id: string) {
	if (!fiche.value) return
	fiche.value.ecrans = fiche.value.ecrans.includes(id) ? fiche.value.ecrans.filter((e) => e !== id) : [...fiche.value.ecrans, id]
}

async function enregistrer() {
	if (!article.value || !fiche.value) return
	busy.value = true
	actionError.value = ''
	try {
		const doc = await saveArticleAide(article.value, fiche.value)
		article.value = doc
		fiche.value = versFiche(doc)
		notice.value = 'Article enregistré : il est déjà à jour dans l\'aide.'
		await load()
	} catch (e) {
		actionError.value = (e as Error).message
		if ((e as Error).message.includes('modifié par ailleurs')) {
			const slug = article.value.slug
			article.value = null
			await ouvrir(slug)
		}
	} finally {
		busy.value = false
	}
}
function annuler() {
	if (article.value) fiche.value = versFiche(article.value)
}

async function supprimer() {
	if (!article.value) return
	const ok = await confirmAction({ title: `Supprimer « ${article.value.titre} » ?`, message: "L'article disparaît de l'aide. Un article tiré d'un guide revient au prochain import des guides.", confirmLabel: "Supprimer l'article", danger: true })
	if (!ok) return
	busy.value = true
	try {
		await deleteArticleAide(article.value)
		article.value = null
		fiche.value = null
		router.replace({ query: {} })
		notice.value = 'Article supprimé.'
		await load()
	} catch (e) {
		actionError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}

// Nouvel article
const creation = ref<{ titre: string; categorie: string; error: string } | null>(null)
function ouvrirCreation() {
	creation.value = { titre: '', categorie: article.value?.categorie || liste.value?.categories[0]?.slug || '', error: '' }
}
async function creer() {
	if (!creation.value) return
	if (!creation.value.titre.trim()) {
		creation.value.error = "Donnez un titre à l'article."
		return
	}
	busy.value = true
	try {
		const doc = await createArticleAide({ titre: creation.value.titre.trim(), categorie: creation.value.categorie, contenu_markdown: '## Comment faire\n\n1. \n' })
		creation.value = null
		await load()
		article.value = null
		await ouvrir(doc.slug)
	} catch (e) {
		if (creation.value) creation.value.error = (e as Error).message
	} finally {
		busy.value = false
	}
}

onMounted(async () => {
	await load()
	const demande = typeof route.query.article === 'string' ? route.query.article : liste.value?.articles[0]?.slug
	if (demande) ouvrir(demande)
})
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Réglages' }, { label: 'Aide' }]" active="reglages-aide">
		<div class="bureau-work tdb">
			<div class="flex flex-wrap items-end gap-3">
				<div class="min-w-0 flex-[1_1_24rem]">
					<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Aide</h1>
					<p class="text-sm text-ink-gray-6">Les articles que le bouton « ? » et le centre d'aide affichent. Un article publié est visible de tous dès l'enregistrement ; un brouillon, seulement d'ici.</p>
				</div>
				<RouterLink :to="{ name: 'Aide' }" class="btn-secondary">Voir le centre d'aide<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" /></RouterLink>
				<button v-if="liste" type="button" class="btn-primary" :disabled="busy" @click="ouvrirCreation"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Nouvel article</button>
			</div>
			<p v-if="error" role="alert" class="card p-4 text-tone-red">{{ error }}</p>
			<p v-else-if="!liste" class="card p-4 text-ink-gray-6">Chargement des articles…</p>
			<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>

			<div v-if="liste" class="tarifs-layout">
				<nav class="card tarifs-liste" aria-label="Articles d'aide">
					<label class="bureau-search">
						<LucideSearch class="h-3.5 w-3.5" aria-hidden="true" />
						<input v-model="recherche" class="field-input" type="search" aria-label="Chercher un article" placeholder="Titre ou écran" />
					</label>
					<div class="seg self-start" role="group" aria-label="Afficher">
						<button type="button" :aria-pressed="vue === 'tous'" @click="vue = 'tous'">Tous<span class="ml-1 tabular-nums text-ink-gray-6">{{ compte('tous') }}</span></button>
						<button type="button" :aria-pressed="vue === 'Publié'" @click="vue = 'Publié'">Publiés<span class="ml-1 tabular-nums text-ink-gray-6">{{ compte('Publié') }}</span></button>
						<button type="button" :aria-pressed="vue === 'Brouillon'" @click="vue = 'Brouillon'">Brouillons<span class="ml-1 tabular-nums text-ink-gray-6">{{ compte('Brouillon') }}</span></button>
					</div>
					<div v-for="cat in groupes" :key="cat.slug" class="tarifs-groupe">
						<span class="stock-groupe-titre">{{ cat.titre }}</span>
						<button v-for="row in cat.articles" :key="row.slug" type="button" class="tarif-item" :aria-current="row.slug === article?.slug ? 'page' : undefined" @click="ouvrir(row.slug)">
							<span class="block font-semibold">{{ row.titre }}</span>
							<span class="flex flex-wrap items-center gap-1.5">
								<span v-if="row.statut === 'Brouillon'" class="badge tone-amber">Brouillon</span>
								<span class="truncate text-xs text-ink-gray-6">{{ ecransLabels(row.ecrans, ecrans).join(' · ') || 'Aucun écran' }}</span>
							</span>
						</button>
					</div>
					<p v-if="!groupes.length" class="px-2.5 text-sm text-ink-gray-6">Aucun article ne correspond.</p>
				</nav>

				<section v-if="article && fiche" class="card tarifs-detail overflow-hidden" aria-labelledby="a-titre">
					<div class="tarifs-head flex-row flex-wrap items-center gap-3">
						<div class="min-w-0 flex-[1_1_18rem]">
							<h2 id="a-titre" class="text-lg font-semibold">{{ article.titre }}</h2>
							<p class="text-xs text-ink-gray-6">{{ [article.source ? `Tiré de ${article.source}` : 'Écrit dans le bureau', article.date_revision && `revu le ${article.date_revision.split('-').reverse().join('/')}`, dureeLabel(article.duree_lecture)].filter(Boolean).join(' · ') }}</p>
						</div>
						<label class="flex items-center gap-2 text-sm font-medium">
							<input type="checkbox" role="switch" class="table-panel-switch" :checked="fiche.statut === 'Publié'" :disabled="busy" @change="fiche.statut = fiche.statut === 'Publié' ? 'Brouillon' : 'Publié'" />
							{{ fiche.statut === 'Publié' ? 'Publié' : 'Brouillon' }}
						</label>
						<RouterLink :to="{ name: 'AideArticle', params: { slug: article.slug } }" class="btn-ghost">Voir<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" /></RouterLink>
						<button type="button" class="icon-btn text-tone-red" aria-label="Supprimer l'article" title="Supprimer l'article" :disabled="busy" @click="supprimer"><LucideTrash2 class="h-4 w-4" aria-hidden="true" /></button>
					</div>

					<div class="flex flex-col gap-3.5 px-4 pb-4 pt-1">
						<div class="form-grid">
							<div class="form-field col-span-full">
								<label class="field-label" for="a-f-titre">Titre <span class="req">obligatoire</span></label>
								<input id="a-f-titre" v-model="fiche.titre" class="field-input" autocomplete="off" />
							</div>
							<div class="form-field">
								<label class="field-label" for="a-f-cat">Rubrique</label>
								<select id="a-f-cat" v-model="fiche.categorie" class="field-input">
									<option v-for="cat in liste.categories" :key="cat.slug" :value="cat.slug">{{ cat.titre }}</option>
								</select>
							</div>
							<div class="form-field">
								<label class="field-label" for="a-f-ordre">Ordre dans la rubrique</label>
								<input id="a-f-ordre" v-model.number="fiche.ordre" class="field-input tabular-nums" type="number" step="10" min="0" />
							</div>
							<div class="form-field col-span-full">
								<label class="field-label" for="a-f-resume">Résumé</label>
								<input id="a-f-resume" v-model="fiche.resume" class="field-input" autocomplete="off" />
								<span class="field-note">Une phrase, sous le titre dans les listes et la recherche.</span>
							</div>
							<div class="form-field col-span-full">
								<label class="field-label" for="a-f-mots">Mots-clés</label>
								<input id="a-f-mots" v-model="fiche.mots_cles" class="field-input" autocomplete="off" placeholder="avoir, remboursement, retour" />
								<span class="field-note">Les mots qu'on taperait pour trouver l'article sans qu'ils soient dans le texte.</span>
							</div>
						</div>

						<fieldset class="aide-ecrans">
							<legend class="field-label">Proposé « Sur cette page » dans</legend>
							<div class="flex flex-wrap gap-1.5">
								<button v-for="ecran in ecrans" :key="ecran.id" type="button" class="aide-puce" :aria-pressed="fiche.ecrans.includes(ecran.id)" @click="basculerEcran(ecran.id)">{{ ecran.label }}</button>
							</div>
						</fieldset>

						<div class="flex flex-wrap items-center gap-2">
							<span class="field-label m-0 flex-auto">Contenu</span>
							<div class="seg aide-onglets" role="group" aria-label="Contenu">
								<button type="button" :aria-pressed="onglet === 'ecrire'" @click="onglet = 'ecrire'">Écrire</button>
								<button type="button" :aria-pressed="onglet === 'apercu'" @click="onglet = 'apercu'">Aperçu</button>
							</div>
						</div>
						<div class="aide-editeur" :data-onglet="onglet">
							<textarea v-model="fiche.contenu_markdown" class="field-input aide-markdown" aria-label="Contenu en Markdown" spellcheck="true"></textarea>
							<div class="aide-apercu" aria-label="Aperçu" aria-live="polite">
								<AideContenu v-if="apercu?.html" :html="apercu.html" compact />
								<p v-else class="text-sm text-ink-gray-6">L'aperçu s'affiche ici.</p>
							</div>
						</div>
						<details class="aide-memo">
							<summary>Aide-mémoire de mise en forme</summary>
							<dl>
								<template v-for="ligne in CONVENTIONS" :key="ligne.code">
									<dt><code>{{ ligne.code }}</code></dt>
									<dd>{{ ligne.rendu }}</dd>
								</template>
							</dl>
						</details>
					</div>
					<div class="stock-barre" :class="ficheDirty && 'is-dirty'">
						<span class="flex-auto text-sm" :class="ficheDirty ? 'font-medium text-tone-amber' : 'text-ink-gray-6'">{{ ficheDirty ? 'Modifications non enregistrées' : 'Aucune modification' }}</span>
						<button type="button" class="btn-ghost" :disabled="busy || !ficheDirty" @click="annuler">Annuler</button>
						<button type="button" class="btn-primary" :disabled="busy || !ficheDirty || !fiche.titre.trim()" @click="enregistrer">Enregistrer</button>
					</div>
				</section>
				<section v-else class="card tarifs-detail p-6 text-center text-ink-gray-6">Choisissez un article à gauche, ou créez-en un.</section>
			</div>
		</div>

		<FormDialog v-if="creation" title="Nouvel article" :dirty="Boolean(creation.titre.trim())" :busy="busy" @close="creation = null" @submit="creer">
			<div class="flex flex-col gap-3">
				<div class="form-field">
					<label class="field-label" for="n-a-titre">Titre <span class="req">obligatoire</span></label>
					<input id="n-a-titre" v-model="creation.titre" class="field-input" autocomplete="off" placeholder="Faire un avoir" />
				</div>
				<div class="form-field">
					<label class="field-label" for="n-a-cat">Rubrique</label>
					<select id="n-a-cat" v-model="creation.categorie" class="field-input">
						<option v-for="cat in liste?.categories" :key="cat.slug" :value="cat.slug">{{ cat.titre }}</option>
					</select>
				</div>
				<p class="field-note">L'article est créé en brouillon : publiez-le quand il est prêt.</p>
				<p v-if="creation.error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ creation.error }}</p>
			</div>
			<template #actions>
				<button type="button" class="btn-primary" :disabled="busy" @click="creer">{{ busy ? 'Création…' : "Créer l'article" }}</button>
			</template>
		</FormDialog>
		<AppToast :message="notice" tone="success" @close="notice = ''" />
	</BureauShell>
</template>
