<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import LucideInfo from '~icons/lucide/info'
import FormDialog from '@shared/components/FormDialog.vue'
import { createDepot, getDepotOptions, updateDepot } from '@/lib/api'
import type { DepotDetail, DepotOptions } from '@/lib/depots'

/** Nouveau dépôt, ou modification d'un dépôt : le nom ne se saisit qu'à la création (il est dans les écritures). */
const props = defineProps<{ depot?: DepotDetail }>()
const emit = defineEmits<{ close: []; created: [name: string]; saved: [depot: DepotDetail] }>()

const editing = computed(() => Boolean(props.depot))
const initial = { depot: '', parent: props.depot?.parent ?? '', type: props.depot?.type ?? '', desactive: Boolean(props.depot?.desactive) }
const values = reactive({ ...initial })
const options = ref<DepotOptions | null>(null)
const loadError = ref('')
const serverError = ref('')
const nameError = ref('')
const busy = ref(false)
const dirty = computed(() => JSON.stringify(values) !== JSON.stringify(initial))

onMounted(async () => {
	try {
		options.value = await getDepotOptions()
		if (!editing.value && !values.parent && options.value.groupes.length) {
			// Prérempli : ce n'est pas une saisie, la fermeture ne demande pas de confirmation.
			values.parent = options.value.groupes[0]
			initial.parent = values.parent
		}
	} catch (e) {
		loadError.value = (e as Error).message
	}
})

async function submit() {
	if (busy.value) return
	serverError.value = ''
	nameError.value = !editing.value && !values.depot.trim() ? 'Saisissez le nom du dépôt.' : ''
	if (nameError.value) return
	if (editing.value && !dirty.value) {
		emit('close')
		return
	}
	busy.value = true
	try {
		const payload = { parent: values.parent, type: values.type, desactive: values.desactive ? 1 : 0 }
		if (props.depot) emit('saved', await updateDepot(props.depot, payload))
		else emit('created', (await createDepot({ ...payload, depot: values.depot.trim() })).name)
		emit('close')
	} catch (e) {
		serverError.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog :title="editing ? `Modifier le dépôt ${depot?.depot}` : 'Nouveau dépôt'" :dirty="dirty" :busy="busy" :hint="editing ? 'Ctrl + Entrée pour enregistrer' : 'Ctrl + Entrée pour créer'" @close="emit('close')" @submit="submit">
		<p v-if="loadError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ loadError }}</p>
		<div v-if="!editing" class="form-field">
			<label class="field-label" for="depot-nom">Nom du dépôt <span class="req">obligatoire</span></label>
			<input id="depot-nom" v-model="values.depot" class="field-input" placeholder="Magasin matières premières" autocomplete="off" :aria-invalid="Boolean(nameError)" @input="nameError = ''" />
			<p v-if="nameError" class="field-error" role="alert">{{ nameError }}</p>
			<p v-else class="field-note"><LucideInfo class="mt-px h-3.5 w-3.5 flex-none" aria-hidden="true" /><span>Le code est complété par l'abréviation de la société, par exemple « {{ values.depot.trim() || 'Magasin' }} - U ».</span></p>
		</div>
		<div class="form-grid">
			<div class="form-field">
				<label class="field-label" for="depot-groupe">Groupe</label>
				<select v-search id="depot-groupe" v-model="values.parent" class="field-input">
					<option value="">Aucun</option>
					<option v-for="item in options?.groupes" :key="item" :value="item">{{ item }}</option>
				</select>
			</div>
			<div class="form-field">
				<label class="field-label" for="depot-type">Type</label>
				<select v-search id="depot-type" v-model="values.type" class="field-input">
					<option value="">Aucun</option>
					<option v-for="item in options?.types" :key="item" :value="item">{{ item }}</option>
				</select>
			</div>
		</div>
		<label v-if="editing" class="flex items-center gap-2 text-sm"><input v-model="values.desactive" type="checkbox" />Dépôt désactivé (il n'est plus proposé dans les pièces ; il doit être vide)</label>
		<p v-if="serverError" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ serverError }}</p>
		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? 'Enregistrement…' : editing ? 'Enregistrer' : 'Créer le dépôt' }}</button>
		</template>
	</FormDialog>
</template>
