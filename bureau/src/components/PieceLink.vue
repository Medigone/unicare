<script setup lang="ts">
import { computed } from 'vue'
import { pieceLink } from '@/lib/fiches'

/** Lien vers une pièce : sa fiche dans le bureau, ou le Desk (nouvel onglet) si le bureau ne l'affiche pas. */
const props = defineProps<{ doctype: string; name: string }>()
const link = computed(() => pieceLink(props.doctype, props.name))
</script>

<template>
	<RouterLink v-if="'to' in link" class="ref-link" :to="link.to"><slot>{{ name }}</slot></RouterLink>
	<a v-else class="ref-link" :href="link.href" target="_blank" rel="noopener noreferrer"><slot>{{ name }}</slot></a>
</template>
