<script setup lang="ts">
import { computed, ref } from 'vue'
import LucideArrowRight from '~icons/lucide/arrow-right'
import LucideFolder from '~icons/lucide/folder'
import FormDialog from '@shared/components/FormDialog.vue'
import { createValeur, deplacerValeur } from '@/lib/api'
import { chemin, dossiersPossibles, usagesLabel, type ListeResume, type ListeValeur } from '@/lib/listes'

/**
 * Réglages › Listes de choix › Déplacer (une valeur ou un dossier dans un autre dossier), ou Nouveau dossier
 * (sans `valeur`). Les fiches gardent leur valeur : seul son rangement change.
 */
const props = defineProps<{ liste: ListeResume; valeurs: ListeValeur[]; valeur?: ListeValeur | null; dossier?: string | null }>()
const emit = defineEmits<{ close: []; done: [valeurs: ListeValeur[], message: string] }>()

const RACINE = ''
const deplacement = computed(() => Boolean(props.valeur))
const dossiers = computed(() => dossiersPossibles(props.valeurs, props.valeur))
const actuel = props.valeur ? (props.valeur.parent ?? RACINE) : null
const cible = ref<string>(props.valeur ? (dossiers.value.find((d) => d.name !== actuel)?.name ?? RACINE) : (props.dossier ?? RACINE))
const nom = ref('')
const busy = ref(false)
const error = ref('')
const nomAffiche = computed(() => props.valeur?.name ?? (nom.value.trim() || 'Nouveau dossier'))

async function submit() {
	if (busy.value) return
	const dossier = cible.value || null
	error.value = ''
	if (props.valeur) {
		if ((props.valeur.parent ?? RACINE) === cible.value) {
			error.value = 'Choisissez un autre dossier que le dossier actuel.'
			return
		}
	} else if (!nom.value.trim()) {
		error.value = 'Donnez un nom au dossier.'
		return
	}
	busy.value = true
	try {
		if (props.valeur) {
			const fresh = await deplacerValeur(props.liste.code, props.valeur, dossier)
			emit('done', fresh, `« ${props.valeur.name} » rangé dans ${dossier ? `« ${dossier} »` : 'la racine'}.`)
		} else {
			const fresh = await createValeur(props.liste.code, nom.value.trim(), dossier, true)
			emit('done', fresh, `Dossier « ${nom.value.trim()} » créé.`)
		}
	} catch (e) {
		error.value = (e as Error).message
	} finally {
		busy.value = false
	}
}
</script>

<template>
	<FormDialog :title="valeur ? `Déplacer « ${valeur.name} »` : 'Nouveau dossier'" :dirty="!deplacement && Boolean(nom.trim())" :busy="busy" :hint="deplacement ? 'Ctrl + Entrée pour déplacer' : 'Ctrl + Entrée pour créer'" @close="emit('close')" @submit="submit">
		<p v-if="valeur" class="text-sm text-ink-gray-7">
			Choisissez le dossier où ranger {{ valeur.dossier ? 'ce dossier et son contenu' : 'cette valeur' }}.
			<template v-if="!valeur.dossier && valeur.usages">Ses {{ usagesLabel(valeur.usages, liste.lien.fiches) }} la gardent : seul son rangement change.</template>
		</p>
		<template v-else>
			<p class="text-sm text-ink-gray-7">Un dossier range des valeurs de « {{ liste.label }} ». Il ne se choisit pas sur une fiche.</p>
			<div class="form-field">
				<label class="field-label" for="dossier-nom">Nom du dossier <span class="req">obligatoire</span></label>
				<input id="dossier-nom" v-model="nom" class="field-input" autocomplete="off" placeholder="Ex. Emballages" @input="error = ''" />
			</div>
		</template>

		<fieldset class="form-field">
			<legend class="field-label">{{ valeur ? 'Ranger dans' : 'Dans' }}</legend>
			<div class="dossiers-choix">
				<label class="dossier-choix" :class="cible === RACINE && 'is-on'">
					<input v-model="cible" type="radio" name="dossier-cible" :value="RACINE" />
					<LucideFolder class="h-4 w-4 flex-none text-[var(--accent)]" aria-hidden="true" />
					<span class="flex-auto font-medium">La racine</span>
					<span v-if="actuel === RACINE" class="text-xs text-ink-gray-6">actuel</span>
				</label>
				<label v-for="dossier in dossiers" :key="dossier.name" class="dossier-choix" :class="cible === dossier.name && 'is-on'" :style="{ paddingLeft: `${0.625 + dossier.niveau * 1.125}rem` }">
					<input v-model="cible" type="radio" name="dossier-cible" :value="dossier.name" />
					<LucideFolder class="h-4 w-4 flex-none text-[var(--accent)]" aria-hidden="true" />
					<span class="flex-auto font-medium">{{ dossier.name }}</span>
					<span v-if="actuel === dossier.name" class="text-xs text-ink-gray-6">actuel</span>
				</label>
			</div>
		</fieldset>

		<p class="dossier-chemin">
			<template v-if="valeur">
				<span class="text-ink-gray-6 line-through">{{ chemin(valeurs, valeur.name) }}</span>
				<LucideArrowRight class="h-3.5 w-3.5 flex-none text-[var(--accent)]" aria-hidden="true" />
			</template>
			<b class="text-[var(--accent-fonce)]">{{ chemin(valeurs, nomAffiche, cible || null) }}</b>
		</p>
		<p v-if="error" role="alert" class="rounded-control tone-red px-3 py-2 text-sm">{{ error }}</p>
		<template #actions>
			<button type="button" class="btn-primary" :disabled="busy" @click="submit">{{ busy ? '…' : valeur ? 'Déplacer' : 'Créer le dossier' }}</button>
		</template>
	</FormDialog>
</template>
