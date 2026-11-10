<script setup lang="ts">
import { computed } from 'vue'
import BureauShell from '@/components/BureauShell.vue'
import { activePoste } from '@/lib/postes'

/** Accueil du poste : point de départ en attendant les tableaux de bord des pages métier. */
const firstName = (window.user_fullname || window.user || '').trim().split(/\s+/)[0]
const poste = computed(() => activePoste())
</script>

<template>
	<BureauShell :crumbs="[{ label: 'Accueil' }]" active="accueil">
		<div class="bureau-work">
			<section class="card flex flex-col gap-2 p-6">
				<h1 class="text-[20px] font-semibold leading-tight text-ink-gray-9">Bonjour{{ firstName ? ` ${firstName}` : '' }}</h1>
				<p class="text-ink-gray-7">Poste {{ poste.label }}. Les écrans du bureau Unicare arrivent ici au fur et à mesure ; en attendant, le Desk reste ouvert pour tout le reste.</p>
				<div class="mt-2">
					<a class="btn-secondary" href="/app" target="_blank" rel="noopener noreferrer">Ouvrir le Desk</a>
				</div>
			</section>
		</div>
	</BureauShell>
</template>
