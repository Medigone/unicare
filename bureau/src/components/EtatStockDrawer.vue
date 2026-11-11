<script setup lang="ts">
import { ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucideChevronUp from '~icons/lucide/chevron-up'
import LucideX from '~icons/lucide/x'
import StatusPill from '@shared/components/StatusPill.vue'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { niveauStock } from '@/lib/etatStock'
import { useDrawerControls } from '@/lib/useDrawerControls'
import { useLigneStock } from '@/lib/useLigneStock'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { ligne, error, notFound, load, refresh } = useLigneStock(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

const NIVEAUX = { negatif: ['Stock négatif', 'red'], rupture: ['En rupture', 'red'], bas: ['Sous le seuil', 'amber'] } as const
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu du stock">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Ligne précédente" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Ligne suivante" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
			<span class="text-xs text-ink-gray-6">{{ position }}</span>
			<span class="flex-auto"></span>
			<button type="button" class="btn-primary" @click="emit('open')">
				Voir l'historique
				<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />
			</button>
			<button type="button" class="icon-btn" aria-label="Fermer l'aperçu" @click="emit('close')"><LucideX class="h-4 w-4" aria-hidden="true" /></button>
		</div>

		<div class="bureau-drawer-body">
			<p v-if="error" role="alert" class="text-tone-red">
				{{ error }}
				<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
			</p>
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Cette ligne de stock n'existe plus.</p>
			<p v-else-if="!ligne" class="py-8 text-center text-ink-gray-6">Chargement…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold">{{ ligne.designation }}</h2>
						<StatusPill v-if="niveauStock(ligne)" :status="NIVEAUX[niveauStock(ligne)!][0]" :tone="NIVEAUX[niveauStock(ligne)!][1]" />
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7">
						<RouterLink class="ref-link" :to="{ name: 'Article', params: { id: ligne.article } }">{{ ligne.article }}</RouterLink>
						· <RouterLink class="ref-link" :to="{ name: 'Depot', params: { id: ligne.depot } }">{{ ligne.depot }}</RouterLink>
					</p>
				</div>

				<dl class="bureau-drawer-facts">
					<div><dt>En stock</dt><dd class="tabular-nums">{{ formatQty(ligne.quantite) }} {{ ligne.unite }}</dd></div>
					<div><dt>Réservé</dt><dd class="tabular-nums">{{ formatQty(ligne.reserve) }}</dd></div>
					<div><dt>Commandé</dt><dd class="tabular-nums">{{ formatQty(ligne.commande) }}</dd></div>
					<div><dt>Projeté</dt><dd class="tabular-nums">{{ formatQty(ligne.projete) }}</dd></div>
					<div><dt>Seuil</dt><dd class="tabular-nums">{{ ligne.seuil === null ? 'Aucun' : formatQty(ligne.seuil) }}</dd></div>
					<div><dt>Valeur</dt><dd class="tabular-nums">{{ formatAmount(ligne.valeur) }} DA</dd></div>
				</dl>
			</template>
		</div>
	</aside>
</template>
