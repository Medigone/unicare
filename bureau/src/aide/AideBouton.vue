<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import LucideCircleHelp from '~icons/lucide/circle-help'
import { aidePanneau, basculerAide, estRaccourciAide } from '@/lib/aide'

/** Le bouton « ? » de la barre du haut ; la touche « ? » fait pareil, de n'importe quelle page. */
function onKey(event: KeyboardEvent) {
	if (!estRaccourciAide(event)) return
	event.preventDefault()
	basculerAide()
}
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
	<button type="button" class="icon-btn aide-bouton" :aria-pressed="aidePanneau !== null" aria-label="Aide (touche ?)" title="Aide (touche ?)" @click="basculerAide">
		<LucideCircleHelp class="h-4 w-4" aria-hidden="true" />
	</button>
</template>
