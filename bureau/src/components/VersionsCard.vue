<script setup lang="ts">
import { computed } from 'vue'
import StatusPill from '@shared/components/StatusPill.vue'
import { openVersion, type Versions } from '@/lib/versions'

/**
 * Bandeau des versions d'une pièce : annulée, il dit comment la corriger (le bouton « Nouvelle version » est dans
 * l'en-tête de la fiche) ou mène à la version qui la remplace ; refaite, il rappelle la pièce d'origine.
 * `fiche` : la route de la fiche de ce type de pièce.
 */
const props = defineProps<{ versions: Versions; docstatus: number; fiche: string; canAmend: boolean }>()

const remplacante = computed(() => openVersion(props.versions))
const autres = computed(() => props.versions.suivantes)
</script>

<template>
	<p v-if="docstatus === 2" role="status" class="rounded-control tone-gray px-3.5 py-2.5">
		<span>
			<strong class="font-semibold">Pièce annulée.</strong>
			<template v-if="remplacante">
				Remplacée par
				<RouterLink class="ref-link tabular-nums" :to="{ name: fiche, params: { id: remplacante.name } }">{{ remplacante.name }}</RouterLink>.
			</template>
			<template v-else-if="canAmend"> Pour la corriger, créez une nouvelle version (bouton en haut) : un brouillon avec le même contenu.</template>
		</span>
	</p>
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
