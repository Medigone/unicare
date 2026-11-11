<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import LucideInfo from '~icons/lucide/info'
import LucidePlus from '~icons/lucide/plus'
import LucideTrash2 from '~icons/lucide/trash-2'
import FormDialog from '@shared/components/FormDialog.vue'
import { createRecette, getRecetteOptions, updateRecette } from '@/lib/api'
import { parseQty } from '@/lib/ordres'
import { recetteErrors, type RecetteDetail, type RecetteOptions } from '@/lib/recettes'

/**
 * Création ou modification d'une recette : le produit fini, la quantité pour laquelle la recette est donnée, le
 * rendement visé, et les matières (au moins un fût). Les ordres déjà créés gardent leurs quantités.
 */
const props = defineProps<{ recette?: RecetteDetail; produit?: string }>()
const emit = defineEmits<{ close: []; created: [name: string]; saved: [recette: RecetteDetail] }>()

interface Ligne {
	key: number
	article: string
	quantite: string
	unite: string
	obligatoire: boolean
}
let nextKey = 0
const ligne = (values: Partial<Ligne> = {}): Ligne => ({ key: nextKey++, article: '', quantite: '', unite: '', obligatoire: true, ...values })

const options = ref<RecetteOptions | null>(null)
const loadError = ref('')
const produit = ref(props.recette?.produit ?? props.produit ?? '')
const quantiteBase = ref(props.recette ? String(props.recette.quantite_base).replace('.', ',') : '1')
const unite = ref(props.recette?.unite ?? '')
const rendement = ref(props.recette ? String(props.recette.rendement).replace('.', ',') : '100')
const lignes = ref<Ligne[]>(props.recette ? props.recette.ingredients.map((row) => ligne({ article: row.article, quantite: String(row.quantite).replace('.', ','), unite: row.unite ?? '', obligatoire: row.obligatoire })) : [ligne()])
const errors = ref<string[]>([])
const serverError = ref('')
const busy = ref(false)
const dirty = ref(false)

onMounted(async () => {
	try {
		options.value = await getRecetteOptions()
		if (props.produit && !props.recette) unite.value = options.value.produits.find((item) => item.value === props.produit)?.unite ?? unite.value
	} catch (e) {
		loadError.value = (e as Error).message
	}
})

const matiere = (article: string) => options.value?.matieres.find((item) => item.value === article)
function onProduit() {
	dirty.value = true
	unite.value = options.value?.produits.find((item) => item.value === produit.value)?.unite ?? unite.value
}
function onMatiere(row: Ligne) {
	dirty.value = true
	row.unite = matiere(row.article)?.unite ?? row.unite
}
function addLigne() {
	lignes.value.push(ligne())
}
function removeLigne(row: Ligne) {
	lignes.value = lignes.value.filter((item) => item.key !== row.key)
	dirty.value = true
}
const produitLabel = computed(() => options.value?.produits.find((item) => item.value === produit.value)?.label ?? produit.value)

