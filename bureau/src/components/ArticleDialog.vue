<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import LucideInfo from '~icons/lucide/info'
import FormDialog from '@shared/components/FormDialog.vue'
import LinkInput from './LinkInput.vue'
import { createArticle, getArticleOptions, searchArticles, updateArticle } from '@/lib/api'
import { articleFormValues, changedArticleValues, validateArticle, type ArticleChoice, type ArticleDetail, type ArticleField, type ArticleOptions, type ArticleValues } from '@/lib/articles'
import { normalizeName } from '@/lib/clients'

/** Nouvel article, ou modification d'un article (`article`) : la même fenêtre. Le type et le code-barres ne se saisissent qu'à la création. */
const props = defineProps<{ article?: ArticleDetail }>()
const emit = defineEmits<{ close: []; created: [name: string]; saved: [article: ArticleDetail] }>()

const editing = computed(() => Boolean(props.article))
const EMPTY: Record<ArticleField, string> = { type: '', designation: '', groupe: '', uom: '', is_stock_item: '1', has_batch_no: '0', description: '', shelf_life_in_days: '', barcode: '', is_purchase_item: '1', is_sales_item: '1', disabled: '0' }
const initial: ArticleValues = props.article ? { ...EMPTY, ...articleFormValues(props.article) } : { ...EMPTY }
const values = reactive<Record<ArticleField, string>>({ ...(initial as Record<ArticleField, string>) })
const options = ref<ArticleOptions | null>(null)
const loadError = ref('')
const serverError = ref('')
const errors = ref<Partial<Record<ArticleField, string>>>({})
const busy = ref(false)
const changes = computed(() => changedArticleValues(initial, values))
const dirty = computed(() => Object.entries(values).some(([field, value]) => value.trim() !== (initial[field as ArticleField] ?? '').trim()))

// Le préfixe du code, tel que CustomItem le génère.
const PREFIXES: Record<string, string> = { Fût: 'FU', Conditionnement: 'CO', 'Produit fini': 'PF', Autre: 'AU' }
// Un fût ou un produit fini est toujours stocké par lots : le serveur l'impose, la fenêtre le montre.
const lotForced = computed(() => Boolean(values.type && options.value?.types_avec_lot.includes(values.type)))
watch(lotForced, (forced) => {
	if (!forced) return
	values.is_stock_item = '1'
	values.has_batch_no = '1'
})

onMounted(async () => {
	try {
		options.value = await getArticleOptions()
	} catch (e) {
		loadError.value = (e as Error).message
	}
})

watch(
	() => ({ ...values }),
	(current, previous) => {
		for (const field of Object.keys(current) as ArticleField[]) if (current[field] !== previous[field] && errors.value[field]) delete errors.value[field]
	},
)

// Désignation : le serveur refuse un doublon parmi les articles actifs. La fenêtre signale les noms proches dès la saisie.
const similar = ref<ArticleChoice[]>([])
let lastName = 0
let nameTimer: ReturnType<typeof setTimeout> | null = null
watch(
	() => values.designation,
	(name) => {
		if (nameTimer) clearTimeout(nameTimer)
		const query = normalizeName(name)
		if (query.length < 3) {
			similar.value = []
			return
		}
		nameTimer = setTimeout(async () => {
			const request = ++lastName
			try {
				const found = await searchArticles(name)
				if (request === lastName) similar.value = found.filter((item) => item.name !== props.article?.name && normalizeName(item.label).includes(query)).slice(0, 3)
			} catch {
				// Le serveur refusera de toute façon un doublon.
			}
		}, 250)
	},
)

// Unité : celles déjà employées dans une liste courte, les autres (plus de deux cents) par recherche.
const OTHER_UOM = '__autre__'
const uomSearch = ref(false)
function onUom() {
	if (values.uom !== OTHER_UOM) return
	values.uom = ''
	uomSearch.value = true
}

function toggle(field: ArticleField, event: Event) {
	values[field] = (event.target as HTMLInputElement).checked ? '1' : '0'
	if (field === 'is_stock_item' && values.is_stock_item === '0') values.has_batch_no = '0'
}

