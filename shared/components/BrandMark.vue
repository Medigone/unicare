<script setup lang="ts">
/** `lg` : écrans où la marque est seule en tête (connexion). `markOnly` : le logo sans le nom, dans la barre du haut. */
withDefaults(defineProps<{ size?: 'md' | 'lg'; markOnly?: boolean }>(), { size: 'md' })
</script>

<!-- Monogramme « U. » : un U plein, extrémités droites et fond en demi-cercle, et un point posé sur la ligne de base.
     Tout suit la couleur du texte, en clair comme en sombre. -->
<template>
	<div class="flex items-center" :class="size === 'lg' ? 'gap-3' : 'gap-2'">
		<svg viewBox="0 0 100 100" class="shrink-0 text-ink-gray-9" :class="size === 'lg' ? 'h-12 w-12' : 'h-7 w-7'" aria-hidden="true">
			<path fill="currentColor" d="M11 18h17v38a9 9 0 0 0 18 0V18h17v38a26 26 0 0 1-52 0Z" />
			<circle cx="80.5" cy="73.5" r="8.5" fill="currentColor" />
		</svg>
		<p v-if="!markOnly" class="min-w-0 truncate font-bold tracking-tight" :class="size === 'lg' ? 'text-xl' : 'text-sm'">Unicare</p>
	</div>
</template>