async function submit() {
	if (busy.value) return
	serverError.value = ''
	const values = {
		produit: produit.value,
		quantite_base: parseQty(quantiteBase.value),
		unite: unite.value || undefined,
		rendement: parseQty(rendement.value),
		ingredients: lignes.value.filter((row) => row.article).map((row) => ({ article: row.article, quantite: parseQty(row.quantite), unite: row.unite || undefined, obligatoire: row.obligatoire })),
	}
	errors.value = recetteErrors({ ...values, ingredients: values.ingredients.map((row) => ({ ...row, type: matiere(row.article)?.type })) })
	if (errors.value.length) return
	busy.value = true
	try {
		if (props.recette) emit('saved', await updateRecette(props.recette, values))
		else emit('created', (await createRecette(values)).name)
		emit('close')
	} catch (e) {
		serverError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog class="recette-dialog" :title="recette ? `Modifier la recette ${recette.name}` : 'Nouvelle recette'" :dirty="dirty" :busy="busy" :hint="recette ? 'Ctrl + Entrée pour enregistrer' : 'Ctrl + Entrée pour créer'" @close="emit('close')" @submit="submit">
		<p v-if="loadError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ loadError }}</p>
		<div class="form-field">
			<label class="field-label" for="recette-produit">Produit fini <span class="req">obligatoire</span></label>
			<select v-search id="recette-produit" v-model="produit" class="field-input" @change="onProduit">
				<option value="">Choisir le produit…</option>
				<option v-if="produit && !options?.produits.some((item) => item.value === produit)" :value="produit">{{ produitLabel }}</option>
				<option v-for="item in options?.produits" :key="item.value" :value="item.value">{{ item.label }} ({{ item.value }})</option>
			</select>
		</div>
		<div class="recette-head">
			<div class="form-field">
				<label class="field-label" for="recette-base">Recette donnée pour</label>
				<input id="recette-base" v-model="quantiteBase" class="field-input text-right tabular-nums" inputmode="decimal" @input="dirty = true" />
			</div>
			<div class="form-field">
				<label class="field-label" for="recette-unite">Unité</label>
				<select v-search id="recette-unite" v-model="unite" class="field-input" @change="dirty = true">
					<option v-if="unite && !options?.unites.includes(unite)" :value="unite">{{ unite }}</option>
					<option v-for="item in options?.unites" :key="item" :value="item">{{ item }}</option>
				</select>
			</div>
			<div class="form-field">
				<label class="field-label" for="recette-rendement">Rendement visé (%)</label>
				<input id="recette-rendement" v-model="rendement" class="field-input text-right tabular-nums" inputmode="decimal" @input="dirty = true" />
			</div>
		</div>

		<section class="flex flex-col gap-2">
			<h3 class="text-sm font-semibold">Matières pour {{ quantiteBase || '…' }} {{ unite }}</h3>
			<div class="recette-lines" role="table" aria-label="Matières de la recette">
				<div class="recette-line recette-line-head" role="row">
					<span role="columnheader">Matière</span>
					<span role="columnheader" class="text-right">Quantité</span>
					<span role="columnheader">Unité</span>
					<span role="columnheader" class="text-center">Obligatoire</span>
					<span role="columnheader"><span class="sr-only">Retirer</span></span>
				</div>
				<div v-for="(row, index) in lignes" :key="row.key" class="recette-line" role="row">
					<span role="cell" class="recette-line-matiere">
						<select v-search v-model="row.article" class="field-input" :aria-label="`Matière ${index + 1}`" @change="onMatiere(row)">
							<option value="">Choisir une matière…</option>
							<option v-for="item in options?.matieres" :key="item.value" :value="item.value">{{ item.label }}</option>
						</select>
						<span v-if="matiere(row.article)" class="badge flex-none" :class="matiere(row.article)?.type === 'Fût' ? 'tone-violet' : 'tone-blue'">{{ matiere(row.article)?.type }}</span>
					</span>
					<span role="cell"><input v-model="row.quantite" class="field-input text-right tabular-nums" inputmode="decimal" :aria-label="`Quantité, matière ${index + 1}`" @input="dirty = true" /></span>
					<span role="cell">
						<select v-search v-model="row.unite" class="field-input" :aria-label="`Unité, matière ${index + 1}`" @change="dirty = true">
							<option v-if="row.unite && !options?.unites.includes(row.unite)" :value="row.unite">{{ row.unite }}</option>
							<option v-for="item in options?.unites" :key="item" :value="item">{{ item }}</option>
						</select>
					</span>
					<span role="cell" class="flex justify-center"><input v-model="row.obligatoire" type="checkbox" class="recette-check" :aria-label="`Obligatoire, matière ${index + 1}`" @change="dirty = true" /></span>
					<span role="cell" class="flex justify-end"><button type="button" class="icon-btn" :aria-label="`Retirer la matière ${index + 1}`" :disabled="lignes.length === 1" @click="removeLigne(row)"><LucideTrash2 class="h-3.5 w-3.5" aria-hidden="true" /></button></span>
				</div>
			</div>
			<div><button type="button" class="btn-secondary" @click="addLigne"><LucidePlus class="h-3.5 w-3.5" aria-hidden="true" />Ajouter une matière</button></div>
			<p class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Au moins une matière de type Fût (le vrac). {{ recette ? 'Les ordres déjà créés gardent leurs quantités.' : '' }}</span></p>
		</section>

		<ul v-if="errors.length" class="field-error" role="alert">
			<li v-for="message in errors" :key="message">{{ message }}</li>
		</ul>
		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>
		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ recette ? 'Enregistrer' : 'Créer la recette' }}</button>
		</template>
	</FormDialog>
</template>
