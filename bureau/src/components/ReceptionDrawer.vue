<script setup lang="ts">
import { ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucideChevronUp from '~icons/lucide/chevron-up'
import LucideX from '~icons/lucide/x'
import StatusPill from '@shared/components/StatusPill.vue'
import TagEditor from './TagEditor.vue'
import { formatQty } from '@/lib/articles'
import { formatAmount } from '@/lib/clients'
import { formatDay } from '@/lib/display'
import { useDrawerControls } from '@/lib/useDrawerControls'
import { useReception } from '@/lib/useReception'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { reception: livraison, error, notFound, load, refresh } = useReception(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

function onTags(tags: string[]) {
	if (livraison.value) livraison.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu de la réception de livraison">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Réception précédente" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Réception suivante" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
			<span class="text-xs text-ink-gray-6">{{ position }}</span>
			<span class="flex-auto"></span>
			<button type="button" class="btn-primary" @click="emit('open')">
				{{ livraison?.actions.includes('preparer') ? 'Préparer' : 'Ouvrir la fiche' }}
				<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />
			</button>
			<button type="button" class="icon-btn" aria-label="Fermer l'aperçu" @click="emit('close')"><LucideX class="h-4 w-4" aria-hidden="true" /></button>
		</div>

		<div class="bureau-drawer-body">
			<p v-if="error" role="alert" class="text-tone-red">
				{{ error }}
				<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
			</p>
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Cette réception n'existe pas ou n'existe plus.</p>
			<p v-else-if="!livraison" class="py-8 text-center text-ink-gray-6">Chargement de la réception…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold tabular-nums">{{ livraison.name }}</h2>
						<StatusPill :status="livraison.status" />
						<span v-if="livraison.retour" class="record-flag">Retour</span>
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7">
						<RouterLink class="ref-link" :to="{ name: 'Fournisseur', params: { id: livraison.fournisseur } }">{{ livraison.fournisseur_label }}</RouterLink>
						· {{ formatDay(livraison.date) }}
					</p>
					<TagEditor class="mt-1.5" doctype="Purchase Receipt" :name="livraison.name" :modified="livraison.modified" :tags="livraison.tags" :can-edit="true" @changed="onTags" />
				</div>

				<dl class="bureau-drawer-facts">
					<div><dt>Total TTC</dt><dd class="tabular-nums">{{ formatAmount(livraison.total_ttc) }} DA</dd></div>
					<div><dt>Facturé</dt><dd class="tabular-nums">{{ Math.round(livraison.facture) }} %</dd></div>
					<div><dt>{{ livraison.retour ? 'Retour de' : 'Commande' }}</dt><dd class="truncate tabular-nums">{{ livraison.retour_de || livraison.commandes.join(', ') || '—' }}</dd></div>
					<div><dt>BL fournisseur</dt><dd class="truncate">{{ livraison.bl_fournisseur || '—' }}</dd></div>
				</dl>

				<p v-if="livraison.blocked.length" role="status" class="rounded-control tone-amber px-3 py-2 text-sm">{{ livraison.blocked.join(' ') }}</p>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Lignes</h3>
					<div v-for="line in livraison.lignes.slice(0, 6)" :key="line.name" class="flex items-baseline justify-between gap-2">
						<span class="min-w-0 truncate" :title="line.designation">{{ line.designation }}</span>
						<span class="flex-none text-right tabular-nums text-ink-gray-7">
							{{ formatQty(line.quantite) }} {{ line.unite }}
							<span v-if="line.lot" class="block text-xs">lot {{ line.lot }}<template v-if="line.peremption"> · périme le {{ formatDay(line.peremption) }}</template></span>
						</span>
					</div>
					<button v-if="livraison.lignes.length > 6" type="button" class="self-start text-sm text-link" @click="emit('open')">Voir les {{ livraison.lignes.length }} lignes</button>
				</section>
			</template>
		</div>
	</aside>
</template>
