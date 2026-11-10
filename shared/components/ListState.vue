<script setup lang="ts">
/** État vide d'une liste ou d'un onglet. `illustration` : la marque « U. » en gris doux (même dessin que BrandMark). */
defineProps<{ title: string; text: string; illustration?: boolean }>()
</script>

<template>
	<div class="list-state">
		<svg v-if="illustration" class="list-state-art" viewBox="0 0 100 100" aria-hidden="true">
			<path d="M11 18h17v38a9 9 0 0 0 18 0V18h17v38a26 26 0 0 1-52 0Z" />
			<circle cx="80.5" cy="73.5" r="8.5" />
		</svg>
		<h3>{{ title }}</h3>
		<p>{{ text }}</p>
		<slot />
	</div>
</template>
