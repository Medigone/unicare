<script setup lang="ts">
import { computed, ref } from 'vue'
import LucideArrowUpRight from '~icons/lucide/arrow-up-right'
import LucideChevronDown from '~icons/lucide/chevron-down'
import LucideChevronUp from '~icons/lucide/chevron-up'
import LucideX from '~icons/lucide/x'
import StatusPill from '@shared/components/StatusPill.vue'
import TagEditor from './TagEditor.vue'
import { formatQty } from '@/lib/articles'
import { formatDay } from '@/lib/display'
import { etatPeremption } from '@/lib/lots'
import { useDrawerControls } from '@/lib/useDrawerControls'
import { useLot } from '@/lib/useLot'

const props = defineProps<{ id: string; position: string; noPrev: boolean; noNext: boolean }>()
const emit = defineEmits<{ prev: []; next: []; close: []; open: []; changed: [] }>()

const { lot, error, notFound, load, refresh } = useLot(() => props.id)
defineExpose({ refresh })

const root = ref<HTMLElement | null>(null)
useDrawerControls(root, { close: () => emit('close'), prev: () => emit('prev'), next: () => emit('next') })
const etat = computed(() => (lot.value ? etatPeremption(lot.value) : null))

function onTags(tags: string[]) {
	if (lot.value) lot.value.tags = tags
	emit('changed')
}
</script>

<template>
	<aside ref="root" class="bureau-drawer" aria-label="Aperçu du lot">
		<div class="bureau-drawer-head">
			<button type="button" class="icon-btn" aria-label="Lot précédent" :disabled="noPrev" @click="emit('prev')"><LucideChevronUp class="h-4 w-4" aria-hidden="true" /></button>
			<button type="button" class="icon-btn" aria-label="Lot suivant" :disabled="noNext" @click="emit('next')"><LucideChevronDown class="h-4 w-4" aria-hidden="true" /></button>
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
			<p v-else-if="notFound" class="py-8 text-center text-ink-gray-6">Ce lot n'existe pas ou n'existe plus.</p>
			<p v-else-if="!lot" class="py-8 text-center text-ink-gray-6">Chargement du lot…</p>

			<template v-else>
				<div>
					<div class="flex flex-wrap items-center gap-1.5">
						<h2 class="text-xl font-semibold tabular-nums">{{ lot.name }}</h2>
						<StatusPill v-if="etat === 'perime'" status="Périmé" tone="red" />
						<StatusPill v-else-if="etat === 'proche'" status="Périme bientôt" tone="amber" />
						<StatusPill v-if="lot.desactive" status="Désactivé" tone="gray" />
					</div>
					<p class="mt-0.5 text-sm text-ink-gray-7"><RouterLink class="ref-link" :to="{ name: 'Article', params: { id: lot.article } }">{{ lot.designation }}</RouterLink></p>
					<TagEditor class="mt-1.5" doctype="Batch" :name="lot.name" :modified="lot.modified" :tags="lot.tags" :can-edit="lot.can_edit" @changed="onTags" />
				</div>

				<dl class="bureau-drawer-facts">
					<div><dt>En stock</dt><dd class="tabular-nums">{{ formatQty(lot.quantite) }} {{ lot.unite }}</dd></div>
					<div><dt>Péremption</dt><dd class="tabular-nums" :class="etat === 'perime' && 'text-tone-red'">{{ formatDay(lot.peremption) || '—' }}</dd></div>
					<div><dt>Origine</dt><dd>{{ lot.origine || '—' }}</dd></div>
					<div><dt>Lot fournisseur</dt><dd class="truncate tabular-nums">{{ lot.lot_fournisseur || '—' }}</dd></div>
				</dl>

				<section class="card flex flex-col gap-1">
					<h3 class="text-base font-semibold">Par dépôt</h3>
					<p v-if="!lot.depots.length" class="text-ink-gray-6">Plus rien en stock.</p>
					<div v-for="row in lot.depots" :key="row.depot" class="flex items-baseline justify-between gap-2">
						<span class="min-w-0 truncate">{{ row.depot }}</span>
						<span class="flex-none tabular-nums text-ink-gray-7">{{ formatQty(row.qty) }} {{ lot.unite }}</span>
					</div>
				</section>
			</template>
		</div>
	</aside>
</template>
