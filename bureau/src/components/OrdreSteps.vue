<script setup lang="ts">
import LucideCheck from '~icons/lucide/check'
import LucideX from '~icons/lucide/x'
import { dureeText, type OrdreEtape } from '@/lib/ordres'

/** Bandeau des étapes d'un ordre : Planifier → Préparer → Produire → Clôturer. `compact` : sans les détails (aperçu). */
defineProps<{ etapes: OrdreEtape[]; compact?: boolean }>()

const HINTS: Record<OrdreEtape['key'], string> = {
	planifier: 'quantités, lots, contrôles',
	preparer: "matières à l'atelier",
	produire: 'saisie des quantités',
	cloturer: 'stock mis à jour',
}

function when(etape: OrdreEtape) {
	if (etape.statut === 'annule') return 'non faite'
	if (etape.statut === 'en_cours') return etape.key === 'produire' && !etape.quand ? 'à démarrer' : 'étape en cours'
	if (etape.statut === 'a_venir') return HINTS[etape.key]
	if (!etape.quand) return 'faite'
	const date = new Date(etape.quand.replace(' ', 'T'))
	const label = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date)
	return etape.duree ? `${label} · ${dureeText(etape.duree)}` : label
}
</script>

<template>
	<ol class="ordre-steps" :class="compact && 'ordre-steps-compact'" aria-label="Étapes de l'ordre">
		<li v-for="(etape, index) in etapes" :key="etape.key" class="ordre-step" :data-statut="etape.statut" :aria-current="etape.statut === 'en_cours' ? 'step' : undefined">
			<span class="ordre-step-dot" aria-hidden="true">
				<LucideCheck v-if="etape.statut === 'fait'" class="h-3.5 w-3.5" />
				<LucideX v-else-if="etape.statut === 'annule'" class="h-3.5 w-3.5" />
				<template v-else>{{ index + 1 }}</template>
			</span>
			<span class="min-w-0">
				<span class="ordre-step-label">{{ etape.label }}</span>
				<span v-if="!compact" class="ordre-step-when">{{ when(etape) }}</span>
				<span class="sr-only"> : {{ { fait: 'faite', en_cours: 'en cours', a_venir: 'à venir', annule: 'non faite' }[etape.statut] }}</span>
			</span>
		</li>
	</ol>
</template>
