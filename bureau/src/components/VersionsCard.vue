<script setup lang="ts">
import { computed } from 'vue'
import LucideCopyPlus from '~icons/lucide/copy-plus'
import StatusPill from '@shared/components/StatusPill.vue'
import { openVersion, type Versions } from '@/lib/versions'

/**
 * Bandeau des versions d'une pièce : annulée, elle propose sa nouvelle version (ou mène à celle qui existe) ;
 * refaite, elle rappelle la pièce d'origine. `fiche` : la route de la fiche de ce type de pièce.
 */
const props = defineProps<{ versions: Versions; docstatus: number; fiche: string; canAmend: boolean; busy?: boolean }>()
const emit = defineEmits<{ amend: [] }>()

const remplacante = computed(() => openVersion(props.versions))
const autres = computed(() => props.versions.suivantes)
</script>

<template>
	<div v-if="docstatus === 2" role="status" class="flex flex-wrap items-center gap-2 rounded-control tone-gray px-3.5 py-2.5">
		<span class="flex-auto">
			<strong class="font-semibold">Pièce annulée.</strong>
			<template v-if="remplacante">
				Remplacée par
				<RouterLink class="ref-link tabular-nums" :to="{ name: fiche, params: { id: remplacante.name } }">{{ remplacante.name }}</RouterLink>.
			</template>
			<template v-else-if="canAmend"> Pour la corriger, créez une nouvelle version : un brouillon avec le même contenu.</template>
		</span>
		<button v-if="canAmend && !remplacante" type="button" class="btn-secondary" :disabled="busy" @click="emit('amend')"><LucideCopyPlus class="h-3.5 w-3.5" aria-hidden="true" />Nouvelle version</button>
	</div>
	<p v-if="versions.origine" class="text-sm text-ink-gray-7">
		Nouvelle version de
		<RouterLink class="ref-link tabular-nums" :to="{ name: fiche, params: { id: versions.origine.name } }">{{ versions.origine.name }}</RouterLink>
		(annulée).
	</p>
	<section v-if="autres.length > 1 || (autres.length && docstatus !== 2)" class="card ref-card">
		<h3>Versions</h3>
		<div class="ref-scroll"><table class="ref-table">
			<thead><tr><th>Pièce</th><th>Statut</th></tr></thead>
			<tbody>
				<tr v-for="row in autres" :key="row.name">
					<td><RouterLink class="ref-link tabular-nums" :to="{ name: fiche, params: { id: row.name } }">{{ row.name }}</RouterLink></td>
					<td><StatusPill :status="row.status" /></td>
				</tr>
			</tbody>
		</table></div>
	</section>
</template>
