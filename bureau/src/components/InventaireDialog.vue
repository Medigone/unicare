<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import LucideInfo from '~icons/lucide/info'
import FormDialog from '@shared/components/FormDialog.vue'
import { createInventaire, getInventaireOptions } from '@/lib/api'
import type { InventaireOptions } from '@/lib/inventaires'

/** Nouvel inventaire : un dépôt et, au choix, un groupe d'articles. La feuille de comptage se prépare au stock d'aujourd'hui. */
const emit = defineEmits<{ close: []; created: [name: string] }>()

const values = reactive({ depot: '', groupe: '' })
const options = ref<InventaireOptions | null>(null)
const loadError = ref('')
const serverError = ref('')
const depotError = ref('')
const busy = ref(false)
const dirty = computed(() => Boolean(values.depot || values.groupe))

onMounted(async () => {
	try {
		options.value = await getInventaireOptions()
	} catch (e) {
		loadError.value = (e as Error).message
	}
})

async function submit() {
	if (busy.value) return
	serverError.value = ''
	depotError.value = values.depot ? '' : 'Choisissez le dépôt à compter.'
	if (depotError.value) return
	busy.value = true
	try {
		emit('created', (await createInventaire({ depot: values.depot, groupe: values.groupe || undefined })).name)
		emit('close')
	} catch (e) {
		serverError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog title="Nouvel inventaire" :dirty="dirty" :busy="busy" hint="Ctrl + Entrée pour préparer la feuille" @close="emit('close')" @submit="submit">
		<p v-if="loadError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ loadError }}</p>
		<div class="form-grid">
			<div class="form-field">
				<label class="field-label" for="inventaire-depot">Dépôt à compter <span class="req">obligatoire</span></label>
				<select v-search id="inventaire-depot" v-model="values.depot" class="field-input" :aria-invalid="Boolean(depotError)" @change="depotError = ''">
					<option value="">Choisir…</option>
					<option v-for="item in options?.depots" :key="item" :value="item">{{ item }}</option>
				</select>
				<p v-if="depotError" class="field-error" role="alert">{{ depotError }}</p>
			</div>
			<div class="form-field">
				<label class="field-label" for="inventaire-groupe">Groupe d'articles</label>
				<select v-search id="inventaire-groupe" v-model="values.groupe" class="field-input">
					<option value="">Tous les articles</option>
					<option v-for="item in options?.groupes" :key="item" :value="item">{{ item }}</option>
				</select>
			</div>
		</div>
		<p class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>La feuille reprend chaque article du dépôt, et chaque lot pour les articles suivis par lots, avec la quantité en stock aujourd'hui. Vous saisirez ensuite ce que vous comptez ; rien ne bouge avant la validation.</span></p>
		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>
		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Préparation…' : 'Préparer la feuille de comptage' }}</button>
		</template>
	</FormDialog>
</template>
