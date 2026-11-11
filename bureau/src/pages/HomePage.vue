<script setup lang="ts">
import { computed } from 'vue'
import BureauShell from '@/components/BureauShell.vue'
import { activePoste } from '@/lib/postes'

/** Accueil du poste : point de départ vers les modules et leurs tableaux de bord. */
const firstName = (window.user_fullname || window.user || '').trim().split(/\s+/)[0]
const poste = computed(() => activePoste())
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Accueil' }]" active="accueil">
		<div class="bureau-work">
			<section class="card flex flex-col gap-2 p-6">
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Bonjour{{ firstName ? ` ${firstName}` : '' }}</h1>
				<p class="text-ink-gray-7">Poste {{ poste.label }}. Choisissez un module dans le rail de gauche : chacun s'ouvre sur son tableau de bord. Ctrl K (⌘ K) mène directement à une page.</p>
			</section>
		</div>
	</BureauShell>
</template>
