<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideArrowLeft from '~icons/lucide/arrow-left'
import LucideChevronLeft from '~icons/lucide/chevron-left'
import LucideChevronRight from '~icons/lucide/chevron-right'
import LucidePlus from '~icons/lucide/plus'
import LucideTrash2 from '~icons/lucide/trash-2'
import FormDialog from '@shared/components/FormDialog.vue'
import AideContenu from '@/aide/AideContenu.vue'
import AideArticleList from '@/components/AideArticleList.vue'
import AppToast from '@/components/AppToast.vue'
import BureauShell from '@/components/BureauShell.vue'
import { apercuAide, createArticleAide, deleteArticleAide, getArticleAideEdition, listArticlesAide, saveArticleAide } from '@/lib/api'
import { CONVENTIONS, dureeLabel, type AideApercu, type AideEdition, type AideListe, type AideValeurs } from '@/lib/aide'
import { confirmAction } from '@/lib/confirm'
import { activePoste, pagesFor } from '@/lib/postes'
import { useArticlesAide } from '@/lib/useArticlesAide'

/** Réglages › Aide : la liste des articles du centre d'aide (/reglages-aide), puis un article ouvert dans son
 * éditeur Markdown avec aperçu (/reglages-aide/<slug>). */
const route = useRoute()
const router = useRouter()

const liste = ref<AideListe | null>(null)
const error = ref('')
const actionError = ref('')
const notice = ref('')
const busy = ref(false)
// La liste reste montée pendant qu'un article est ouvert : elle garde sa vue, ses filtres et sa page.
const state = useArticlesAide()
const slug = computed(() => (typeof route.params.slug === 'string' ? route.params.slug : ''))

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

async function charger(nom: string) {
	actionError.value = ''
	article.value = null
	fiche.value = null
	if (!nom) return
	try {
		const doc = await getArticleAideEdition(nom)
		article.value = doc
		fiche.value = versFiche(doc)
		apercu.value = { html: doc.html, sommaire: [], duree_lecture: doc.duree_lecture }
		onglet.value = 'ecrire'
	} catch (e) {
		actionError.value = (e as Error).message
	}
}
const ouvrir = (nom: string) => router.push({ name: 'ReglagesAide', params: { slug: nom } })

async function quitter() {
	return !ficheDirty.value || confirmAction({ title: 'Quitter cet article ?', message: 'Les modifications non enregistrées seront perdues.', confirmLabel: 'Quitter sans enregistrer', danger: true })
}
onBeforeRouteLeave(quitter)
onBeforeRouteUpdate(async (to, from) => {
	if (to.params.slug !== from.params.slug && !(await quitter())) return false
})
// L'article suit l'adresse : ouvert depuis la liste, les flèches ou un lien.
watch(slug, (nom) => charger(nom))

// Article précédent et suivant, dans la liste telle qu'elle est affichée.
const voisins = computed(() => {
	const suite = state.names.value
	const i = suite.indexOf(slug.value)
	return { position: i + 1, total: suite.length, avant: i > 0 ? suite[i - 1] : null, apres: i >= 0 && i < suite.length - 1 ? suite[i + 1] : null }
})
async function aller(nom: string | null) {
	if (!nom) return
	await router.replace({ name: 'ReglagesAide', params: { slug: nom } })
	state.reveal(nom)
}

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
		state.load()
	} catch (e) {
		actionError.value = (e as Error).message
		if ((e as Error).message.includes('modifié par ailleurs')) {
			await charger(article.value.slug)
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
		notice.value = 'Article supprimé.'
		state.load()
		router.replace({ name: 'ReglagesAide' })
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
		state.load()
		ouvrir(doc.slug)
	} catch (e) {
		if (creation.value) creation.value.error = (e as Error).message
	} finally {
		busy.value = false
	}
}

onMounted(async () => {
	// L'ancienne adresse ?article=<slug> mène à l'article.
	if (!slug.value && typeof route.query.article === 'string') {
		router.replace({ name: 'ReglagesAide', params: { slug: route.query.article } })
		return
	}
	charger(slug.value)
	await load()
})
</script>

<template>
	<BureauShell :crumbs="slug ? [{ label: 'Réglages' }, { label: 'Aide', to: { name: 'ReglagesAide' } }, { label: article?.titre || '…' }] : [{ label: 'Réglages' }, { label: 'Aide' }]" active="reglages-aide">
		<div class="bureau-work" :class="slug && 'tdb'">
			<AideArticleList v-show="!slug" :state="state" :selected="slug || undefined" @open="ouvrir" @create="ouvrirCreation" @changed="state.load()" />

			<template v-if="slug">
				<div class="flex flex-wrap items-center gap-2">
					<RouterLink :to="{ name: 'ReglagesAide' }" class="btn-ghost"><LucideArrowLeft class="h-3.5 w-3.5" aria-hidden="true" />Tous les articles</RouterLink>
					<span class="flex-auto"></span>
					<span class="text-xs tabular-nums text-ink-gray-6">{{ voisins.position ? `${voisins.position} sur ${voisins.total}` : 'Hors de la vue' }}</span>
					<button type="button" class="icon-btn" aria-label="Article précédent" :disabled="!voisins.avant" @click="aller(voisins.avant)"><LucideChevronLeft class="h-4 w-4" aria-hidden="true" /></button>
					<button type="button" class="icon-btn" aria-label="Article suivant" :disabled="!voisins.apres" @click="aller(voisins.apres)"><LucideChevronRight class="h-4 w-4" aria-hidden="true" /></button>
				</div>
				<p v-if="actionError" role="alert" class="rounded-control tone-red px-3.5 py-2.5">{{ actionError }}</p>
				<p v-else-if="!article" class="card p-4 text-ink-gray-6">Chargement de l'article…</p>
				<section v-if="article && fiche" class="card overflow-hidden" aria-labelledby="a-titre">
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
									<option v-for="cat in liste?.categories" :key="cat.slug" :value="cat.slug">{{ cat.titre }}</option>
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
			</template>
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
