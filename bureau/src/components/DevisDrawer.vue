<script setup lang="ts">
import { ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucideChevronUp from '~icons/lucide/chevron-up'
import LucideX from '~icons/lucide/x'
import StatusPill from '@shared/components/StatusPill.vue'
import TagEditor from './TagEditor.vue'
import { formatAmount } from '@/lib/clients'
import { formatDay } from '@/lib/display'
import { formatQty } from '@/lib/articles'
import { useDevis } from '@/lib/useDevis'
import { useDrawerControls } from '@/lib/useDrawerControls'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { devis, error, notFound, load, refresh } = useDevis(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })

function onTags(tags: string[]) {
	if (devis.value) devis.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu du devis">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Devis précédent" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Devis suivant" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
			<span class="text-xs text-ink-gray-6">{{ position }}</span>
			<span class="flex-auto"></span>
			<button type="button" class="btn-primary" @click="emit('open')">
				Ouvrir la fiche
				<LucideArrowUpRight class="h-3.5 w-3.5" aria-hidden="true" />
			</button>
			<button type="button" class="icon-btn" aria-label="Fermer l'aperçu" @click="emit('close')"><LucideX class="h-4 w-4" aria-hidden="true" /></button>
		</div>

		<div class="bureau-drawer-body">
			<p v-if="error" role="alert" class="text-tone-red">
				{{ error }}
				<button type="button" class="ml-1 font-semibold underline" @click="load">Réessayer</button>
			</p>
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Ce devis n'existe pas ou n'existe plus.</p>
			<p v-else-if="!devis" class="py-8 text-center text-ink-gray-6">Chargement du devis…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold tabular-nums">{{ devis.name }}</h2>
						<StatusPill :status="devis.status" />
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7">
						<RouterLink class="ref-link" :to="{ name: 'Client', params: { id: devis.client } }">{{ devis.client_label }}</RouterLink>
						· {{ formatDay(devis.date) }}
					</p>
					<TagEditor class="mt-1.5" doctype="Quotation" :name="devis.name" :modified="devis.modified" :tags="devis.tags" :can-edit="true" @changed="onTags" />
				</div>

				<dl class="bureau-drawer-facts">
					<div><dt>Total HT</dt><dd class="tabular-nums">{{ formatAmount(devis.total) }} DA</dd></div>
					<div><dt>Total TTC</dt><dd class="tabular-nums">{{ formatAmount(devis.total_ttc) }} DA</dd></div>
					<div><dt>Valable jusqu'au</dt><dd class="tabular-nums">{{ formatDay(devis.valable) || '—' }}</dd></div>
					<div><dt>Créé par</dt><dd class="truncate">{{ devis.cree_par }}</dd></div>
				</dl>

				<p v-if="devis.blocked.length" role="status" class="rounded-control tone-amber px-3 py-2 text-sm">{{ devis.blocked.join(' ') }}</p>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Lignes</h3>
					<p v-if="!devis.lignes.length" class="text-ink-gray-6">Aucune ligne.</p>
					<div v-for="line in devis.lignes.slice(0, 6)" :key="line.name" class="flex items-baseline justify-between gap-2">
						<span class="min-w-0 truncate" :title="line.designation">{{ line.designation }}</span>
						<span class="flex-none tabular-nums text-ink-gray-7">{{ formatQty(line.quantite) }} {{ line.unite }} · <span :class="!line.prix && 'text-tone-amber'">{{ line.prix ? `${formatAmount(line.montant)} DA` : 'sans prix' }}</span></span>
					</div>
					<button v-if="devis.lignes.length > 6" type="button" class="self-start text-sm text-link" @click="emit('open')">Voir les {{ devis.lignes.length }} lignes</button>
				</section>
			</template>
		</div>
	</aside>
</template>