async function submit() {
	if (busy.value) return
	errors.value = validateArticle(values, editing.value)
	serverError.value = ''
	if (Object.keys(errors.value).length) {
		await nextTick()
		document.querySelector<HTMLElement>('.dialog [aria-invalid="true"]')?.focus()
		return
	}
	if (props.article && !Object.keys(changes.value).length) {
		emit('close')
		return
	}
	busy.value = true
	try {
		if (props.article) {
			emit('saved', await updateArticle(props.article, changes.value))
		} else {
			const { disabled: _disabled, is_purchase_item: _achat, is_sales_item: _vente, ...fields } = values
			const { name } = await createArticle(Object.fromEntries(Object.entries(fields).map(([field, value]) => [field, value.trim()])))
			emit('created', name)
		}
		emit('close')
	} catch (e) {
		// La saisie reste en place : rien n'est perdu si le serveur refuse.
		serverError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
onBeforeUnmount(() => {
	if (nameTimer) clearTimeout(nameTimer)
})
</script>

<template>
	<FormDialog :title="editing ? 'Modifier l\'article' : 'Nouvel article'" :dirty="dirty" :busy="busy" :hint="editing ? 'Ctrl + Entrée pour enregistrer' : 'Ctrl + Entrée pour créer'" @close="emit('close')" @submit="submit">
		<p v-if="loadError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ loadError }}</p>

		<div class="form-grid">
			<div class="form-field">
				<label class="field-label" for="article-type">Type <span v-if="!editing" class="req">obligatoire</span></label>
				<select v-if="!editing" id="article-type" v-model="values.type" class="field-input" :aria-invalid="Boolean(errors.type)">
					<option value="">Choisir…</option>
					<option v-for="item in options?.types" :key="item" :value="item">{{ item }}</option>
				</select>
				<p v-else id="article-type" class="field-input flex items-center text-ink-gray-7">{{ values.type || '—' }}</p>
				<p v-if="errors.type" class="field-error" role="alert">{{ errors.type }}</p>
				<p v-else-if="editing" class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Le type a fixé le code de l'article : il ne change plus.</span></p>
				<p v-else-if="values.type" class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Code généré : {{ PREFIXES[values.type] ?? '?' }}-000001 et suivants.</span></p>
			</div>
			<div class="form-field">
				<label class="field-label" for="article-groupe">Groupe <span class="req">obligatoire</span></label>
				<select id="article-groupe" v-model="values.groupe" class="field-input" :aria-invalid="Boolean(errors.groupe)">
					<option value="">Choisir…</option>
					<option v-if="values.groupe && options && !options.groupes.includes(values.groupe)" :value="values.groupe">{{ values.groupe }}</option>
					<option v-for="item in options?.groupes" :key="item" :value="item">{{ item }}</option>
				</select>
				<p v-if="errors.groupe" class="field-error" role="alert">{{ errors.groupe }}</p>
			</div>
		</div>

		<div class="form-field">
			<label class="field-label" for="article-designation">Désignation <span class="req">obligatoire</span></label>
			<input id="article-designation" v-model="values.designation" class="field-input" placeholder="Lotion lavante bébé 500 ml" autocomplete="off" :aria-invalid="Boolean(errors.designation)" />
			<p v-if="errors.designation" class="field-error" role="alert">{{ errors.designation }}</p>
			<p v-if="similar.length" class="field-note">
				<LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" />
				<span>
					Déjà enregistré :
					<template v-for="(item, index) in similar" :key="item.name">{{ index ? ', ' : '' }}<a class="ref-link" :href="`/bureau/articles/${encodeURIComponent(item.name)}`" target="_blank" rel="noopener noreferrer">{{ item.label }}</a> ({{ item.name }}<template v-if="item.disabled">, désactivé</template>)</template>.
				</span>
			</p>
		</div>

		<div class="form-grid">
			<div class="form-field">
				<label class="field-label" for="article-uom">Unité de stock <span class="req">obligatoire</span></label>
				<select v-if="!uomSearch && options?.uoms.length && (!values.uom || options.uoms.includes(values.uom))" id="article-uom" v-model="values.uom" class="field-input" :aria-invalid="Boolean(errors.uom)" @change="onUom">
					<option value="">Choisir…</option>
					<option v-for="item in options.uoms" :key="item" :value="item">{{ item }}</option>
					<option :value="OTHER_UOM">Autre unité…</option>
				</select>
				<LinkInput v-else v-model="values.uom" doctype="Item" fieldname="stock_uom" input-id="article-uom" />
				<p v-if="errors.uom" class="field-error" role="alert">{{ errors.uom }}</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="article-conservation">Durée de conservation (jours)</label>
				<input id="article-conservation" v-model="values.shelf_life_in_days" class="field-input tabular-nums" inputmode="numeric" placeholder="730" autocomplete="off" :aria-invalid="Boolean(errors.shelf_life_in_days)" />
				<p v-if="errors.shelf_life_in_days" class="field-error" role="alert">{{ errors.shelf_life_in_days }}</p>
				<p v-else class="field-note"><span>Sert à calculer la péremption des lots.</span></p>
			</div>
			<div v-if="!editing" class="form-field">
				<label class="field-label" for="article-barcode">Code-barres</label>
				<input id="article-barcode" v-model="values.barcode" class="field-input tabular-nums" placeholder="6130000000017" autocomplete="off" />
			</div>
		</div>

		<div class="flex flex-wrap gap-x-5 gap-y-1.5">
			<label class="export-choice"><input type="checkbox" :checked="values.is_stock_item === '1'" :disabled="lotForced" @change="toggle('is_stock_item', $event)" /> Article de stock</label>
			<label class="export-choice"><input type="checkbox" :checked="values.has_batch_no === '1'" :disabled="lotForced || values.is_stock_item !== '1'" @change="toggle('has_batch_no', $event)" /> Géré par lots</label>
			<template v-if="editing">
				<label class="export-choice"><input type="checkbox" :checked="values.is_purchase_item === '1'" @change="toggle('is_purchase_item', $event)" /> Acheté</label>
				<label class="export-choice"><input type="checkbox" :checked="values.is_sales_item === '1'" @change="toggle('is_sales_item', $event)" /> Vendu</label>
				<label class="export-choice"><input type="checkbox" :checked="values.disabled === '1'" @change="toggle('disabled', $event)" /> Désactivé</label>
			</template>
		</div>
		<p v-if="errors.has_batch_no" class="field-error" role="alert">{{ errors.has_batch_no }}</p>
		<p v-else-if="lotForced" class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Un {{ values.type.toLowerCase() }} est toujours stocké et suivi par lots.</span></p>

		<div class="form-field">
			<label class="field-label" for="article-description">Description</label>
			<textarea id="article-description" v-model="values.description" class="field-input min-h-[4.5rem]" rows="3" placeholder="Reprend la désignation si elle reste vide."></textarea>
		</div>

		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>

		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Enregistrement…' : editing ? 'Enregistrer' : "Créer l'article" }}</button>
		</template>
	</FormDialog>
</template>
