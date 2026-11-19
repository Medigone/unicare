<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import LucideArrowRight from '~icons/lucide/arrow-right'
import FormDialog from '@shared/components/FormDialog.vue'
import { fusionnerValeur, getFiches } from '@/lib/api'
import { singulier, usagesLabel, type FichesValeur, type ListeResume, type ListeValeur } from '@/lib/listes'

/**
 * Réglages › Listes de choix › Fusionner : les fiches d'une valeur passent dans une autre, puis la valeur est supprimée.
 * Pour un doublon ou une faute de frappe. Ne se défait pas.
 */
const props = defineProps<{ liste: ListeResume; valeur: ListeValeur; valeurs: ListeValeur[]; cible?: string | null }>()
const emit = defineEmits<{ close: []; done: [valeurs: ListeValeur[], cible: string] }>()

const choix = computed(() => props.valeurs.filter((row) => row.name !== props.valeur.name && !row.dossier).sort((a, b) => b.usages - a.usages || a.name.localeCompare(b.name)))
const cible = ref(props.cible && props.cible !== props.valeur.name ? props.cible : (choix.value[0]?.name ?? ''))
const cibleRow = computed(() => props.valeurs.find((row) => row.name === cible.value) ?? null)
const fiches = ref<FichesValeur | null>(null)
const busy = ref(false)
const error = ref('')
const mot = computed(() => props.liste.lien.fiches)

onMounted(async () => {
	if (!props.valeur.usages) return
	try {
		fiches.value = await getFiches(props.liste.code, props.valeur.name)
	} catch {
		fiches.value = null
	}
})

async function submit() {
	if (busy.value || !cible.value) return
	busy.value = true
	error.value = ''
	try {
		emit('done', await fusionnerValeur(props.liste.code, props.valeur, cible.value), cible.value)
	} catch (e) {
		error.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog :title="`Fusionner « ${valeur.name} »`" :dirty="false" :busy="busy" hint="Ctrl + Entrée pour fusionner" @close="emit('close')" @submit="submit">
		<p class="text-sm text-ink-gray-7">Les {{ mot }} classés dans « {{ valeur.name }} » passent dans la valeur choisie, puis « {{ valeur.name }} » est supprimée. Utile pour un doublon ou une faute de frappe.</p>
		<div class="form-field">
			<label class="field-label" for="fusion-cible">Fusionner dans</label>
			<select id="fusion-cible" v-model="cible" class="field-input">
				<option v-for="row in choix" :key="row.name" :value="row.name">{{ row.name }} — {{ usagesLabel(row.usages, mot) }}</option>
			</select>
		</div>

		<div class="fusion-apercu" aria-label="Résultat de la fusion">
			<div class="fusion-carte">
				<span class="font-semibold text-ink-gray-6 line-through">{{ valeur.name }}</span>
				<span class="text-xs text-ink-gray-6">{{ usagesLabel(valeur.usages, mot) }} · sera supprimée</span>
			</div>
			<LucideArrowRight class="h-4 w-4 flex-none text-[var(--accent)]" aria-hidden="true" />
			<div class="fusion-carte fusion-cible">
				<span class="font-semibold">{{ cible || '—' }}</span>
				<span class="text-xs">{{ usagesLabel((cibleRow?.usages ?? 0) + valeur.usages, mot) }} après la fusion</span>
			</div>
		</div>

		<div v-if="fiches?.fiches.length" class="flex flex-col gap-1.5">
			<span class="field-label">{{ mot.charAt(0).toUpperCase() + mot.slice(1) }} reclassés</span>
			<ul class="list-disc pl-5 text-sm text-ink-gray-8">
				<li v-for="fiche in fiches.fiches" :key="fiche.name">{{ fiche.titre }}<span v-if="fiche.titre !== fiche.name" class="text-ink-gray-6"> · {{ fiche.name }}</span></li>
				<li v-if="fiches.total > fiches.fiches.length" class="text-ink-gray-6">et {{ fiches.total - fiches.fiches.length }} autre{{ fiches.total - fiches.fiches.length > 1 ? 's' : '' }} {{ fiches.total - fiches.fiches.length > 1 ? mot : singulier(mot) }}</li>
			</ul>
		</div>
		<p class="rounded-control tone-amber px-3 py-2 text-sm">Cette action ne se défait pas.</p>
		<p v-if="error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ error }}</p>
		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy || !cible" @click="submit">{{ busy ? 'Fusion…' : `Fusionner dans « ${cible} »` }}</button>
		</template>
	</FormDialog>
</template>
