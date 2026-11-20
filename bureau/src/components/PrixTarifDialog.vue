<script setup lang="ts">
import FormDialog from '@shared/components/FormDialog.vue'
import { formatAmount } from '@/lib/clients'

/**
 * Prix saisis différents de ceux de la liste de prix, au moment d'enregistrer une pièce : la personne choisit de
 * mettre la liste à jour, ou de garder ces prix pour cette pièce seulement. Fermer revient à la saisie.
 */
defineProps<{ liste: string; piece: string; lignes: { article: string; designation: string; saisi: number; tarif: number }[]; nouveaux: number }>()
const emit = defineEmits<{ close: []; choose: [choice: 'liste' | 'piece'] }>()
</script>

<template>
	<FormDialog class="confirm-dialog" title="Prix différents de la liste" :dirty="false" hint="Ctrl + Entrée pour mettre la liste à jour" @close="emit('close')" @submit="emit('choose', 'liste')">
		<p>{{ lignes.length > 1 ? 'Ces prix diffèrent' : 'Ce prix diffère' }} de la liste « {{ liste }} ».</p>
		<div class="devis-lines" role="table" aria-label="Prix saisis et prix de la liste">
			<div class="devis-line devis-line-head" role="row" style="grid-template-columns: minmax(0, 1fr) auto auto">
				<span role="columnheader">Article</span>
				<span role="columnheader" class="end">Liste</span>
				<span role="columnheader" class="end">Saisi</span>
			</div>
			<div v-for="item in lignes" :key="item.article" class="devis-line" role="row" style="grid-template-columns: minmax(0, 1fr) auto auto">
				<span role="cell" class="truncate">{{ item.designation }}</span>
				<span role="cell" class="end tabular-nums text-ink-gray-6">{{ formatAmount(item.tarif) }}</span>
				<span role="cell" class="end tabular-nums font-semibold">{{ formatAmount(item.saisi) }}</span>
			</div>
		</div>
		<p class="field-note">
			<span
				>Mettre à jour : les prochaines pièces reprendront ces prix. Seulement sur {{ piece }} : la liste ne change pas.<template v-if="nouveaux">
					{{ nouveaux > 1 ? `Les ${nouveaux} articles` : "L'article" }} sans prix dans la liste y {{ nouveaux > 1 ? 'sont ajoutés' : 'est ajouté' }} dans les deux cas.</template
				></span
			>
		</p>
		<template #actions>
			<button type="button" class="btn-secondary" @click="emit('choose', 'piece')">Seulement sur {{ piece }}</button>
			<button type="button" class="btn-primary" @click="emit('choose', 'liste')">Mettre à jour la liste</button>
		</template>
	</FormDialog>
</template>
